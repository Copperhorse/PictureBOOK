"""Warning notes for the human reviewer (never an automatic action). Gemma 4 E4B, 1120 image tokens, thinking off.
Measured (docs/research/page-defects.md, 76 labelled images): second figure of a character 75% recall at 4% false alarms when the model must LIST every figure;
floating character about 85% at 15%; duplicate carried object 70% at 0%; missing event about 60% at 0%. Extra hands/legs are NOT detected (0 of 3): they are left to the human checklist."""
import json
from common import chat, image_part, _none
POS = ["far left", "left", "center-left", "center", "center-right", "right", "far right"]

def _figure_schema(names):
    fig = {"type": "object", "additionalProperties": False, "required": ["who", "position"], "properties": {"who": {"enum": list(names) + ["other"]}, "position": {"enum": POS}}}
    return {"type": "object", "additionalProperties": False, "required": ["figures"], "properties": {"figures": {"type": "array", "minItems": 0, "maxItems": 8, "items": fig}}}

def figure_hints(port, image, names):
    """List every separate person/animal drawn; more entries than characters (or one character twice) = a possible duplicate."""
    prompt = (f"Look at this picture carefully. Characters that may appear: {', '.join(names)}.\nfigures: list EVERY separate person or animal drawn in the picture, one entry per drawing "
              "(a head or body drawn apart from another figure is its own entry). Be literal: list only what is really drawn.")
    ch = chat(port, [{"role": "user", "content": [image_part(image), {"type": "text", "text": prompt}]}], _figure_schema(names), "figures", temperature=0.0, max_tokens=1200)
    figs = json.loads(ch["message"]["content"])["figures"]
    count = {}
    for f in figs: count[f["who"]] = count.get(f["who"], 0) + 1
    hints = []
    for n in names:
        if count.get(n, 0) > 1: hints.append(f"{n} may be drawn {count[n]} times")
    if count.get("other", 0): hints.append(f"{count['other']} extra figure(s) that are not in the plan")
    return hints

def held_objects(chars, names):
    """Names of the things the characters on this page carry (from their specs), for the duplicate-object count."""
    out = []
    for n in names:
        a = chars[n]["accessories"]
        if not _none(a) and a.lower() not in out: out.append(a.lower())
    return out

def scene_hints(port, image, page, chars):
    """Floating characters, duplicate carried objects, and whether the page's must_show facts are visible."""
    names = [l["character"] for l in page["layout"]]; objs = held_objects(chars, names); facts = page.get("must_show") or []
    props = {"floating": {"type": "object", "additionalProperties": False, "required": names, "properties": {n: {"type": "boolean"} for n in names}}} if names else {}
    if objs: props["object_counts"] = {"type": "object", "additionalProperties": False, "required": objs, "properties": {o: {"enum": [0, 1, 2, 3, 4]} for o in objs}}
    if facts: props["events"] = {"type": "object", "additionalProperties": False, "required": [f"event_{i}" for i in range(len(facts))], "properties": {f"event_{i}": {"type": "boolean"} for i in range(len(facts))}}
    if not props: return []
    schema = {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    q = ["Inspect this children's picture-book illustration and answer only with JSON."]
    if names: q.append("floating: for each character, true if they are NOT supported by ground, a boat, furniture or similar (and are not meant to fly), for example sitting on open water or hanging in the air.")
    if objs: q.append("object_counts: how many of each object are visible in the whole picture: " + ", ".join(objs) + ".")
    if facts: q.append("events: true only if the picture clearly shows it: " + " ".join(f"event_{i} = {f}" for i, f in enumerate(facts)))
    ch = chat(port, [{"role": "user", "content": [image_part(image), {"type": "text", "text": "\n".join(q)}]}], schema, "scene", temperature=0.0, max_tokens=800)
    a = json.loads(ch["message"]["content"]); hints = []
    for n, v in (a.get("floating") or {}).items():
        if v: hints.append(f"{n} may be floating (nothing to stand or sit on)")
    for o, c in (a.get("object_counts") or {}).items():
        if c >= 2: hints.append(f"{c} x {o} may be visible (expected 1)")
    for i, f in enumerate(facts):
        if not (a.get("events") or {}).get(f"event_{i}", True): hints.append(f"page may not show: {f}")
    return hints
