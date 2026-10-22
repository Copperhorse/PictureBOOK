"""Planner test: one full-plan call vs several calls, thinking on/off. usage:
planner_test.py --port 18080 --tag e2b_planner --conds single_off,single_on,multi_off,multi_on --repeats 3
Server must run with --reasoning-budget N (thinking on = default; off = chat_template_kwargs.enable_thinking=false)."""
import argparse, json, os, re, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
STORIES = {
 "arcania": ["Once upon a time in a land not like ours, used to be the kingdom of mages.",
             "The mages were people capable of bending the laws of nature to their will.",
             "And the most talented mage of them all in Arcania was the seventh prince.",
             "He was a timid boy with a small frame and stature, but his mind was like no other, capable of understanding complex structures in mere seconds and display his prowess with a small wooden stick.",
             "He was the pride of the kingdom."],
 "red_hood": ["A little girl in a red hood walked through the forest to visit her grandmother.",
              "A big grey wolf stepped out from behind a tree and asked where she was going.",
              "She told him about her grandmother's cottage on the other side of the hill.",
              "The wolf ran ahead, climbed into grandmother's bed and put on her nightcap.",
              "When the girl opened the door, a woodcutter with a shining axe came in and chased the wolf away."],
 "fox_lantern": ["On a dark night, a young fox found a glowing lantern under an old oak tree.",
                 "She carried it carefully through the meadow to the village where a sleepy owl lived.",
                 "The owl blinked, yawned, and hung the lantern on the church tower.",
                 "Its magic light spread across the roofs and made the whole village glow like silver.",
                 "Everyone woke up to watch the stars together."]}
# facts the story states explicitly; each is checked with a predicate on the final plan
FACTS = {
 "arcania": [("prince build slight", lambda p: any(c["build"] == "slight" for c in p["characters"])),
             ("prince height short/very_short", lambda p: any(c["height_relative"] in ("short", "very_short") for c in p["characters"])),
             ("wooden stick mentioned in a character", lambda p: any("stick" in json.dumps(c).lower() for c in p["characters"])),
             ("prince age_group child/teen", lambda p: any(c["age_group"] in ("child", "teen") for c in p["characters"]))],
 "red_hood": [("red hood in a character", lambda p: any("red" in json.dumps(c).lower() and "hood" in json.dumps(c).lower() for c in p["characters"])),
              ("wolf character with species wolf", lambda p: any("wolf" in c["species"].lower() for c in p["characters"])),
              ("grey wolf colour", lambda p: any("wolf" in c["species"].lower() and ("gr" in (c["skin_colour"] + c["hair"]).lower()) for c in p["characters"])),
              ("woodcutter character", lambda p: any("wood" in (c["name"] + c["species"]).lower() or "axe" in json.dumps(c).lower() for c in p["characters"]))],
 "fox_lantern": [("fox character", lambda p: any("fox" in c["species"].lower() for c in p["characters"])),
                 ("owl character", lambda p: any("owl" in c["species"].lower() for c in p["characters"])),
                 ("night time environment", lambda p: any(e["time_of_day"] == "night" for e in p["environments"])),
                 ("lantern as key object or effect somewhere", lambda p: "lantern" in json.dumps(p).lower())]}
AGE = ["infant", "child", "teen", "adult", "elderly", "none"]; BUILD = ["slight", "average", "sturdy", "large"]
HEIGHT = ["very_short", "short", "average", "tall"]; POSE = ["standing", "walking", "running", "sitting", "jumping", "waving", "pointing", "sleeping", "holding_item", "hugging", "other"]
EXPR = ["happy", "sad", "surprised", "scared", "angry", "curious", "sleepy", "neutral", "shy", "proud", "determined", "embarrassed"]
def S(n): return {"type": "string", "maxLength": n}
def arr(item, lo, hi): return {"type": "array", "minItems": lo, "maxItems": hi, "items": item}
def obj(props): return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
OUTFIT = obj({"item": S(30), "colour": S(30), "detail": S(60)})
CHAR = obj({"name": S(40), "species": S(30), "age_group": {"enum": AGE}, "build": {"enum": BUILD}, "height_relative": {"enum": HEIGHT},
            "hair": S(60), "headwear": S(60), "eyewear": S(60), "face": S(60), "skin_colour": S(40), "outfit": arr(OUTFIT, 1, 4),
            "accessories": S(60), "distinguishing_marks": S(60)})
