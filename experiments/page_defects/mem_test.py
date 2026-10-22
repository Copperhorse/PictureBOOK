"""Can one page render with the plate + N characters on the 8 GB card? Uses the Boat book's assets (4 characters). usage: python3 mem_test.py <n_characters> <pixels>"""
import os, sys, time, torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from common import Run, page_instruction
from rules import slug
from klein import Klein
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
n, px = int(sys.argv[1]), int(sys.argv[2])
run = Run(os.path.join(ROOT, "runs", "boat")); plan = run.load("plan.json"); chars = {c["name"]: c for c in plan["characters"]}; env = plan["environments"][0]
names = list(chars)[:n]; page = {"scenario": "Everyone is together.", "effects": [], "must_show": [], "layout": [{"character": m, "pose": "standing", "pose_detail": "none", "placement": "standing on the ground", "expression": "happy", "facing": "front", "position": "center", "depth": "mid"} for m in names]}
imgs = [Image.open(run.p("assets", f"plate_{slug(env['name'])}.png")).convert("RGB").resize((px, px))] + [Image.open(run.p("assets", f"ref_{slug(m)}.png")).convert("RGB").resize((px, px)) for m in names]
k = Klein(); torch.cuda.reset_peak_memory_stats(); t = time.time()
try:
    out = k(page_instruction(page, chars, env, names), images=imgs, seed=5); out.save(f"/tmp/claude-1000/-home-copper-Git-PictureBOOK/dd2ae928-9ea4-4881-b211-7f35342dc072/scratchpad/mem_{n}_{px}.png")
    print(f"OK  characters={n} images={len(imgs)} px={px}  peak_alloc={torch.cuda.max_memory_allocated()/2**30:.2f} GiB  time={time.time()-t:.0f}s")
except torch.OutOfMemoryError as e: print(f"OOM characters={n} images={len(imgs)} px={px}  peak_alloc={torch.cuda.max_memory_allocated()/2**30:.2f} GiB")
