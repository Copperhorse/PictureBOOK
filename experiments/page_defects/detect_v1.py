"""Gemma 4 E4B sanity detector on rendered pages: counts figures, hands, legs per character; floating; held-object counts; must_show events; hair style.
One constrained call per page (fixed keys per character so every field can be located in the logprobs).
usage: python3 detect.py <manifest.json> <out.jsonl> [--think] [--tokens 1120]
manifest: [{"file": path, "run": "mira", "page": 4, "objects": ["fishing rod"], "must_show": ["..."]}, ...]"""
import json, math, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from common import Run, llama_server, chat, image_part, require_ram, ROOT
from critic import who
THINK = "--think" in sys.argv; manifest = json.load(open(sys.argv[1])); out_path = sys.argv[2]
NUM = list(range(0, 7))
def char_schema():
    return {"type": "object", "additionalProperties": False, "required": ["evidence", "figures", "hands", "legs", "floating", "hair_style", "hair_style_matches"], "properties": {
        "evidence": {"type": "string", "maxLength": 160}, "figures": {"enum": [0, 1, 2, 3, 4]}, "hands": {"enum": NUM}, "legs": {"enum": NUM}, "floating": {"type": "boolean"},
        "hair_style": {"type": "string", "maxLength": 40}, "hair_style_matches": {"type": "boolean"}}}
def schema(names, objects, facts):
    props = {"characters": {"type": "object", "additionalProperties": False, "required": names, "properties": {n: char_schema() for n in names}}}
    if objects: props["objects"] = {"type": "object", "additionalProperties": False, "required": objects, "properties": {o: {"enum": [0, 1, 2, 3, 4]} for o in objects}}
    if facts: props["events"] = {"type": "object", "additionalProperties": False, "required": [f"event_{i}" for i in range(len(facts))], "properties": {f"event_{i}": {"type": "boolean"} for i in range(len(facts))}}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
SYSTEM = ("You are a careful inspector of children's picture-book illustrations. Look closely and COUNT what is really drawn; do not assume the picture is correct. "
          "For each character, write short 'evidence' (what arms, hands and legs you can see) BEFORE giving numbers. Answer only with JSON.")
def prompt(chars, hair, objects, facts):
    L = ["Inspect this picture. Characters:"]
    for n, c in chars.items(): L.append(f"- {n}: {who(c)}; expected hair: {hair[n]}")
    L.append("For every character give: figures = how many separate drawings of this character are in the picture (a second copy, or a head or body drawn separately, counts); hands = how many hands of this character are visible; "
             "legs = how many legs or feet of this character are visible; floating = true if the character is not supported by ground, a boat, furniture or similar (and is not meant to fly); hair_style = the hair style you see (a few words); hair_style_matches = true if it fits the expected hair.")
    if objects: L.append("objects: for each named object, how many of them are visible in the whole picture: " + ", ".join(objects) + ".")
    if facts: L.append("events: for each event, true only if the picture clearly shows it: " + " ".join(f"event_{i} = {f}" for i, f in enumerate(facts)))
    return "\n".join(L)
def locate(content, choice, key_regex):
    """Probability of the value chosen for a JSON field, renormalised over the tokens the grammar allowed (top_logprobs at that token)."""
    toks = (choice.get("logprobs") or {}).get("content") or []
    pos = 0; spans = []
    for t in toks: spans.append((pos, pos + len(t["token"]))); pos += len(t["token"])
    out = []
    for m in re.finditer(key_regex, content):
        s = m.start(1)
        for t, (a, b) in zip(toks, spans):
            if a <= s < b:
                alts = {}
                for x in t.get("top_logprobs", []) + [{"token": t["token"], "logprob": t["logprob"]}]:
                    k = x["token"].strip(); alts[k] = max(alts.get(k, 0), math.exp(x["logprob"]))
                out.append({"token": t["token"].strip(), "dist": alts}); break
    return out
os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
done = {json.loads(l)["file"] for l in open(out_path)} if os.path.exists(out_path) else set()
require_ram(5)
class P:  # llama_server wants a log path only
    pass
with llama_server(os.path.join(os.path.dirname(os.path.abspath(out_path)), "llama_detect.log")) as port, open(out_path, "a") as f:
    for m in manifest:
        if m["file"] in done: continue
        plan = Run(os.path.join(ROOT, "runs", m["run"])).load("plan.json"); page = plan["pages"][m["page"] - 1]
        chars = {c["name"]: c for c in plan["characters"]}; layout = [l["character"] for l in page["layout"]]
        cs = {n: chars[n] for n in layout}; hair = {n: ("none (bald)" if cs[n]["hair"].lower() in ("none", "") else cs[n]["hair"]) for n in layout}
        sc = schema(layout, m.get("objects", []), m.get("must_show", []))
        msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [image_part(m["file"]), {"type": "text", "text": prompt(cs, hair, m.get("objects", []), m.get("must_show", []))}]}]
        ch = chat(port, msg, sc, "sanity", temperature=0.0, max_tokens=8192 if THINK else 1500, think=THINK, logprobs=True)
        content = ch["message"]["content"]; ans = json.loads(content)
        conf = {k: locate(content, ch, rf'"{k}":\s*([0-9a-z]+)') for k in ("figures", "hands", "legs", "floating")}
        f.write(json.dumps({"file": m["file"], "answers": ans, "dists": conf, "finish": ch.get("finish_reason")}) + "\n"); f.flush(); print("done", os.path.basename(m["file"]), flush=True)