ENV = obj({"name": S(40), "setting": {"enum": ["indoor", "outdoor"]}, "location": S(80),
           "time_of_day": {"enum": ["dawn", "morning", "noon", "afternoon", "evening", "night", "none"]}, "weather": S(40),
           "season": {"enum": ["spring", "summer", "autumn", "winter", "none"]}, "lighting": S(60), "mood": S(40),
           "palette": arr(S(30), 2, 4), "key_objects": arr(S(40), 0, 6)})
def layout_item(names): return obj({"character": {"enum": names} if names else S(40), "pose": {"enum": POSE}, "pose_detail": S(60), "expression": {"enum": EXPR},
            "facing": {"enum": ["left", "right", "front", "back"]}, "position": {"enum": ["left", "center", "right"]}, "depth": {"enum": ["foreground", "mid", "background"]}})
def page_props(envs=None, chars=None, ranged=False):
    p = {}
    if ranged: p.update({"first_sentence": {"type": "integer", "minimum": 1, "maximum": 6}, "last_sentence": {"type": "integer", "minimum": 1, "maximum": 6}})
    p.update({"scenario": S(240), "effects": arr(S(80), 0, 3), "camera": {"enum": ["wide", "medium", "close-up"]},
              "environment": {"enum": envs} if envs else S(40), "render_mode": {"enum": ["layered", "ref_compose", "composite_refine", "full_scene"]},
              "layout": arr(layout_item(chars), 0, 4)})
    return p
RULES = ("Rules: use only facts from the story; where the story does not state a visual detail, INVENT a plausible concrete value "
         "(never 'None' for hair, skin_colour or clothing colours; 'None' is correct only for things a character plausibly does not have, such as glasses or a hat). "
         "Animals and creatures are characters too (species = the animal). Every character that appears on a page must be listed in that page's layout; use layout [] only for pages without any character. "
         "'effects' lists magic or light effects that are neither characters nor setting. A page with effects must not use render_mode 'layered'. "
         "scenario is one or two concrete sentences about what is visible. Answer only with JSON.")
def story_text(sents): return "\n".join(f"{i}. {s}" for i, s in enumerate(sents, 1))

def post(port, body, timeout=1200):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer critic-test-key"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=timeout)); return r, time.time() - t

