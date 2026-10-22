"""Redraw pages the human found wrong (new seed each time; the old picture is kept).
usage: python3 regen.py <run_dir> 2,4          redraw pages 2 and 4
       python3 regen.py <run_dir> --undo 2     put the previous picture of page 2 back
Works from plan.json and the assets only, so it is independent of the story."""
import os, shutil, subprocess, sys, time
from common import Run, capped, pb_event, die_with_parent
die_with_parent()
HERE = os.path.dirname(os.path.abspath(__file__))
run = Run(sys.argv[1]); plan = run.load("plan.json"); valid = {p["index"] for p in plan["pages"]}
log = run.load("regen_log.json") if os.path.exists(run.p("regen_log.json")) else {}
def page(n): return run.p("pages", f"page_{n:02d}.png")
def stage(script, *args, name=None, fatal=True):
    name = name or script.split(".")[0]
    pb_event(stage=name, state="start")
    r = subprocess.run(capped([sys.executable, os.path.join(HERE, script), run.dir, *args]))
    if r.returncode:
        pb_event(stage=name, state="failed", code=r.returncode)
        if fatal: sys.exit(f"{script} failed (exit {r.returncode}); nothing was changed in regen_log.json")
        print(f"{script} failed (exit {r.returncode}); continuing without it", flush=True)
    pb_event(stage=name, state="done")
def finish():
    run.save("regen_log.json", log); stage("export.py"); stage_nocap("review.py")
def stage_nocap(script): subprocess.run([sys.executable, os.path.join(HERE, script), run.dir], check=True)

if len(sys.argv) > 2 and sys.argv[2] == "--undo":
    n = int(sys.argv[3]); e = log.get(str(n))
    if n not in valid or not e or not e["archive"]: sys.exit(f"page {n} has no earlier picture to go back to")
    prev = e["archive"].pop(); shutil.move(page(n), run.p("pages", f"page_{n:02d}_discarded_a{e['attempt']}.png")); shutil.move(run.p("pages", prev), page(n))
    print(f"page {n}: previous picture restored (attempt counter stays {e['attempt']}, so the next redraw uses a new seed)"); finish(); sys.exit(0)

try: want = sorted({int(x) for x in sys.argv[2].split(",")})
except (IndexError, ValueError): sys.exit("usage: regen.py <run_dir> 2,4   or   regen.py <run_dir> --undo 2")
bad = [n for n in want if n not in valid]
if bad: sys.exit(f"no such page: {bad}; this book has pages {sorted(valid)}")
t = time.time(); backup = {}
for n in want:                                     # keep the current picture as the next archived version
    e = log.setdefault(str(n), {"attempt": 0, "archive": []}); name = f"page_{n:02d}_v{len(e['archive']) + 1}.png"
    shutil.copy(page(n), run.p("pages", name)); backup[n] = name
attempts = ",".join(f"{n}:{log[str(n)]['attempt'] + 1}" for n in want)
try: stage("render.py", "render", "--pages", ",".join(map(str, want)), "--attempts", attempts)
except SystemExit:
    for n, name in backup.items(): shutil.move(run.p("pages", name), page(n))   # a failed render must not lose the picture
    raise
for n in want: log[str(n)]["archive"].append(backup[n]); log[str(n)]["attempt"] += 1
stage("critic.py", "hints", "--pages", ",".join(map(str, want)), name="hints", fatal=False)     # notes for the NEW pictures (a failure here never loses the redraw)
print(f"redrew pages {want} in {time.time() - t:.0f} s; older pictures kept as {[backup[n] for n in want]}")
finish()
# before/after pair per page at 900 px each, so small mistakes (a third leg, a bear ear) are visible; judge the new picture at THIS size, not on the thumbnail sheet
from PIL import Image
os.makedirs(run.p("compare"), exist_ok=True)
for n in want:
    a, b = Image.open(run.p("pages", backup[n])).convert("RGB").resize((900, 900)), Image.open(page(n)).convert("RGB").resize((900, 900))
    s = Image.new("RGB", (1800, 900), "white"); s.paste(a, (0, 0)); s.paste(b, (900, 0)); s.save(run.p("compare", f"page_{n:02d}_attempt{log[str(n)]['attempt']}.png"))
print("before/after pictures for checking:", run.p("compare"))
