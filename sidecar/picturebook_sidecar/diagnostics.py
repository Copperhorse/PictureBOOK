"""First-run check: is everything the pipeline needs present on this machine? Every probe is a plain function of an `Env`
(paths, PATH, a command runner), so each ok / warn / missing branch is tested without touching the real machine.

Model locations come from `scripts/modelpaths.py`, the same file the stage scripts load models from, so the check cannot disagree
with the pipeline. Nothing is downloaded or changed here; every problem comes with a plain-words fix."""
import importlib.util
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

OK, WARN, MISSING = "ok", "warn", "missing"
MIN_VRAM_MIB, MIN_DISK_GB, MIN_RAM_GIB = 7500, 10.0, 6.0     # 8 GB card (7.5 GiB usable), room for models and pages, the pipeline refuses below 5 GiB


@dataclass
class Check:
    id: str
    title: str
    status: str
    detail: str
    fix: str = ""
    needed_for: str = "all"          # all | audio | optional ("audio" = only books made from a recording)

    @property
    def blocking(self) -> bool:
        return self.status == MISSING and self.needed_for != "optional"


@dataclass
class Env:
    scripts_dir: Path
    home: Path = field(default_factory=Path.home)
    path: str = field(default_factory=lambda: os.environ.get("PATH", ""))
    library_dir: Path | None = None
    pipeline_python: str = sys.executable
    run: object = None               # run(argv, timeout) -> (returncode, stdout); injectable for tests
    meminfo: str = "/proc/meminfo"
    disk_free: object = None         # () -> bytes free; injectable for tests

    def runner(self, argv: list[str], timeout: float = 15.0) -> tuple[int, str]:
        if self.run is not None:
            return self.run(argv, timeout)
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 127, str(exc)

    def which(self, name: str) -> str | None:
        return shutil.which(name, path=os.pathsep.join([str(self.home / ".local" / "bin"), self.path]))


def load_modelpaths(scripts_dir: Path, home: Path):
    """The scripts' own model-location module (pure standard library); `home` lets tests point it at a fake home folder."""
    f = Path(scripts_dir) / "modelpaths.py"
    if not f.is_file():
        return None
    spec = importlib.util.spec_from_file_location("pb_modelpaths", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.home = lambda: str(home)         # type: ignore[attr-defined]
    return mod


def _size(p: str) -> int:
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def check_gpu(env: Env) -> Check:
    rc, out = env.runner(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], 10) if env.which("nvidia-smi") or env.run else (127, "")
    if rc != 0 or "," not in out:
        return Check("gpu", "Graphics card", MISSING, "No NVIDIA graphics card answered.", "Install the NVIDIA driver (the app needs a CUDA card with 8 GB) and restart; if the driver was just updated, reboot.")
    name, mib = [x.strip() for x in out.strip().splitlines()[0].split(",")][:2]
    if int(float(mib)) < MIN_VRAM_MIB:
        return Check("gpu", "Graphics card", WARN, f"{name}, {int(float(mib))} MiB. The pictures were tested on 8 GB cards and may not fit in less.", "Close other programs that use the card, or use a card with 8 GB or more.")
    return Check("gpu", "Graphics card", OK, f"{name}, {int(float(mib))} MiB")


def check_torch(env: Env) -> Check:
    rc, out = env.runner([env.pipeline_python, "-c", "import torch;print(torch.cuda.is_available(), torch.__version__)"], 90)
    last = out.strip().splitlines()[-1] if out.strip() else ""
    if rc == 0 and last.startswith("True"):
        return Check("torch", "Picture engine (PyTorch with CUDA)", OK, last.split(" ", 1)[1])
    if rc == 0:
        return Check("torch", "Picture engine (PyTorch with CUDA)", MISSING, "PyTorch is installed but cannot use the graphics card.", "Check the NVIDIA driver; after a driver update a reboot is needed.")
    return Check("torch", "Picture engine (PyTorch with CUDA)", MISSING, "PyTorch is not available in the app's Python environment.", "Run `uv sync` in the sidecar folder (about 2 GB download).")


def check_llama(env: Env) -> Check:
    exe = env.which("llama")
    if not exe:
        return Check("llama", "Language and vision program (llama.cpp)", MISSING, "The `llama` program was not found (looked in ~/.local/bin and PATH).", "Install llama.cpp so that the `llama` command exists (see the project README).")
    rc, out = env.runner([exe, "version"], 15)
    first = out.strip().splitlines()[0] if out.strip() else "installed"
    return Check("llama", "Language and vision program (llama.cpp)", OK if rc == 0 else WARN, first if rc == 0 else f"Found at {exe} but it did not report a version.", "" if rc == 0 else "Reinstall llama.cpp.")


def check_gemma(env: Env, mp) -> Check:
    model, proj = mp.gemma_e4b()
    miss = [p for p in (model, proj) if _size(p) < 50_000_000]
    if not miss:
        return Check("gemma", "Story planner and checker (Gemma 4 E4B)", OK, f"{_size(model) / 1e9:.1f} GB + projector")
    return Check("gemma", "Story planner and checker (Gemma 4 E4B)", MISSING, "Missing: " + ", ".join(os.path.basename(p) for p in miss) + ".",
                 f"Put gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf and mmproj-F16.gguf in {os.path.dirname(model)} (about 5.5 GB).")


