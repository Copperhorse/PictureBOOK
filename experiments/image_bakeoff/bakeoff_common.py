"""Shared helpers for the image bake-off: specs from the mock run, a PromptComposer prototype, and resource measurement."""
import json, os, re, subprocess, threading, time, resource

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_MOCK = os.path.join(HERE, "..", "..", "docs", "examples", "mock-run.md")

# ---------- specs: single source of truth is docs/examples/mock-run.md ----------
def load_mock():
    md = open(DOCS_MOCK).read()
    blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", md, re.S)]
    ce = [b for b in blocks if isinstance(b, dict) and "characters" in b][0]
    pages = [b for b in blocks if isinstance(b, dict) and "pages" in b][0]["pages"]
    return {c["name"]: c for c in ce["characters"]}, {e["name"]: e for e in ce["environments"]}, pages

STYLES = {
    "flat": "flat cut-paper storybook illustration, simple shapes, soft drop shadows, muted gentle palette, clean edges",
    "watercolour": "soft watercolour children's book illustration, gentle colour washes, visible paper texture, warm muted palette",
    "crayon": "crayon and coloured-pencil children's book illustration, waxy texture, hand-drawn wobbly lines, soft palette",
}

# ---------- PromptComposer prototype (pure code, deterministic) ----------
def _none(v): return (v or "").strip().lower() in ("", "none")
def render_descriptor(c):
    parts = [f"{c['name']}, a {c['height_relative'].replace('_', ' ')}, {c['build']}-build {c['age_group']} {c['species']}"]
    if not _none(c["hair"]): parts.append(f"with {c['hair']} hair")
    if not _none(c["skin_colour"]): parts.append(f"{c['skin_colour']} skin")
    if not _none(c["face"]): parts.append(c["face"])
    if not _none(c["headwear"]): parts.append(f"wearing {c['headwear']}")
    def art(o): return "" if o["item"].strip().lower().endswith("s") else "a "
    outfit = ", ".join(f"{art(o)}{o['colour']} {o['item']}" + ("" if _none(o["detail"]) else f" ({o['detail']})") for o in c["outfit"])
    parts.append(f"wearing {outfit}")
    if not _none(c["eyewear"]): parts.append(f"with {c['eyewear']}")
    if not _none(c["accessories"]): parts.append(f"with {c['accessories']}")
    if not _none(c["distinguishing_marks"]): parts.append(c["distinguishing_marks"])
    return ", ".join(parts)

def render_environment(e):
    bits = [e["location"], f"{e['time_of_day']}" if e["time_of_day"] != "none" else "", f"{e['season']}" if e["season"] != "none" else "",
            e["lighting"], f"{e['mood']} mood", "palette " + ", ".join(e["palette"])]
    if e["key_objects"]: bits.append(", ".join(e["key_objects"]))
    return ", ".join(b for b in bits if b)

def character_prompt(c, style, pose="standing, hands relaxed, facing the viewer", expression="neutral expression"):
    return f"{STYLES[style]}. Full-body character on a plain light background. {render_descriptor(c)}. {pose}, {expression}."

def plate_prompt(e, style):
    return f"{STYLES[style]}. Wide view of {render_environment(e)}. No people, no characters."

def scene_prompt(page, chars, env, style):
    present = [chars[l["character"]] for l in page["layout"]]
    who = " ".join(render_descriptor(c) + "." for c in present)
    fx = (" Visible effects: " + "; ".join(page["effects"]) + ".") if page["effects"] else ""
    return f"{STYLES[style]}. {page['camera']} shot. {page['scenario']} {who}{fx} Setting: {render_environment(env)}."

def derive_pose_instruction(pose, expression, facing="the viewer"):
    return (f"Same character, now {pose}, {expression} expression, facing {facing}, plain light background. "
            "Keep the face, hair, outfit colours and proportions unchanged.")

def derive_pose_instruction_v2(pose, expression, keep="the small wooden stick", facing="the viewer"):
    """v2 template: also names accessories to keep (v1 lost the stick in 4 of 5 edits)."""
    return (f"Same character, now {pose}, with a {expression} expression, facing {facing}, plain light background. "
            f"Keep the face, hair, outfit colours and proportions unchanged, and keep {keep} in the hand.")

def repair_instruction(item, observed, expected):
    return f"Change the {item} colour from {observed} to {expected}. Keep everything else exactly the same."

# ---------- resource measurement ----------
def mem_available_gib():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"): return int(l.split()[1]) / 1048576
def require_ram(min_gib=6.0):
    a = mem_available_gib()
    if a < min_gib: raise SystemExit(f"Only {a:.1f} GiB RAM available (need {min_gib}); close programs and retry.")
    return a

class GpuSampler:
    """Samples nvidia-smi memory.used every 0.5 s in a thread; reports the peak (includes the CUDA context)."""
    def __init__(self, interval=0.5): self.interval, self.peak, self._stop = interval, 0, threading.Event()
    def _loop(self):
        while not self._stop.is_set():
            try:
                v = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout.strip().split()[0])
                self.peak = max(self.peak, v)
            except Exception: pass
            time.sleep(self.interval)
    def __enter__(self): self._t = threading.Thread(target=self._loop, daemon=True); self._t.start(); return self
    def __exit__(self, *a): self._stop.set(); self._t.join(timeout=3)
    def reset(self): self.peak = 0

def peak_rss_gib(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
def log_json(path, rec):
    with open(path, "a") as f: f.write(json.dumps(rec) + "\n")

# ---------- compact prompts for SDXL (CLIP reads only 77 tokens per encoder; the long klein prompts get truncated) ----------
STYLES_SHORT = {"flat": "flat cut-paper storybook illustration, muted palette", "watercolour": "soft watercolour children's book illustration",
                "crayon": "crayon and coloured pencil children's book illustration"}
def compact_descriptor(c):
    outfit = ", ".join(f"{o['colour']} {o['item']}" for o in c["outfit"])
    bits = [f"{c['height_relative'].replace('_', ' ')} {c['build']} {c['age_group']} {c['species']}", f"{c['hair']} hair", f"{outfit}"]
    if not _none(c["headwear"]): bits.append(c["headwear"])
    if not _none(c["accessories"]): bits.append(c["accessories"].replace(" held like a wand", ""))
    return ", ".join(bits)
def character_prompt_short(c, style, pose="standing facing the viewer"):
    return f"{STYLES_SHORT[style]}, full body character on a plain light background, {compact_descriptor(c)}, {pose}, no text"
def plate_prompt_short(e, style):
    return f"{STYLES_SHORT[style]}, wide landscape, {e['location']}, {e['lighting']}, {', '.join(e['key_objects'][:3])}, no people"
def scene_prompt_short(page, chars, env, style):
    who = "; ".join(compact_descriptor(chars[l['character']]) for l in page['layout'])
    return f"{STYLES_SHORT[style]}, {page['camera']} shot, {who}, {', '.join(page['effects'])}, in a {env['location']}"
