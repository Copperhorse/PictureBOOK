"""Shared helpers for the Phase 1 command-line pipeline: run directory, timings, sentence splitting, prompt composer, llama server control."""
import base64, json, os, re, signal, subprocess, sys, time, urllib.request
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ---------------------------------------------------------------- run directory and timings
class Run:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        for d in ("assets", "pages", "checks"): os.makedirs(os.path.join(self.dir, d), exist_ok=True)
    def p(self, *a): return os.path.join(self.dir, *a)
    def load(self, name): return json.load(open(self.p(name)))
    def save(self, name, obj): json.dump(obj, open(self.p(name), "w"), indent=2, ensure_ascii=False)
    @property
    def style(self):
        """Art style chosen for this run (written by run_all.py / assets.py to config.json; default crayon)."""
        try: return self.load("config.json").get("style", "crayon")
        except FileNotFoundError: return "crayon"
    def log(self, stage, seconds, **extra):
        path = self.p("timings.jsonl")
        with open(path, "a") as f: f.write(json.dumps({"stage": stage, "seconds": round(seconds, 1), "at": time.strftime("%H:%M:%S"), **extra}) + "\n")
        print(f"[{stage}] {seconds:.1f}s {extra if extra else ''}", flush=True)

@contextmanager
def timed(run, stage, **extra):
    t = time.time(); yield; run.log(stage, time.time() - t, **extra)

# ---------------------------------------------------------------- text
def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]

def _none(v): return (v or "").strip().lower() in ("", "none")

# ---------------------------------------------------------------- prompt composer (code, deterministic)
STYLE = {"crayon": "crayon and coloured-pencil children's book illustration, waxy texture, hand-drawn wobbly lines, soft palette",
         "flat": "flat cut-paper storybook illustration, simple shapes, soft drop shadows, muted gentle palette, clean edges",
         "watercolour": "soft watercolour children's book illustration, gentle colour washes, visible paper texture, warm muted palette"}
NO_TEXT = "No text, no lettering, no captions, no signature."
EXPRESSION_WORDS = {"determined": "focused, calm and concentrating", "shy": "bashful with a small timid smile", "proud": "quietly proud with a small smile",
                    "angry": "cross", "embarrassed": "a little embarrassed", "sad": "sad", "happy": "happy", "surprised": "surprised", "scared": "frightened",
                    "curious": "curious", "sleepy": "sleepy", "neutral": "calm"}

def descriptor(c):
    parts = [f"{c['name']}, a {c['height_relative'].replace('_', ' ')}, {c['build']}-build {c['age_group']} {c['species']}"]
    if not _none(c["hair"]): parts.append(f"with {c['hair']} hair" + (f" in a {c['hair_style']} style" if c.get("hair_style") not in (None, "covered") else ""))
    if not _none(c["skin_colour"]): parts.append(f"{c['skin_colour']} skin")
    if not _none(c["face"]): parts.append(c["face"])
    if not _none(c["headwear"]): parts.append(f"wearing {c['headwear']}")
    def art(o): return "" if o["item"].strip().lower().endswith("s") else "a "
    parts.append("wearing " + ", ".join(f"{art(o)}{o['colour']} {o['item']}" + ("" if _none(o["detail"]) else f" ({o['detail']})") for o in c["outfit"]))
    if not _none(c["eyewear"]): parts.append(f"with {c['eyewear']}")
    if not _none(c["accessories"]): parts.append(f"with {c['accessories']}")
    if not _none(c["distinguishing_marks"]): parts.append(c["distinguishing_marks"])
    return ", ".join(parts)

def env_text(e):
    bits = [e["location"], e["time_of_day"] if e["time_of_day"] != "none" else "", e["season"] if e["season"] != "none" else "", e["lighting"], f"{e['mood']} mood", "palette " + ", ".join(e["palette"])]
    if e["key_objects"]: bits.append(", ".join(e["key_objects"]))
    return ", ".join(b for b in bits if b)

def character_prompt(c, style):
    return f"{STYLE[style]}. Full-body character on a plain light background. {descriptor(c)}. Standing, hands relaxed, facing the viewer, calm expression. {NO_TEXT}"

def plate_prompt(e, style):
    return f"{STYLE[style]}. Wide view of {env_text(e)}. No people, no characters, no animals, no kites or other carried objects. {NO_TEXT}"

def page_instruction(page, chars, env, ref_names, style="crayon"):
    """Multi-reference instruction: image 1 is the background plate, then one reference image per character in `ref_names` order."""
    lines = [f"Compose one picture-book page in the same style as the pictures given ({STYLE[style]}). Image 1 is the background ({env['name']})."]
    for i, n in enumerate(ref_names, 2):
        who = chars.get(n)
        lines.append(f"Image {i} is {n}" + (f", {'an' if who['species'][:1].lower() in 'aeiou' else 'a'} {who['species']}." if who else "."))
    for l in page["layout"]:
        lines.append(f"{l['character']}: {l['pose'].replace('_', ' ')}" + ("" if _none(l["pose_detail"]) else f" ({l['pose_detail']})") + ("" if _none(l.get("placement", "")) else f", {l['placement']}") + f", {EXPRESSION_WORDS[l['expression']]} expression, on the {l['position']}, {l['depth']}, facing {l['facing']}.")
    lines.append(page["scenario"])
    for rf in page.get("reflections", []):
        who = chars.get(rf["of"]); sp = who["species"] if who else "character"
        lines.append(f"{rf['of']}'s reflection is visible as a faint, mirrored, slightly rippled image in {rf['surface']}. It is only a reflection, not a second {sp}: there is exactly one real {rf['of']} in the picture, and the reflection stays inside {rf['surface']}.")
    if page.get("must_show"): lines.append("The picture must clearly show: " + "; ".join(page["must_show"]) + ".")
    if page["effects"]: lines.append("Visible effects: " + "; ".join(page["effects"]) + ".")
    if len(ref_names) > 1:
        lines.append(f"These are {len(ref_names)} different individuals and each appears exactly once: " + "; ".join(f"{n} looks only like image {i}" for i, n in enumerate(ref_names, 2)) + ". Never mix features between characters (a person has human ears and no animal parts; an animal keeps its own head, fur and ears); characters stand beside each other without overlapping furniture or each other.")
    lines.append("Keep every character's appearance exactly as in their reference image and keep the background as in image 1. " + NO_TEXT)
    return " ".join(lines)

