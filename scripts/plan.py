"""Stage 2: transcript.json -> plan.json. Several grammar-constrained Gemma calls (characters, environments, one per page) plus code-side rules.
usage: python3 plan.py <run_dir> [--seed N]"""
import json, sys, time
from common import Run, llama_server, chat, timed, require_ram
from schemas import Plan, AgeGroup, Build, Height, Pose, Expression, HairStyle
from typing import get_args
from rules import (fold_reflections, clean_text, setting_lines, limits_for_story, page_ranges, clean_layout, strip_carried, inferred_for_char, inferred_for_env, mentioned, PRONOUN, MAX_CHARS_PER_PAGE, DEFAULT_PAGES)

run = Run(sys.argv[1]); seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
N_PAGES = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else DEFAULT_PAGES
tr = run.load("transcript.json"); sents = tr["sentences"]
from rules import story_problem
if (why := story_problem(tr["text"])): sys.exit(why)            # defence in depth: never plan a book from nothing
LIM = limits_for_story(len(sents), N_PAGES)
require_ram(5)

# ---------------------------------------------------------------- JSON schemas (bounded strings, enums, no inferred_fields)
def S(n): return {"type": "string", "maxLength": n}
def arr(item, lo, hi): return {"type": "array", "minItems": lo, "maxItems": hi, "items": item}
def obj(props): return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
def enum(t): return {"enum": list(get_args(t))}
OUTFIT = obj({"item": S(30), "colour": S(30), "detail": S(60)})
CHAR = obj({"name": S(40), "species": S(30), "age_group": enum(AgeGroup), "build": enum(Build), "height_relative": enum(Height), "hair": S(60), "hair_style": enum(HairStyle), "headwear": S(60), "eyewear": S(60),
            "face": S(60), "skin_colour": S(40), "outfit": arr(OUTFIT, 1, 4), "accessories": S(60), "distinguishing_marks": S(60)})
ENV = obj({"name": S(40), "setting": {"enum": ["indoor", "outdoor"]}, "location": S(80), "time_of_day": {"enum": ["dawn", "morning", "noon", "afternoon", "evening", "night", "none"]},
           "weather": S(40), "season": {"enum": ["spring", "summer", "autumn", "winter", "none"]}, "lighting": S(60), "mood": S(40), "palette": arr(S(30), 2, 4), "key_objects": arr(S(40), 0, 6)})
def layout_item(names): return obj({"character": {"enum": names}, "pose": enum(Pose), "pose_detail": S(60), "placement": S(60), "expression": enum(Expression),
                                    "facing": {"enum": ["left", "right", "front", "back"]}, "position": {"enum": ["left", "center", "right"]}, "depth": {"enum": ["foreground", "mid", "background"]}})
def page_schema(envs, chars):
    return obj({"has_effects": {"type": "boolean"}, "scenario": S(240), "must_show": arr(S(120), 0, 2), "reflections": arr(obj({"of": {"enum": chars}, "surface": S(40)}), 0, 2), "effects": arr(S(80), 0, 3), "camera": {"enum": ["wide", "medium", "close-up"]},
                "environment": {"enum": envs}, "layout": arr(layout_item(chars), 0, MAX_CHARS_PER_PAGE + 2)})

RULES = ("Rules: use only facts from the story and do not invent plot. Where the story does not state a visual detail, INVENT a plausible concrete value "
         "(never 'None' for hair, skin_colour or clothing colours; 'None' is correct only for things a character plausibly does not have, such as glasses or a hat). "
         "build and height_relative describe the character's body as the story says (for example 'a small frame' means build slight and height short). Animals and creatures are characters too (species = the animal). "
         "If the story shows a group (for example 'the villagers') include one representative individual as a character. Answer only with JSON.")
story = "Story (numbered sentences):\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(sents, 1))
def ask(user, schema, name, sd, system=RULES, max_tokens=3000):
    c = chat(PORT, [{"role": "system", "content": system}, {"role": "user", "content": user}], schema, name, temperature=0.4, max_tokens=max_tokens, seed=sd)
    return json.loads(c["message"]["content"])

# code-side rules live in rules.py (story-independent, unit-tested)

