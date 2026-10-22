"""Whole pipeline, one command: audio (or a typed story as .txt) -> book.pdf. Every GPU stage is its own process under a memory-capped systemd scope (one model at a time).
usage: python3 scripts/run_all.py <audio.wav | story.txt> <run_dir> [--style crayon|flat|watercolour] [--pages N] [--steps plan|assets|pages|all] [--only "<character or place>"] [--keep-audio]   (N pages, default 6; up to 10 for a long story)"""
import json, os, signal, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
audio, rd = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else "crayon"
os.makedirs(rd, exist_ok=True)
from common import capped, pb_event, die_with_parent
die_with_parent()
def _terminate(*_):                                  # the sidecar asked us to stop: take the whole process group down (stage, llama serve ...)
    signal.signal(signal.SIGTERM, signal.SIG_IGN); os.killpg(0, signal.SIGTERM); sys.exit(143)
signal.signal(signal.SIGTERM, _terminate)
TEXT_INPUT = audio.lower().endswith(".txt")
n_pages = sys.argv[sys.argv.index("--pages") + 1] if "--pages" in sys.argv else None
json.dump({"style": style, "pages": n_pages}, open(os.path.join(rd, "config.json"), "w"))   # every stage (and regen.py) reads the style from here
def opt(name): return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None
from rules import stages_for
STEPS = opt("--steps") or "all"
ONLY = opt("--only")                          # redraw one character or place only (assets step)
WANTED = set(stages_for(STEPS))
RESUME = "--resume-from-critic" in sys.argv   # skip stages up to and including the page render; reuse the existing run directory
SKIPPED = {"transcribe", "plan", "assets", "critic_assets", "ref_repair", "critic_refs", "render"} if RESUME else set()
def stage(name, *args):
    if name in SKIPPED or name not in WANTED: return 0.0
    t = time.time(); pb_event(stage=name, state="start")
    r = subprocess.run(capped([sys.executable, os.path.join(HERE, args[0])] + list(args[1:])))
    if r.returncode: pb_event(stage=name, state="failed", code=r.returncode); sys.exit(f"stage {name} failed (exit {r.returncode})")
    pb_event(stage=name, state="done", seconds=round(time.time() - t, 1)); return time.time() - t
t0 = time.time(); wall = {}
if RESUME and os.path.exists(os.path.join(rd, "wall_times.json")): wall = {k: v for k, v in json.load(open(os.path.join(rd, "wall_times.json"))).items() if k in ("transcribe", "plan", "assets", "critic_assets", "ref_repair", "critic_refs", "render")}
have_transcript = os.path.exists(os.path.join(rd, "transcript.json"))           # a resumed or repeated plan step does not listen again
if have_transcript and STEPS == "plan": WANTED.discard("transcribe")
wall["transcribe"] = stage("transcribe", "from_text.py", rd, audio) if TEXT_INPUT else stage("transcribe", "transcribe.py", rd, audio)
if "transcribe" in WANTED and not TEXT_INPUT and "--keep-audio" not in sys.argv:
    from rules import delete_recordings
    gone = delete_recordings(rd)            # the story now exists as text; the recording itself is no longer needed (privacy: it is deleted unless the parent asked to keep it)
    if gone: print("deleted the recording after transcription:", gone)
wall["plan"] = stage("plan", "plan.py", rd, *(["--pages", n_pages] if n_pages else []))
only = ["--only", ONLY] if ONLY else []
wall["assets"] = stage("assets", "assets.py", rd, "--style", style, *only)
wall["critic_assets"] = stage("critic_assets", "critic.py", rd, "assets", *only)
if "assets" in WANTED and not RESUME:
    ac = json.load(open(os.path.join(rd, "checks", "assets.json")))
    if any(v["confident_mismatches"] for k, v in ac.items() if not ONLY or k == ONLY):
        wall["ref_repair"] = stage("ref_repair", "assets.py", rd, "repair", *only)
        wall["critic_refs"] = stage("critic_refs", "critic.py", rd, "refs", *only)
wall["render"] = stage("render", "render.py", rd, "render")
wall["critic_pages_r0"] = stage("critic_pages_r0", "critic.py", rd, "pages", "r0")
checks = r0_checks = json.load(open(os.path.join(rd, "checks", "pages_r0.json"))) if "render" in WANTED else {}
if any(e["confident_mismatches"] for es in checks.values() for e in es):
    wall["repair"] = stage("repair", "render.py", rd, "repair", os.path.join(rd, "checks", "pages_r0.json"))
    wall["critic_pages_r1"] = stage("critic_pages_r1", "critic.py", rd, "pages", "r1")
    # keep a repair only if it reduced the confident mismatches on that page; otherwise restore the pre-repair image
    r1 = json.load(open(os.path.join(rd, "checks", "pages_r1.json"))); kept = {}
    for n, es in r0_checks.items():
        before = os.path.join(rd, "pages", f"page_{int(n):02d}_before_repair.png")
        if not os.path.exists(before): continue
        c0 = sum(len(e["confident_mismatches"]) for e in es); c1 = sum(len(e["confident_mismatches"]) for e in r1.get(n, []))
        kept[n] = {"before": c0, "after": c1, "kept_repair": c1 < c0}
        if c1 >= c0: os.replace(before, os.path.join(rd, "pages", f"page_{int(n):02d}.png"))
    json.dump(kept, open(os.path.join(rd, "checks", "repair_decisions.json"), "w"), indent=2); print("repair decisions:", kept)
wall["hints"] = stage("hints", "critic.py", rd, "hints")      # warning notes for the human reviewer (nothing is redrawn automatically)
wall["export"] = stage("export", "export.py", rd)
wall["review"] = stage("review", "review.py", rd)
wall["total"] = time.time() - t0
if STEPS == "all": json.dump({k: round(v, 1) for k, v in wall.items()}, open(os.path.join(rd, "wall_times.json"), "w"), indent=2)
print("\n".join(f"{k:18s}{v:7.1f}s" for k, v in wall.items() if v)); print("book:", os.path.join(rd, "book.pdf")) if "export" in WANTED else print("steps done:", STEPS)
pb_event(stage="all", state="done", seconds=round(wall["total"], 1))