def repair_instruction(attribute, observed, expected, who="the character"):
    """Targeted edit. Verified on the mage's wand (docs/research/phase1-results.md): 'Change X from A to B' did not remove a spear; 'Remove A completely. Instead ...' did."""
    exp = "nothing" if _none(expected) else expected
    t = {"held_item": f"Remove the {observed} completely. Instead {who} holds {exp} in one hand." if exp != "nothing" else f"Remove the {observed} completely so {who} holds nothing.",
         "headwear": f"Remove the {observed} on the head of {who}. Instead {who} wears {exp}." if exp != "nothing" else f"Remove the {observed} from the head of {who}, showing the hair.",
         "eyewear": f"Remove the {observed} from the face of {who}. Instead {who} wears {exp}." if exp != "nothing" else f"Remove the {observed} from the face of {who}.",
         "outfit": f"Change the clothing of {who} from {observed} to {exp}."}.get(attribute, f"Change the {attribute.replace('_', ' ')} of {who} from {observed} to {exp}.")
    return f"{t} Keep the face, hair, pose and background exactly the same. {NO_TEXT}"

# ---------------------------------------------------------------- llama server control (Gemma 4 E4B + projector)
LLAMA_PORT, LLAMA_KEY = 18090, "pipeline-local-key"
import modelpaths
E4B = modelpaths.gemma_e4b()
QWEN35_4B = modelpaths.qwen35_4b()
VLMS = {"e4b": E4B, "qwen35_4b": QWEN35_4B}   # PB_VLM=<name> picks the vision model for every llama_server() call (default e4b)

@contextmanager
def llama_server(log_path, port=LLAMA_PORT):
    """Start `llama serve` (E4B + vision projector, 1120 image tokens, reasoning budget capped) and stop it afterwards."""
    model = VLMS[os.environ.get("PB_VLM", "e4b")]
    cmd = ["llama", "serve", "-m", model[0], "--mmproj", model[1], "--host", "127.0.0.1", "--port", str(port), "-ngl", "99", "-c", "16384", "-np", "1", "-fa", "on",
           "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--temp", "0.6", "--top-p", "0.95", "--top-k", "20", "--repeat-penalty", "1.1", "--repeat-last-n", "256",
           "--reasoning-budget", "2048", "--jinja", "--api-key", LLAMA_KEY, "--no-webui", "--image-min-tokens", "1120", "--image-max-tokens", "1120", "-lv", "3"]
    log = open(log_path, "w")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
    try:
        for _ in range(120):
            if proc.poll() is not None: raise RuntimeError(f"llama serve exited early, see {log_path}")
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Authorization": f"Bearer {LLAMA_KEY}"})
                if b"ok" in urllib.request.urlopen(req, timeout=2).read(): break
            except Exception: time.sleep(1)
        else: raise RuntimeError("llama serve did not become healthy")
        yield port
    finally:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=15)
        except subprocess.TimeoutExpired: proc.kill()

def chat(port, messages, schema=None, name="out", temperature=0.4, max_tokens=3000, seed=None, think=False, logprobs=False):
    body = {"model": "x", "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if seed is not None: body["seed"] = seed
    if not think: body["chat_template_kwargs"] = {"enable_thinking": False}
    if schema: body["response_format"] = {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
    if logprobs: body.update({"logprobs": True, "top_logprobs": 5})
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": f"Bearer {LLAMA_KEY}"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    return r["choices"][0]

def image_part(path): return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()}}

def die_with_parent():
    """Linux: SIGTERM us when the process that started us (the sidecar) dies, so a crashed sidecar never leaves a GPU job behind.
    The sidecar sets PICTUREBOOK_PARENT to its pid; if it is already gone by now, stop at once (the race the kernel flag cannot cover)."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)          # PR_SET_PDEATHSIG
    except Exception:
        return
    expected = os.environ.get("PICTUREBOOK_PARENT")
    if expected and expected.isdigit() and os.getppid() != int(expected): sys.exit("the app that started this job is gone")

def pb_event(**kw):
    """Machine-readable progress line for the app (the sidecar parses lines that start with '@@pb '); humans just see a JSON line."""
    print("@@pb " + json.dumps(kw), flush=True)

def capped(cmd):
    """Run a stage in its own memory-capped systemd scope: a runaway model kills only itself, never the desktop."""
    return ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=11G", "-p", "MemorySwapMax=0"] + list(cmd)

def require_ram(min_gib=6.0):
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"):
            a = int(l.split()[1]) / 1048576
            if a < min_gib: raise SystemExit(f"Only {a:.1f} GiB RAM available (need {min_gib}); close programs.")