with timed(run, "plan_total"), llama_server(run.p("llama_plan.log")) as PORT:
    # ---- call 1: title + characters
    t = time.time()
    r1 = ask(story + "\nTask: give the book a short title and list the characters of the story (at most " + str(LIM["max_chars"]) + "). A reflection, shadow or mirror image of a character is NOT a separate character: never list it. Include the main protagonist and ALSO one representative individual for every group of beings the story names (for example, for 'the villagers' add a character named 'Villager'; for 'the soldiers' add 'Soldier').", obj({"title": S(60), "characters": arr(CHAR, 1, LIM["max_chars"])}), "chars", seed)
    chars = r1["characters"]; names = [c["name"] for c in chars]
    run.log("plan_characters", time.time() - t, n=len(chars))
    # ---- call 2: environments
    t = time.time()
    r2 = ask(story + "\nCharacters: " + ", ".join(names) + "\nTask: list the PLACES where the story happens (at most " + str(LIM["max_places"]) + "). Give every different room or outdoor area its own place: a kitchen, a living room and a bedroom are three places even when they are in one house, and the forest is another; only merge places that would look the same. The 'location' field must be a concrete visual description of what the place looks like (walls, furniture, landscape, objects), never a label such as 'general' or 'a region'; invent a vivid, child-friendly look that fits the story. key_objects are fixed scenery only (buildings, trees, rocks, a boat, a bench, a table, beds), never things a character carries, holds or uses (a kite, a fishing rod, a net, a lantern, a stick). Describe each place as a wide establishing view with nothing in the foreground (an outdoor place seen from a distance; a room seen as a whole from inside), never a close-up of an object, and include in key_objects whatever the characters stand, sit, lie or ride on there (for example a small wooden boat on the lake, a bench, a bed, a path), so people can be placed in it without floating.", obj({"environments": arr(ENV, 1, LIM["max_places"])}), "envs", seed + 1)
    envs = r2["environments"]; env_names = [e["name"] for e in envs]
    strip_carried(envs, chars)   # carried things belong to the character, not the background plate (rules.py)
    run.log("plan_environments", time.time() - t, n=len(envs))
    # ---- page ranges chosen by code (rules.page_ranges): one sentence per page up to N_PAGES pages, otherwise grouped evenly
    ranges = page_ranges(len(sents), LIM["n_pages"])
    char_lines = "\n".join(f"- {c['name']}: {c['species']}, {c['age_group']}" for c in chars)
    pages = []
    for idx, (a, b) in enumerate(ranges, 1):
        text = " ".join(sents[a - 1:b])
        base = (f"{story}\nCharacters:\n{char_lines}\nSettings:\n{setting_lines(envs)}\nTask: describe page {idx}, which illustrates "
                f"{'sentence ' + str(a) if a == b else 'sentences ' + str(a) + '-' + str(b)}: \"{text}\". environment: choose the setting where THIS page's action happens (not where the story started). Put every character who is visible on this page into layout "
                "(use layout [] only for pages with nobody visible, such as a view of the land). placement: for each character say where exactly they are, naming something solid from the setting (for example 'standing on the grass', 'sitting inside the boat', 'on the bench'); never open water or empty sky unless they swim or fly. reflections: if the sentence shows a character's REFLECTION or mirror image (in water, a mirror or glass), list it here (of = the original character, surface = where it is seen); a reflection is never a character and never goes into layout. must_show: up to 2 short facts the picture MUST visibly show to tell this sentence (an event, a change, the state of an object; for example 'the kite string is broken and the kite flies away alone'); use [] when the sentence only describes. Set has_effects true only if the text describes magic, glowing light or similar visible effects; otherwise false and effects [].")
        t = time.time(); d = ask(base, page_schema(env_names, names), "page", seed + 10 + idx, max_tokens=1500)
        # rule: a page whose text mentions a character (or uses a pronoun with a protagonist) must show that character
        need = [c["name"] for c in chars if mentioned(c, text) and c["name"] not in [l["character"] for l in d["layout"]]]
        if not need and not d["layout"] and PRONOUN.search(text): need = [chars[0]["name"]]
        if need:
            d2 = ask(base + f"\nNote: this page must show {', '.join(need)} in layout.", page_schema(env_names, names), "page", seed + 50 + idx, max_tokens=1500)
            if len(d2["layout"]) >= len(d["layout"]): d = d2
        d["layout"] = clean_layout(d["layout"])   # each character once, at most MAX_CHARS_PER_PAGE (GPU memory)
        if not d["has_effects"]: d["effects"] = []
        effects = d["effects"]
        mode = "ref_compose" if (d["layout"] or effects) else "layered"      # code decides; 'layered' = empty plate in Phase 1
        pages.append({"index": idx, "first_sentence": a, "last_sentence": b, "story_text": text, "scenario": d["scenario"], "effects": effects, "must_show": d["must_show"], "reflections": d.get("reflections", []), "camera": d["camera"],
                      "environment": d["environment"], "render_mode": mode, "layout": d["layout"]})
        run.log(f"plan_page_{idx}", time.time() - t, layout=len(d["layout"]), effects=len(effects), mode=mode)

folded = fold_reflections(chars, pages); names = [c["name"] for c in chars]          # a reflection the model listed as a character becomes an effect (rules.py)
if folded: print("reflection characters folded into effects:", folded)
for c in chars: c["inferred_fields"] = inferred_for_char(c, tr["text"])
for e in envs: e["inferred_fields"] = inferred_for_env(e, tr["text"])
plan = Plan.model_validate(clean_text({"title": r1["title"], "characters": chars, "environments": envs, "pages": pages}))
dangling = [(p.index, p.environment) for p in plan.pages if p.environment not in env_names] + [(p.index, l.character) for p in plan.pages for l in p.layout if l.character not in names]
assert not dangling, dangling
run.save("plan.json", plan.model_dump())
print("title:", plan.title); print("characters:", names); print("environments:", env_names)
for p in plan.pages: print(f"page {p.index}: {p.render_mode:11s} layout={[l.character for l in p.layout]} effects={p.effects} | {p.scenario[:80]}")
