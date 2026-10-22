"""Gemma 4 E4B sanity detector (v2). One constrained call per page (+ optionally one per character on a zoomed crop).
Answers are enums so the probability of the chosen value can be read from the logprobs (renormalised over the grammar-allowed tokens).
usage: python3 detect.py <manifest.json> <out.jsonl> [--think] [--crops]
manifest items: {"file", "run", "page" (0 = a character reference image), "only": character name (refs), "objects": [...], "must_show": [...]}"""
import json, math, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "..", "..", "scripts"))
from common import Run, llama_server, chat, image_part, require_ram, ROOT
from critic import who
from PIL import Image
if "--model" in sys.argv: os.environ["PB_VLM"] = sys.argv[sys.argv.index("--model") + 1]
THINK = "--think" in sys.argv; CROPS = "--crops" in sys.argv; manifest = json.load(open(sys.argv[1])); out_path = sys.argv[2]
STYLES = ["short", "medium", "long", "bun", "ponytail", "braids", "curly", "bald", "covered", "fur_or_none"]
def char_schema(with_style=True):
    p = {"evidence": {"type": "string", "maxLength": 160}, "figures": {"enum": [0, 1, 2, 3, 4]}, "hands": {"enum": list(range(7))}, "legs": {"enum": list(range(7))}, "floating": {"type": "boolean"}, "hair_style": {"enum": STYLES}}
    return {"type": "object", "additionalProperties": False, "required": list(p), "properties": p}
def schema(names, objects, facts):
    props = {"characters": {"type": "object", "additionalProperties": False, "required": names, "properties": {n: char_schema() for n in names}}}
    if objects: props["objects"] = {"type": "object", "additionalProperties": False, "required": objects, "properties": {o: {"enum": [0, 1, 2, 3, 4]} for o in objects}}
    if facts: props["events"] = {"type": "object", "additionalProperties": False, "required": [f"event_{i}" for i in range(len(facts))], "properties": {f"event_{i}": {"type": "boolean"} for i in range(len(facts))}}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
SYSTEM = ("You are a careful inspector of children's picture-book illustrations. Look closely and COUNT what is really drawn; do not assume the picture is correct. "
          "For each character, write short 'evidence' (what arms, hands and legs you can see) BEFORE giving numbers. Answer only with JSON.")
def prompt(chars, objects, facts, crop=False):
    L = ["Inspect this " + ("close-up of one character" if crop else "picture") + ". Characters:"] + [f"- {n}: {who(c)}" for n, c in chars.items()]
    L.append("For every character give: figures = how many separate drawings of this character are in the picture (a second copy, or a head or body drawn separately, counts); hands = how many hands of this character are visible; "
             "legs = how many legs or feet of this character are visible; floating = true if the character is not supported by ground, a boat, furniture or similar (and is not meant to fly); hair_style = the hair style you see (fur_or_none for animals).")
    if objects: L.append("objects: for each named object, how many of them are visible in the whole picture: " + ", ".join(objects) + ".")
    if facts: L.append("events: for each event, true only if the picture clearly shows it: " + " ".join(f"event_{i} = {f}" for i, f in enumerate(facts)))
    return "\n".join(L)
def value_dist(choice, key):
    """Distribution at the VALUE token of the first occurrence of `"key": <value>` in order of appearance; returns list over occurrences."""
    toks = (choice.get("logprobs") or {}).get("content") or []; out = []; run = ""
    i = 0
    while i < len(toks):
        run += toks[i]["token"]
        if run.rstrip().endswith(f'"{key}":'):
            j = i + 1
            while j < len(toks) and not toks[j]["token"].strip(): j += 1
            if j < len(toks):
                alts = {}
                for x in toks[j].get("top_logprobs", []) + [{"token": toks[j]["token"], "logprob": toks[j]["logprob"]}]:
                    k = x["token"].strip(); alts[k] = max(alts.get(k, 0), math.exp(x["logprob"]))
                tot = sum(alts.values()); out.append({k: v / tot for k, v in alts.items()})
        i += 1
    return out
def crop_for(path, position, out):
    im = Image.open(path).convert("RGB"); w, h = im.size
    a, b = {"left": (0, .6), "center": (.2, .8), "right": (.4, 1)}[position]
    im.crop((int(a * w), 0, int(b * w), h)).save(out); return out
os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True); os.makedirs(os.path.join(H, "crops"), exist_ok=True)
done = {(json.loads(l)["file"], json.loads(l).get("crop")) for l in open(out_path)} if os.path.exists(out_path) else set()
require_ram(5)
def ask(port, image, cs, objects, facts, crop=False):
    sc = schema(list(cs), objects, facts)
    msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [image_part(image), {"type": "text", "text": prompt(cs, objects, facts, crop)}]}]
    ch = chat(port, msg, sc, "sanity", temperature=0.0, max_tokens=8192 if THINK else 1500, think=THINK, logprobs=True)
    content = ch["message"]["content"]; ans = json.loads(content)
    return {"answers": ans, "dists": {k: value_dist(ch, k) for k in ("figures", "hands", "legs", "floating", "hair_style")}, "finish": ch.get("finish_reason")}
with llama_server(os.path.join(H, "results", "llama_detect.log")) as port, open(out_path, "a") as f:
    for m in manifest:
        plan = Run(os.path.join(ROOT, "runs", m["run"])).load("plan.json"); chars = {c["name"]: c for c in plan["characters"]}
        if m["page"] == 0: cs = {m["only"]: chars[m["only"]]}; pos = {m["only"]: "center"}
        else:
            lay = plan["pages"][m["page"] - 1]["layout"]; cs = {l["character"]: chars[l["character"]] for l in lay}; pos = {l["character"]: l["position"] for l in lay}
        if (m["file"], None) not in done:
            r = ask(port, m["file"], cs, m.get("objects", []), m.get("must_show", [])); f.write(json.dumps({"file": m["file"], "crop": None, **r}) + "\n"); f.flush()
        if CROPS and m["page"] != 0:
            for n in cs:
                if (m["file"], n) in done: continue
                cp = crop_for(m["file"], pos[n], os.path.join(H, "crops", re.sub(r"\W+", "_", os.path.relpath(m["file"], ROOT)) + f"_{re.sub(chr(32), '', n)}.png"))
                r = ask(port, cp, {n: cs[n]}, [], [], crop=True); f.write(json.dumps({"file": m["file"], "crop": n, **r}) + "\n"); f.flush()
        print("done", os.path.basename(m["file"]), flush=True)
