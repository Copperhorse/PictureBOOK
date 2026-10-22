"""Re-render the flagged pages with other seeds / prompt variants (same refs, same prompt composer as scripts/render.py).
usage: python3 gen.py <variant> <seeds comma list> [pages like arcania:3,mira:1,...]   variants: base | anatomy | steps8 | sequential"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from common import Run, page_instruction, require_ram
from klein import Klein
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
variant = sys.argv[1]; seeds = [int(s) for s in sys.argv[2].split(",")]
pages = [tuple(x.split(":")) for x in (sys.argv[3] if len(sys.argv) > 3 else "arcania:3,mira:1,mira:2,mira:4,fox:3,boat:2,boat:5").split(",")]
ANAT = " Each character has exactly two arms, two hands and two legs and appears exactly once in the picture."
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
def shrink(path, px):
    im = Image.open(path).convert("RGB"); return im if px >= im.width else im.resize((px, px), Image.LANCZOS)
require_ram(5); k = Klein(); out_dir = os.path.join(os.path.dirname(__file__), "out")
for run_name, n in pages:
    run = Run(os.path.join(ROOT, "runs", run_name)); plan = run.load("plan.json"); n = int(n)
    p = plan["pages"][n - 1]; chars = {c["name"]: c for c in plan["characters"]}; envs = {e["name"]: e for e in plan["environments"]}
    names = [l["character"] for l in p["layout"]]; plate = run.p("assets", f"plate_{slug(p['environment'])}.png")
    refs = [plate] + [run.p("assets", f"ref_{slug(m)}.png") for m in names]; px = {2: 1024, 3: 768}.get(len(refs), 512)
    instr = page_instruction(p, chars, envs[p["environment"]], names) + (ANAT if variant == "anatomy" else "")
    for s in seeds:
        out = os.path.join(out_dir, f"{run_name}_p{n}_{variant}_s{s}.png")
        if os.path.exists(out): continue
        if variant == "sequential" and len(names) > 1:   # one character reference per call: plate + first, then add the others
            img = k(page_instruction({**p, "layout": p["layout"][:1]}, chars, envs[p["environment"]], names[:1]), images=[shrink(refs[0], 1024), shrink(refs[1], 1024)], seed=s)
            for i in range(1, len(names)):
                l = p["layout"][i]
                img = k(f"Add {names[i]} (shown in the second image) to the first image: " + page_instruction({**p, "layout": [l]}, chars, envs[p["environment"]], [names[i]]).split("Image 2 is")[-1] + " Keep everything already in the first image unchanged.", images=[img, shrink(refs[i + 1], 1024)], seed=s)
        else:
            img = k(instr, images=[shrink(i, px) for i in refs], seed=s, steps=8 if variant == "steps8" else 4)
        img.save(out); print("saved", os.path.basename(out), flush=True)
