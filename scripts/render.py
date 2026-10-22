"""Stage 5: pages.
usage: python3 render.py <run_dir> render [--pages 2,4] [--attempts 2:1,4:3]   -> pages/page_NN.png (ref_compose: plate + character references)
                                                                               --pages: only these pages; --attempts page:K: K-th redraw (new seed, see rules.page_seed)
       python3 render.py <run_dir> repair <checks.json>                       -> targeted edit on every page with a confident mismatch (one round)"""
import json, shutil, sys
from common import Run, timed, require_ram, page_instruction, repair_instruction
from rules import slug, ref_pixels, page_seed
run = Run(sys.argv[1]); mode = sys.argv[2]
def opt(name): return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None
only = {int(x) for x in opt("--pages").split(",")} if opt("--pages") else None
attempts = {int(a.split(":")[0]): int(a.split(":")[1]) for a in opt("--attempts").split(",")} if opt("--attempts") else {}
require_ram(5); plan = run.load("plan.json"); style = run.style
envs = {e["name"]: e for e in plan["environments"]}; chars = {c["name"]: c for c in plan["characters"]}
from klein import Klein
from PIL import Image
def shrink(path, px):
    im = Image.open(path).convert("RGB")
    return im if px >= im.width else im.resize((px, px), Image.LANCZOS)
k = Klein()
with timed(run, f"render_{mode}"):
    for p in plan["pages"]:
        n = p["index"]
        if only is not None and n not in only: continue
        out = run.p("pages", f"page_{n:02d}.png"); plate = run.p("assets", f"plate_{slug(p['environment'])}.png")
        if mode == "render":
            if not p["layout"] and not p["effects"]:
                shutil.copy(plate, out); continue
            names = [l["character"] for l in p["layout"]]
            refs = [plate] + [run.p("assets", f"ref_{slug(m)}.png") for m in names]
            px = ref_pixels(len(refs))   # more input pictures at 1024 px overflow the 8 GB card
            with timed(run, "page", page=n, refs=len(refs), ref_px=px, attempt=attempts.get(n, 0)):
                k(page_instruction(p, chars, envs[p["environment"]], names, style), images=[shrink(i, px) for i in refs], seed=page_seed(n, attempts.get(n, 0))).save(out)
        else:
            checks = json.load(open(sys.argv[3])).get(str(n), [])
            bad = [(e["character"], r) for e in checks for r in e["confident_mismatches"]]
            if not bad: continue
            shutil.copy(out, run.p("pages", f"page_{n:02d}_before_repair.png"))
            for who, r in bad[:2]:
                instr = repair_instruction(r["attribute"], r["observed"], r["expected"], f"the {who}")
                with timed(run, "repair", page=n, attribute=r["attribute"]):
                    k(instr, images=[out], seed=200 + n).save(out)
