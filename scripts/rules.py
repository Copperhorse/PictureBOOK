"""Story-independent code rules (no models, no GPU), used by plan.py / render.py / regen.py and unit-tested in tests/.
Nothing in here may mention a particular story."""
import os, re
from common import _none

# ---------------------------------------------------------------- limits that scale with the story, and GPU-memory settings
DEFAULT_PAGES, MAX_PAGES = 6, 10          # the brief asks for 4-6 pages; --pages N allows more for a long story
MAX_CHARS_PER_PAGE = 4                    # measured on the 8 GB card (see docs/research/page-defects.md); one named setting
def limits_for_story(n_sentences, n_pages=DEFAULT_PAGES):
    """How many characters / places the planner may list, and how many pages to make, for a story of n_sentences sentences."""
    n_pages = max(1, min(int(n_pages), MAX_PAGES, n_sentences))
    return {"n_pages": n_pages, "max_chars": 6, "max_places": max(2, min(5, 1 + n_sentences // 7))}
def ref_pixels(n_images):
    """Side length of each input picture for one page render: plate + characters share the 8 GB card (3+ pictures at 1024 px ran out of memory)."""
    return {1: 1024, 2: 1024, 3: 768}.get(n_images, 512 if n_images <= 4 else 448)
def page_seed(page_index, attempt=0):
    """Seed of a page render; every redraw (attempt + 1) gives a different picture, deterministically."""
    return 100 + page_index + 1000 * attempt

CJK = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]")
def clean_text(obj):
    """The small model sometimes leaks Chinese/Japanese/Korean characters into English fields; remove them from every string of a nested structure."""
    if isinstance(obj, str): return re.sub(r"\s{2,}", " ", CJK.sub("", obj)).strip()
    if isinstance(obj, list): return [clean_text(x) for x in obj]
    if isinstance(obj, dict): return {k: clean_text(v) for k, v in obj.items()}
    return obj
def setting_lines(envs, width=110):
    """One line per place for the page prompt, so the model picks the place where the page's action happens (name alone is not enough)."""
    return "\n".join(f"- {e['name']}: {e['location'][:width]}" for e in envs)

def slug(s): return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

# ---------------------------------------------------------------- page ranges, layout and plate rules
def page_ranges(n_sentences, n_pages):
    """Sentence ranges (1-based, inclusive) per page, grouped evenly. One sentence per page when there are at most n_pages sentences."""
    n_pages = max(1, min(n_pages, n_sentences))
    bounds = [round(i * n_sentences / n_pages) for i in range(n_pages + 1)]
    return [(bounds[i] + 1, bounds[i + 1]) for i in range(n_pages)]
def clean_layout(layout, max_per_page=MAX_CHARS_PER_PAGE):
    """Each character at most once per page, at most max_per_page characters (GPU memory)."""
    seen = set(); out = []
    for l in layout:
        if l["character"] in seen: continue
        seen.add(l["character"]); out.append(l)
    return out[:max_per_page]

STOP = set("the a an and of to in on at for with his her their its this that was were is are be been by from as it he she they them but or into over under who which than then there some very more most".split())
def words(t): return [w for w in re.findall(r"[a-z']+", t.lower()) if len(w) > 3 and w not in STOP]
def carried_words(chars):
    """Words naming what the characters carry or wear: such things belong to the character, never to the background plate."""
    return set(w for c in chars for w in words(" ".join([c["accessories"], c["headwear"], c["eyewear"]] + [o["item"] for o in c["outfit"]])))
def strip_carried(envs, chars):
    carried = carried_words(chars)
    for e in envs: e["key_objects"] = [k for k in e["key_objects"] if not (set(words(k)) & carried)]
    return envs

# ---------------------------------------------------------------- which fields did the story state (vs the model invent)?
LEX = {"age_group": {"child": ["boy", "girl", "child", "kid", "young"], "adult": ["man", "woman", "adult"], "elderly": ["old", "elderly", "grandmother", "grandfather"]},
       "build": {"slight": ["small frame", "slight", "thin", "slender"], "large": ["big", "large", "huge"], "sturdy": ["sturdy", "strong"]},
       "height_relative": {"short": ["small", "short", "tiny", "little"], "tall": ["tall", "giant", "big"], "very_short": ["tiny"]}}
def inferred_for_char(c, text):
    low = text.lower(); inferred = []
    named = any(w in low for w in words(c["name"]) + words(c["species"]))
    for f in ("species", "age_group", "build", "height_relative", "hair", "headwear", "eyewear", "face", "skin_colour", "outfit", "accessories", "distinguishing_marks"):
        v = c[f]
        if f in LEX:
            hit = any(k in low for k in LEX[f].get(v, []))
            if not (named and hit): inferred.append(f)
        elif f == "outfit":
            if not any(w in low for o in v for w in words(o["item"] + " " + o["colour"])): inferred.append(f)
        elif isinstance(v, str):
            if _none(v): continue
            if not any(w in low for w in words(v)): inferred.append(f)
    return inferred
def inferred_for_env(e, text):
    low = text.lower(); out = []
    for f in ("location", "time_of_day", "season", "lighting", "mood", "palette", "key_objects", "weather"):
        v = e[f]
        if isinstance(v, str):
            if _none(v) or v == "none": continue
            if not any(w in low for w in words(v)): out.append(f)
        elif v and not any(w in low for x in v for w in words(x)): out.append(f)
    return out
def mentioned(c, text):
    low = text.lower(); keys = set(words(c["name"]) + words(c["species"]))
    return any(k in low for k in keys)
PRONOUN = re.compile(r"\b(he|she|they|his|her|their|him|them)\b", re.I)

# ---------------------------------------------------------------- reflections are not characters
REFLECTION_WORDS = re.compile(r"\b(reflection|reflected|mirror image|mirrored)\b", re.I)
def _name_tokens(name):
    return {t for t in re.findall(r"[a-z]+", REFLECTION_WORDS.sub(" ", name.lower().replace("'s", " "))) if t not in STOP and t not in ("image", "of", "the")}
def reflection_owner(name, others):
    """If `name` names a reflection ("Reflection Dog", "Mirror Image of Isla", "Isla's Reflection"), the name of the original character among `others`
    (the one sharing the most name words; None when there is no overlap)."""
    if not REFLECTION_WORDS.search(name): return None
    mine = _name_tokens(name)
    scored = [(len(mine & _name_tokens(o)), len(o), o) for o in others if o != name and not REFLECTION_WORDS.search(o)]
    scored = [s for s in scored if s[0] > 0]
    return max(scored)[2] if scored else None
def fold_reflections(chars, pages):
    """Remove reflection characters from the cast and from every layout; remember them as page 'reflections' of their owner.
    A reflection with no recognisable owner is left alone (better a second figure than a lost one). Returns the names removed."""
    names = [c["name"] for c in chars]
    owner = {n: reflection_owner(n, [m for m in names if m != n]) for n in names}
    gone = {n for n, o in owner.items() if o}
    if not gone: return []
    for p in pages:
        refl = list(p.get("reflections", []))
        for l in p["layout"]:
            if l["character"] in gone and not any(r["of"] == owner[l["character"]] for r in refl):
                refl.append({"of": owner[l["character"]], "surface": "the water, mirror or glass in the scene"})
        p["layout"] = [l for l in p["layout"] if l["character"] not in gone]
        p["reflections"] = refl[:2]
    chars[:] = [c for c in chars if c["name"] not in gone]
    return sorted(gone)

# ---------------------------------------------------------------- the pipeline in three steps (the app asks the parent to approve characters between 'plan' and 'pages')
STEP_STAGES = {
    "plan": ["transcribe", "plan"],
    "assets": ["assets", "critic_assets", "ref_repair", "critic_refs"],
    "pages": ["render", "critic_pages_r0", "repair", "critic_pages_r1", "hints", "export", "review"],
}
STEP_STAGES["all"] = STEP_STAGES["plan"] + STEP_STAGES["assets"] + STEP_STAGES["pages"]
def stages_for(step):
    """Stage names run by `run_all.py --steps <step>`; unknown steps are an error, never 'everything'."""
    if step not in STEP_STAGES: raise ValueError(f"unknown step {step!r}; use one of {sorted(STEP_STAGES)}")
    return list(STEP_STAGES[step])
def draw_seed(base, attempt):
    """Seed for the n-th drawing of one character or place (attempt 0 = the first drawing); every attempt differs, deterministically."""
    return base + 7919 * attempt

def asset_files(filenames, name):
    """Which of these file names are the pictures of the character or place `name` (final reference, candidates c1.., pre-repair copy, plate).
    A name that is another name plus a suffix ('Bear' and 'Bear Cub') never matches the other's files; only a name ending in '_c<digits>' could collide."""
    s = re.escape(slug(name))
    pat = re.compile(rf"^(ref|plate)_{s}(_c\d+|_before_repair)?\.png$")
    return [f for f in filenames if pat.match(f)]

def delete_recordings(run_dir):
    """Delete the book's own recordings (audio.<ext> directly in the book folder) once a non-empty transcript exists. Returns the names deleted.
    Nothing else is touched, and nothing is deleted without a usable transcript."""
    t = os.path.join(run_dir, "transcript.json")
    try: ok = os.path.getsize(t) > 20 and bool(__import__("json").load(open(t)).get("text", "").strip())
    except (OSError, ValueError): ok = False
    if not ok: return []
    gone = []
    for f in sorted(os.listdir(run_dir)):
        p = os.path.join(run_dir, f)
        if re.fullmatch(r"audio\.(wav|mp3|m4a|flac|ogg)", f) and os.path.isfile(p) and not os.path.islink(p):
            os.remove(p); gone.append(f)
    return gone

# ---------------------------------------------------------------- is there a story at all?
MIN_STORY_WORDS = 6
STT_HALLUCINATIONS = {"thank you", "thanks", "thanks for watching", "thank you for watching", "you", "bye", "bye bye", "okay", "ok", "so", "oh", "um", "uh", "hmm", "yeah", "mm"}
def story_problem(text):
    """None when `text` can be a story; otherwise a plain-words reason. Speech models invent text from silence and noise ("Thank you.", "."), and a language
    model will happily write a whole book about it, so the pipeline stops before it spends minutes on nothing."""
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    if not tokens:
        return "I could not hear a story. Try again a little closer to the microphone, or type the story."
    sentences = [" ".join(re.findall(r"[a-z0-9']+", s.lower())) for s in re.split(r"[.!?]+", text) if re.search(r"[a-z0-9]", s, re.I)]
    if all(s in STT_HALLUCINATIONS for s in sentences):
        return "I only heard background noise, no story. Try again a little closer to the microphone, or type the story."
    if len(tokens) < MIN_STORY_WORDS:
        return f"That is too short for a picture book ({len(tokens)} word{'s' if len(tokens) != 1 else ''}). Tell a story of a few sentences."
    if len(set(tokens)) < 4:
        return "I heard the same few words over and over, not a story. Try again, or type the story."
    return None