def llm(port, think, system, user, schema, name, max_tokens, seed):
    body = {"model": "x", "temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": seed, "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if think == "off": body["chat_template_kwargs"] = {"enable_thinking": False}
    r, dt = post(port, body); c = r["choices"][0]; m = c["message"]
    meta = {"latency": dt, "finish": c["finish_reason"], "completion_tokens": r["usage"]["completion_tokens"], "prompt_tokens": r["usage"]["prompt_tokens"],
            "reasoning_chars": len(m.get("reasoning_content") or "")}
    try: data = json.loads(m.get("content") or "")
    except Exception: data = None
    return data, meta

def run_single(port, think, sents, seed):
    schema = obj({"title": S(60), "characters": arr(CHAR, 1, 4), "environments": arr(ENV, 1, 3),
                  "pages": arr(obj(page_props(ranged=True)), len(sents), len(sents))})
    system = ("You plan a children's picture book from a spoken story, in ONE JSON object: title, characters, environments, pages. "
              f"Make exactly {len(sents)} pages. Each page covers a range of numbered sentences (first_sentence..last_sentence); pages are in order and together cover every sentence exactly once. " + RULES +
              " Every page.environment must be the exact name of one of the environments you define; every layout.character must be the exact name of one of the characters you define.")
    data, meta = llm(port, think, system, "Story (numbered sentences):\n" + story_text(sents), schema, "plan", 8192, seed)
    return data, [meta]

def run_multi(port, think, sents, seed):
    metas = []; stx = "Story (numbered sentences):\n" + story_text(sents)
    sysb = "You plan a children's picture book from a spoken story. " + RULES
    d1, m1 = llm(port, think, sysb + " Task: list the characters of the story (at most 4).", stx, obj({"characters": arr(CHAR, 1, 4)}), "chars", 4096, seed); metas.append(m1)
    if not d1: return None, metas
    names = [c["name"] for c in d1["characters"]]
    d2, m2 = llm(port, think, sysb + " Task: list the distinct settings (at most 3) where the story takes place.", stx + "\nCharacters: " + ", ".join(names), obj({"environments": arr(ENV, 1, 3)}), "envs", 4096, seed); metas.append(m2)
    if not d2: return None, metas
    envs = [e["name"] for e in d2["environments"]]; pages = []
    for i, s in enumerate(sents, 1):
        ctx = stx + f"\nCharacters: {', '.join(names)}\nSettings: {', '.join(envs)}\nTask: describe page {i}, which illustrates exactly sentence {i}: \"{s}\""
        d3, m3 = llm(port, think, sysb, ctx, obj(page_props(envs, names)), "page", 3072, seed + i); metas.append(m3)
        if not d3: return None, metas
        d3 = {"first_sentence": i, "last_sentence": i, **d3}; pages.append(d3)
    return {"title": "", "characters": d1["characters"], "environments": d2["environments"], "pages": pages}, metas

def check(plan, story_key, sents):
    v = {}
    if not plan: return {"parse_ok": False}
    names = {c["name"] for c in plan["characters"]}; envs = {e["name"] for e in plan["environments"]}
    v["parse_ok"] = True; v["pages"] = len(plan["pages"])
    v["dangling_env"] = sum(p["environment"] not in envs for p in plan["pages"])
    v["dangling_char"] = sum(l["character"] not in names for p in plan["pages"] for l in p["layout"])
    v["effects_layered"] = sum(bool(p["effects"]) and p["render_mode"] == "layered" for p in plan["pages"])
    # characters named (first word or full name, or species) in the sentences of the page but missing in layout
    miss = 0
    for p in plan["pages"]:
        txt = " ".join(sents[p["first_sentence"] - 1:p["last_sentence"]]).lower() if 1 <= p["first_sentence"] <= p["last_sentence"] <= len(sents) else ""
        inl = {l["character"] for l in p["layout"]}
        for c in plan["characters"]:
            keys = {c["name"].lower(), c["species"].lower()} | {w for w in c["name"].lower().split() if len(w) > 3}
            if any(k and k in txt for k in keys) and c["name"] not in inl: miss += 1
    v["char_missing_from_layout"] = miss
    v["empty_layout_pages"] = sum(len(p["layout"]) == 0 for p in plan["pages"])
    # sentence coverage
    cov = []; ok = True; prev = 0
    for p in plan["pages"]:
        a, b = p["first_sentence"], p["last_sentence"]
        if a != prev + 1 or b < a: ok = False
        prev = b
    v["ranges_ok"] = ok and prev == len(sents)
    v["none_misuse"] = sum(c["hair"].strip().lower() == "none" or c["skin_colour"].strip().lower() == "none" for c in plan["characters"]) + \
                       sum(o["colour"].strip().lower() == "none" for c in plan["characters"] for o in c["outfit"])
    facts = FACTS[story_key]; v["facts"] = {n: bool(f(plan)) for n, f in facts}
    return v

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--conds", default="single_off,single_on,multi_off,multi_on"); ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--stories", default="arcania,red_hood,fox_lantern"); a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = open(os.path.join(HERE, "results", f"{a.tag}.jsonl"), "w"); t0 = time.time()
    for rep in range(a.repeats):
        for sk in a.stories.split(","):
            sents = STORIES[sk]
            for cond in a.conds.split(","):
                shape, think = cond.split("_")
                seed = 1000 + rep * 17
                try:
                    plan, metas = (run_single if shape == "single" else run_multi)(a.port, think, sents, seed)
                    res = check(plan, sk, sents)
                except Exception as e:
                    plan, metas, res = None, [], {"parse_ok": False, "error": repr(e)[:200]}
                rec = {"story": sk, "cond": cond, "rep": rep, "metas": metas, "total_latency": sum(m["latency"] for m in metas), "check": res, "plan": plan}
                out.write(json.dumps(rec) + "\n"); out.flush()
                print(f"{time.time()-t0:5.0f}s {sk:11s} {cond:11s} rep{rep} latency {rec['total_latency']:.0f}s parse_ok={res.get('parse_ok')} dangling_env={res.get('dangling_env')} dangling_char={res.get('dangling_char')} eff_layered={res.get('effects_layered')} miss_layout={res.get('char_missing_from_layout')}", flush=True)