def check_hf(env: Env, mp, repo: str, cid: str, title: str, size: str, needed_for: str = "all") -> Check:
    snap = mp.hf_snapshot(repo)
    if snap:
        return Check(cid, title, OK, repo, needed_for=needed_for)
    return Check(cid, title, MISSING, f"{repo} is not downloaded.", f"Run `hf download {repo}` ({size}).", needed_for=needed_for)


def check_ffmpeg(env: Env) -> Check:
    if env.which("ffmpeg"):
        return Check("ffmpeg", "Audio converter (ffmpeg)", OK, "found", needed_for="optional")
    return Check("ffmpeg", "Audio converter (ffmpeg)", WARN, "ffmpeg was not found. m4a files and some recordings cannot be converted.", "Install ffmpeg (for example `sudo pacman -S ffmpeg`).", needed_for="optional")


def check_microphone(env: Env) -> Check:
    """Is there an input device? (pactl talks to PipeWire's PulseAudio layer; without it the check can only say 'unknown'.)"""
    if not env.which("pactl"):
        return Check("microphone", "Microphone", WARN, "Could not look for a microphone (`pactl` was not found).", "Recording in the app may still work; try the Record screen.", "optional")
    rc, out = env.runner(["pactl", "list", "short", "sources"], 10)
    inputs = [ln.split("\t")[1] for ln in out.splitlines() if "\t" in ln and not ln.split("\t")[1].endswith(".monitor")]
    if rc == 0 and inputs:
        return Check("microphone", "Microphone", OK, f"{len(inputs)} input device{'s' if len(inputs) != 1 else ''} found", needed_for="optional")
    return Check("microphone", "Microphone", WARN, "No microphone was found, so stories cannot be recorded (typing and audio files still work).", "Plug in a microphone, or check the sound settings of your system.", "optional")


def check_systemd(env: Env) -> Check:
    if not env.which("systemd-run"):
        return Check("memory_cap", "Memory safety (systemd)", WARN, "`systemd-run` was not found, so the pipeline cannot limit its memory.", "Without it a runaway model could slow the whole computer; install systemd or free memory before long books.", "optional")
    rc, out = env.runner(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=1G", "true"], 15)
    if rc == 0:
        return Check("memory_cap", "Memory safety (systemd)", OK, "memory limits work", needed_for="optional")
    return Check("memory_cap", "Memory safety (systemd)", MISSING, "The user systemd session refused to start a limited process.", "Log in through a normal desktop session (a user systemd session is required).")


def check_disk(env: Env) -> Check:
    target = env.library_dir if env.library_dir and env.library_dir.exists() else env.home
    free = (env.disk_free() if env.disk_free else shutil.disk_usage(target).free) / 1e9
    if free >= MIN_DISK_GB:
        return Check("disk", "Free disk space", OK, f"{free:.0f} GB free", needed_for="optional")
    return Check("disk", "Free disk space", WARN if free >= 3 else MISSING, f"Only {free:.1f} GB free where the books are kept.", "Free some space; a book with its pictures needs about 100 MB, the models more.", "optional" if free >= 3 else "all")


def check_ram(env: Env) -> Check:
    try:
        kb = next(int(line.split()[1]) for line in Path(env.meminfo).read_text().splitlines() if line.startswith("MemAvailable:"))
    except (OSError, StopIteration, ValueError):
        return Check("ram", "Free memory", WARN, "Could not read the memory state.", needed_for="optional")
    gib = kb / 1024 / 1024
    if gib >= MIN_RAM_GIB:
        return Check("ram", "Free memory", OK, f"{gib:.1f} GiB available", needed_for="optional")
    return Check("ram", "Free memory", WARN, f"Only {gib:.1f} GiB of memory is free; making a book needs about 6 GiB.", "Close other programs (browsers use a lot) and check again.", "optional")


def run_checks(env: Env) -> list[Check]:
    mp = load_modelpaths(env.scripts_dir, env.home)
    if mp is None:
        return [Check("scripts", "Pipeline scripts", MISSING, f"The pipeline scripts were not found in {env.scripts_dir}.", "Reinstall the app or set PICTUREBOOK_SCRIPTS.")]
    jobs = [lambda: check_gpu(env), lambda: check_torch(env), lambda: check_llama(env), lambda: check_gemma(env, mp),
            lambda: check_hf(env, mp, mp.KLEIN_REPO, "klein", "Picture model (FLUX.2 klein)", "4.8 GB"),
            lambda: check_hf(env, mp, mp.WHISPER_REPO, "whisper", "Speech model (Whisper)", "1.6 GB", "audio"),
            lambda: check_ffmpeg(env), lambda: check_microphone(env), lambda: check_systemd(env), lambda: check_disk(env), lambda: check_ram(env)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(j) for j in jobs]
        return [f.result() for f in futures]


def report(checks: list[Check]) -> dict:
    return {"checks": [{**asdict(c), "blocking": c.blocking} for c in checks], "blockers": [c.id for c in checks if c.blocking],
            "audio_ready": not any(c.blocking for c in checks if c.needed_for in ("all", "audio"))}
