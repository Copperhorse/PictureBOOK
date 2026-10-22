"""Runs the Phase 1 stage scripts (scripts/run_all.py, scripts/regen.py) as ONE subprocess per job and turns their
machine-readable progress lines (``@@pb {json}``) into job events.

Why a subprocess: every stage loads its own model and frees all memory when it exits (one model on the GPU at a time,
inside a memory-capped systemd scope; see scripts/common.py). The sidecar never imports torch itself.

Safety: the sidecar only works on a folder that is a direct child of the library folder and holds a ``book.json``; the
input file name is a fixed pattern. Whole process groups are killed on cancel and on shutdown (stage, ``llama serve`` ...).
"""
import asyncio
import json
import os
import re
import signal
import sys
import time
from collections import deque
from pathlib import Path

from .jobs import Job

# Seconds per stage measured on the development machine (docs/research/phase1-results.md). They are only used to turn
# "which stage is running" into a progress bar; the real work is never timed by them.
STAGES: dict[str, tuple[str, float]] = {
    "transcribe": ("Reading the story", 13), "plan": ("Planning the pages", 50), "assets": ("Drawing characters and places", 70),
    "critic_assets": ("Checking the characters", 33), "ref_repair": ("Fixing a character", 30), "critic_refs": ("Checking the fix", 18),
    "render": ("Drawing the pages", 150), "critic_pages_r0": ("Checking the pages", 60), "repair": ("Repairing pages", 30),
    "critic_pages_r1": ("Checking the repairs", 60), "hints": ("Preparing notes for the review", 30), "export": ("Making the PDF", 1),
    "review": ("Preparing the review", 2),
}
STEP_BASE = {"plan": ["transcribe", "plan"], "assets": ["assets", "critic_assets"], "pages": ["render", "critic_pages_r0", "hints", "export", "review"]}   # parity-tested with scripts/rules.STEP_STAGES
GENERATE = ["transcribe", "plan", "assets", "critic_assets", "render", "critic_pages_r0", "hints", "export", "review"]
INPUT_NAME = re.compile(r"^(story\.txt|audio\.(wav|mp3|m4a|flac|ogg))$")
STYLES = {"crayon", "flat", "watercolour"}
MARK = "@@pb "


class PipelineError(ValueError):
    """A request that must be refused (HTTP 400)."""


class Progress:
    """Maps stage start/end markers (and drawn-page lines) to a 0..1 fraction."""

    def __init__(self, base: list[str], expected: dict[str, float] | None = None):
        self.expected = {k: v[1] for k, v in STAGES.items()} | (expected or {})
        self.total = sum(self.expected.get(s, 5) for s in base)
        self.known = set(base)
        self.done_weight = 0.0
        self.current: str | None = None
        self.started = 0.0
        self.pages_total = 0
        self.pages_done = 0
        self.last = 0.0                              # the bar never goes backwards

    def start(self, stage: str) -> None:
        self.current, self.started, self.pages_done = stage, time.monotonic(), 0
        if stage not in self.known:                 # optional stage (repair ...): the bar grows instead of jumping back
            self.known.add(stage)
            self.total += self.expected.get(stage, 5)

    def finish(self, stage: str) -> None:
        self.done_weight += self.expected.get(stage, 5)
        self.current = None

    def fraction(self) -> float:
        inside = 0.0
        if self.current:
            exp = max(self.expected.get(self.current, 5), 1.0)
            inside = (self.pages_done / self.pages_total) if (self.current == "render" and self.pages_total) else min(0.9, (time.monotonic() - self.started) / exp)
            inside *= exp
        self.last = max(self.last, round(min(0.99, (self.done_weight + inside) / max(self.total, 1.0)), 3))
        return self.last


def resolve_book_dir(library_root: Path | None, raw: str) -> Path:
    if library_root is None:
        raise PipelineError("the library folder is not configured")
    try:
        p = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError):
        raise PipelineError("that book folder does not exist") from None
    if p.parent != library_root.resolve() or not p.is_dir():
        raise PipelineError("the book folder must be directly inside the library folder")
    if not (p / "book.json").is_file():
        raise PipelineError("the folder has no book.json")
    return p


def check_input(book_dir: Path, name: str, must_exist: bool = True) -> Path:
    if not INPUT_NAME.match(name):
        raise PipelineError("the input must be story.txt or audio.<wav|mp3|m4a|flac|ogg>")
    f = book_dir / name
    if must_exist and not f.is_file():
        raise PipelineError(f"{name} is missing in the book folder")
    return f


def kill_group(proc: asyncio.subprocess.Process, sig: int = signal.SIGTERM) -> None:
    if proc.returncode is None:
        try:
            os.killpg(proc.pid, sig)                # start_new_session=True made the child its own group leader
        except ProcessLookupError:
            pass


