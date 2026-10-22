"""Stage 3: plan.json -> environment plates and character reference candidates (klein).
usage: python3 assets.py <run_dir> [--style crayon] [--candidates 2] [--only "<character or place>"]
       --only draws just that one again, with new seeds each time (assets/draw_log.json counts the drawings); without it, existing pictures are kept."""
import json, os, re, shutil, sys, time
from common import Run, timed, require_ram, plate_prompt, character_prompt
from rules import draw_seed, asset_files
run = Run(sys.argv[1]); style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else run.style
n_cand = int(sys.argv[sys.argv.index("--candidates") + 1]) if "--candidates" in sys.argv else 2
require_ram(5)
plan = run.load("plan.json")
REPAIR = len(sys.argv) > 2 and sys.argv[2] == "repair"
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
if ONLY and ONLY not in [c["name"] for c in plan["characters"]] + [e["name"] for e in plan["environments"]]: sys.exit(f"no character or place named {ONLY!r} in the plan")
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
from klein import Klein
if REPAIR:  # targeted edit of a chosen reference that the critic confidently found wrong (checks/assets.json)
    from common import repair_instruction
    checks = run.load("checks/assets.json")
    from klein import Klein
    k = Klein()
    with timed(run, "reference_repair"):
        for c in plan["characters"]:
            if ONLY and c["name"] != ONLY: continue
            bad = checks.get(c["name"], {}).get("confident_mismatches", [])
            if not bad: continue
            ref = run.p("assets", f"ref_{slug(c['name'])}.png"); shutil.copy(ref, ref.replace(".png", "_before_repair.png"))
            for r in bad[:2]:
                with timed(run, "ref_repair", name=c["name"], attribute=r["attribute"]):
                    k(repair_instruction(r["attribute"], r["observed"], r["expected"]), images=[ref], seed=300).save(ref)
    sys.exit(0)
log_path = run.p("assets", "draw_log.json")
draws = json.load(open(log_path)) if os.path.exists(log_path) else {}
if ONLY:                                            # draw this one again: drop its old pictures, count the new drawing
    draws[ONLY] = draws.get(ONLY, 0) + 1
    for f in asset_files(os.listdir(run.p("assets")), ONLY): os.remove(run.p("assets", f))
with timed(run, "assets_total", style=style):
    t = time.time(); k = Klein(); run.log("klein_load", time.time() - t)
    for e in plan["environments"]:
        if ONLY and e["name"] != ONLY: continue
        out = run.p("assets", f"plate_{slug(e['name'])}.png")
        if not os.path.exists(out):
            with timed(run, "plate", name=e["name"]): k(plate_prompt(e, style), seed=draw_seed(1, draws.get(e["name"], 0))).save(out)
    for c in plan["characters"]:
        if ONLY and c["name"] != ONLY: continue
        for i in range(1, n_cand + 1):
            out = run.p("assets", f"ref_{slug(c['name'])}_c{i}.png")
            if not os.path.exists(out):
                with timed(run, "character_candidate", name=c["name"], candidate=i): k(character_prompt(c, style), seed=draw_seed(i, draws.get(c["name"], 0))).save(out)
json.dump(draws, open(log_path, "w"))
