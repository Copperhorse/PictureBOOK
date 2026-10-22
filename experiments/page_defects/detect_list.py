"""Enumeration detector: the model must LIST every figure and every hand (one entry each, with owner and position); the count is len(list).
usage: python3 detect_list.py <manifest_v2.json> <out.jsonl> [--crops]"""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "..", "..", "scripts"))
from common import Run, llama_server, chat, image_part, require_ram, ROOT
from PIL import Image
if "--model" in sys.argv: os.environ["PB_VLM"] = sys.argv[sys.argv.index("--model") + 1]
CROPS = "--crops" in sys.argv; manifest = json.load(open(sys.argv[1])); out_path = sys.argv[2]
POS = ["far left", "left", "center-left", "center", "center-right", "right", "far right"]
def schema(names):
    fig = {"type": "object", "additionalProperties": False, "required": ["who", "position"], "properties": {"who": {"enum": names + ["other"]}, "position": {"enum": POS}}}
    hand = {"type": "object", "additionalProperties": False, "required": ["owner", "position", "holding"], "properties": {"owner": {"enum": names + ["other"]}, "position": {"enum": POS}, "holding": {"type": "string", "maxLength": 30}}}
    return {"type": "object", "additionalProperties": False, "required": ["figures", "hands"], "properties": {"figures": {"type": "array", "minItems": 0, "maxItems": 8, "items": fig}, "hands": {"type": "array", "minItems": 0, "maxItems": 10, "items": hand}}}
def prompt(names, crop):
    return (f"Look at this {'close-up' if crop else 'picture'} carefully. Characters that may appear: {', '.join(names)}.\n"
            "figures: list EVERY separate person or animal drawn in the picture, one entry per drawing (a head or body drawn apart from another figure is its own entry). "
            "hands: list EVERY human or animal hand you can see (not feet, not wings), one entry per hand, giving whose it is, where it is, and what it holds ('nothing' if empty). Be literal: list only what is really drawn.")
done = {(json.loads(l)["file"], json.loads(l).get("crop")) for l in open(out_path)} if os.path.exists(out_path) else set()
require_ram(5)
os.makedirs(os.path.join(H, "results"), exist_ok=True)
with llama_server(os.path.join(H, "results", "llama_detect.log")) as port, open(out_path, "a") as f:
    for m in manifest:
        if m["page"] == 0 or (m["file"], None) in done: continue
        plan = Run(os.path.join(ROOT, "runs", m["run"])).load("plan.json"); names = [l["character"] for l in plan["pages"][m["page"] - 1]["layout"]]
        msg = [{"role": "user", "content": [image_part(m["file"]), {"type": "text", "text": prompt(names, False)}]}]
        ch = chat(port, msg, schema(names), "list", temperature=0.0, max_tokens=1500)
        f.write(json.dumps({"file": m["file"], "crop": None, "answers": json.loads(ch["message"]["content"])}) + "\n"); f.flush(); print("done", os.path.basename(m["file"]), flush=True)