class PipelineRunner:
    def __init__(self, scripts_dir: Path, python: str | None = None, grace_s: float = 8.0):
        self.scripts_dir = Path(scripts_dir)
        self.python = python or os.environ.get("PICTUREBOOK_PIPELINE_PYTHON") or sys.executable
        self.grace_s = grace_s
        self.procs: dict[str, asyncio.subprocess.Process] = {}

    def check_ready(self) -> None:
        for s in ("run_all.py", "regen.py"):
            if not (self.scripts_dir / s).is_file():
                raise PipelineError(f"the pipeline scripts are not found in {self.scripts_dir}")

    def generate_argv(self, book_dir: Path, input_name: str, style: str, pages: int | None, must_exist: bool = True, keep_audio: bool = False) -> list[str]:
        if style not in STYLES:
            raise PipelineError(f"unknown style {style!r}")
        if pages is not None and not 1 <= pages <= 10:
            raise PipelineError("pages must be between 1 and 10")
        argv = [str(self.scripts_dir / "run_all.py"), str(check_input(book_dir, input_name, must_exist)), str(book_dir), "--style", style]
        return argv + (["--pages", str(pages)] if pages else []) + (["--keep-audio"] if keep_audio else [])

    def step_argv(self, book_dir: Path, step: str, input_name: str, style: str, pages: int | None, only: str | None, keep_audio: bool = False) -> list[str]:
        """One of the three pipeline steps ('plan', 'assets', 'pages') of run_all.py. The input file only has to exist for the plan step
        (later steps read the transcript, and a recording may already be deleted)."""
        if step not in STEP_BASE:
            raise PipelineError("unknown step")
        if only is not None and (step != "assets" or not only.strip() or len(only) > 80 or "\x00" in only):
            raise PipelineError("`only` is for drawing one character or place again, and needs a plain name")
        argv = self.generate_argv(book_dir, input_name, style, pages, must_exist=(step == "plan"), keep_audio=keep_audio)
        argv += ["--steps", step]
        return argv + (["--only", only] if only else [])

    def regen_argv(self, book_dir: Path, pages: list[int] | None, undo: int | None) -> list[str]:
        if undo is not None:
            return [str(self.scripts_dir / "regen.py"), str(book_dir), "--undo", str(int(undo))]
        if not pages or len(pages) > 50 or any(not isinstance(p, int) or p < 1 for p in pages):
            raise PipelineError("pages must be a non-empty list of page numbers")
        return [str(self.scripts_dir / "regen.py"), str(book_dir), ",".join(str(p) for p in sorted(set(pages)))]

    async def run(self, job: Job, argv: list[str], book_dir: Path, base: list[str], expected: dict[str, float] | None = None) -> None:
        progress = Progress(base, expected)
        tail: deque[str] = deque(maxlen=30)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PICTUREBOOK_PARENT": str(os.getpid())}   # the script ends if we die (common.die_with_parent)
        try:
            proc = await asyncio.create_subprocess_exec(self.python, *argv, cwd=str(self.scripts_dir), env=env, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        except OSError as exc:
            await job.emit("error", {"code": "spawn_failed", "message": f"could not start the pipeline: {exc}"}, final=True)
            return
        self.procs[job.id] = proc
        stop_ticker = asyncio.Event()

        async def ticker() -> None:            # keeps the bar moving between stage markers (only when the number changed)
            shown = -1.0
            while not stop_ticker.is_set():
                await asyncio.sleep(2)
                if progress.current and progress.fraction() != shown:
                    shown = progress.fraction()
                    await self._emit(job, progress, "running")

        tick = asyncio.create_task(ticker())
        try:
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                if line.startswith(MARK):
                    try:
                        ev = json.loads(line[len(MARK):])
                    except json.JSONDecodeError:
                        continue
                    stage, state = str(ev.get("stage", "")), str(ev.get("state", ""))
                    if stage == "all":
                        continue
                    if state == "start":
                        progress.start(stage)
                        if stage == "render":
                            progress.pages_total = _plan_pages(book_dir)
                    elif state in ("done", "failed"):
                        progress.finish(stage)
                    await self._emit(job, progress, state, stage)
                else:
                    tail.append(line)
                    if progress.current == "render" and line.startswith("[page]"):
                        progress.pages_done += 1
                        await self._emit(job, progress, "running", message=f"Page {progress.pages_done} of {progress.pages_total or '?'} drawn")
            code = await proc.wait()
        finally:
            stop_ticker.set()
            tick.cancel()
            kill_group(proc, signal.SIGKILL)       # anything the stage left behind (llama serve ...)
            self.procs.pop(job.id, None)
        if job.cancel_requested:
            await job.emit("cancelled", {"message": "stopped by the user"}, final=True)
        elif code == 0:
            await job.emit("done", {"result": {"book_dir": book_dir.name, "pdf": (book_dir / "book.pdf").is_file()}}, final=True)
        else:
            await job.emit("error", {"code": "stage_failed", "stage": progress.current or "", "message": "\n".join(tail) or f"the pipeline exited with code {code}"}, final=True)

    async def _emit(self, job: Job, progress: Progress, state: str, stage: str | None = None, message: str | None = None) -> None:
        cur = stage or progress.current or ""
        label = STAGES.get(cur, (cur, 0))[0]
        await job.emit("progress", {"stage": cur, "state": state, "label": label, "fraction": progress.fraction(), "message": message or label})

    async def cancel(self, job: Job) -> bool:
        proc = self.procs.get(job.id)
        if proc is None or proc.returncode is not None:
            return False
        job.cancel_requested = True
        kill_group(proc, signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), self.grace_s)
        except asyncio.TimeoutError:
            kill_group(proc, signal.SIGKILL)
        return True

    def kill_all(self) -> None:
        for proc in list(self.procs.values()):
            kill_group(proc, signal.SIGKILL)


def _plan_pages(book_dir: Path) -> int:
    try:
        return len(json.loads((book_dir / "plan.json").read_text())["pages"])
    except Exception:
        return 0
