"""FastAPI app: bearer-token auth, Host-header check, health, demo job with SSE progress, shutdown."""
import asyncio
import contextlib
import hmac
import os
import shutil
import subprocess
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path

from pydantic import BaseModel, Field

from . import __version__
from .jobs import JobManager
from . import diagnostics
from .pipeline import GENERATE, STEP_BASE, PipelineError, PipelineRunner, resolve_book_dir
from . import plan_edit


class GenerateRequest(BaseModel):
    book_dir: str
    input: str = "story.txt"                      # story.txt (typed) or audio.<ext>, inside the book folder
    style: str = "crayon"
    pages: int | None = Field(None, ge=1, le=10)
    keep_audio: bool = False                      # keep the recording after it was transcribed (default: delete it)


class StepRequest(BaseModel):
    book_dir: str
    step: str                                      # plan | assets | pages
    input: str = "story.txt"
    style: str = "crayon"
    pages: int | None = Field(None, ge=1, le=10)
    only: str | None = Field(None, max_length=80)  # assets step: draw this one character or place again
    keep_audio: bool = False


class SaveItemRequest(BaseModel):
    book_dir: str
    name: str = Field(..., min_length=1, max_length=80)
    fields: dict = Field(..., max_length=20)


class RegenRequest(BaseModel):
    book_dir: str
    pages: list[int] = Field(..., min_length=1, max_length=50)


class UndoRequest(BaseModel):
    book_dir: str
    page: int = Field(..., ge=1)


class DemoJobRequest(BaseModel):
    steps: int = Field(5, ge=1, le=100)
    delay_ms: int = Field(200, ge=0, le=5000)


def gpu_info() -> dict | None:
    """Best-effort GPU summary from nvidia-smi; None when unavailable."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().splitlines()[0]
        name, total, used = [x.strip() for x in out.split(",")]
        return {"name": name, "vram_total_mib": int(total), "vram_used_mib": int(used)}
    except Exception:
        return None


def create_app(token: str, on_shutdown: Callable[[], None] | None = None, allowed_hosts: set[str] | None = None,
               on_startup: Callable[[], None] | None = None, library_root: Path | None = None, scripts_dir: Path | None = None,
               pipeline_python: str | None = None) -> FastAPI:
    if not token or len(token) < 16:
        raise ValueError("a token of at least 16 characters is required")
    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        if on_startup:
            on_startup()
        try:
            yield
        finally:
            runner.kill_all()                      # never leave a stage or llama serve running behind the sidecar

    app = FastAPI(title="PictureBOOK sidecar", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    jobs = JobManager()
    app.state.jobs = jobs
    root = Path(library_root) if library_root else (Path(os.environ["PICTUREBOOK_LIBRARY"]) if os.environ.get("PICTUREBOOK_LIBRARY") else None)
    scripts = Path(scripts_dir or os.environ.get("PICTUREBOOK_SCRIPTS") or Path(__file__).resolve().parents[2] / "scripts")   # dev default: the repository's scripts/
    runner = PipelineRunner(scripts, pipeline_python)
    app.state.runner = runner

    @app.middleware("http")
    async def host_check(request: Request, call_next):
        # Defence against DNS rebinding: only loopback host names are served.
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
        ok = host in {"127.0.0.1", "localhost", "::1", "testserver"} if allowed_hosts is None else host in allowed_hosts
        if not ok:
            return JSONResponse({"detail": "bad host"}, status_code=400)
        return await call_next(request)

    def require_auth(request: Request) -> None:
        header = request.headers.get("authorization", "")
        supplied = header[7:] if header.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="unauthorised")

    @app.get("/health", dependencies=[Depends(require_auth)])
    async def health():
        return {"status": "ok", "version": __version__, "gpu": gpu_info(), "loaded": []}

    @app.get("/diagnostics", dependencies=[Depends(require_auth)])
    async def get_diagnostics():
        env = diagnostics.Env(scripts_dir=scripts, library_dir=root, pipeline_python=runner.python)
        checks = await asyncio.get_running_loop().run_in_executor(None, diagnostics.run_checks, env)
        return diagnostics.report(checks)

    @app.post("/jobs/demo", dependencies=[Depends(require_auth)])
    async def demo_job(req: DemoJobRequest):
        job = jobs.create()
        jobs.spawn(jobs.run_demo(job, req.steps, req.delay_ms / 1000))
        return {"job_id": job.id}

    def start_pipeline(make, base, expected=None):
        """One GPU: one pipeline job at a time. `make` returns (argv, book_dir) or raises PipelineError."""
        try:
            runner.check_ready()
            argv, book_dir = make()
        except PipelineError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        busy = next((j for j in jobs.jobs.values() if j.pipeline and not j.finished), None)
        if busy is not None:
            raise HTTPException(status_code=409, detail=f"another job is running ({busy.id})")
        job = jobs.create()
        job.pipeline = True
        jobs.spawn(runner.run(job, argv, book_dir, base, expected))
        return {"job_id": job.id}

    @app.post("/jobs/generate", dependencies=[Depends(require_auth)])
    async def generate(req: GenerateRequest):
        def make():
            d = resolve_book_dir(root, req.book_dir)
            return runner.generate_argv(d, req.input, req.style, req.pages, keep_audio=req.keep_audio), d
        return start_pipeline(make, GENERATE)

    @app.post("/jobs/step", dependencies=[Depends(require_auth)])
    async def step(req: StepRequest):
        def make():
            d = resolve_book_dir(root, req.book_dir)
            argv = runner.step_argv(d, req.step, req.input, req.style, req.pages, req.only, req.keep_audio)
            return argv, d
        base = STEP_BASE.get(req.step, [])
        expected = {"assets": 14.0, "critic_assets": 8.0} if req.only else None      # one character is much quicker than a whole cast
        return start_pipeline(make, base, expected)

    @app.get("/plan/options", dependencies=[Depends(require_auth)])
    async def plan_options():
        try:
            return plan_edit.options(scripts)
        except plan_edit.PlanEditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    def save_plan_item(kind: str, req: SaveItemRequest):
        if any(j.pipeline and not j.finished for j in jobs.jobs.values()):
            raise HTTPException(status_code=409, detail="wait until the running job has finished")
        try:
            d = resolve_book_dir(root, req.book_dir)
            return {"spec": plan_edit.save_item(scripts, d, kind, req.name, req.fields)}
        except (PipelineError, plan_edit.PlanEditError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/plan/character", dependencies=[Depends(require_auth)])
    async def save_character(req: SaveItemRequest):
        return save_plan_item("character", req)

    @app.post("/plan/place", dependencies=[Depends(require_auth)])
    async def save_place(req: SaveItemRequest):
        return save_plan_item("place", req)

    @app.post("/jobs/regen", dependencies=[Depends(require_auth)])
    async def regen(req: RegenRequest):
        def make():
            d = resolve_book_dir(root, req.book_dir)
            return runner.regen_argv(d, req.pages, None), d
        return start_pipeline(make, ["render", "hints", "export", "review"], {"render": 35.0 * len(set(req.pages)) + 8, "hints": 12.0 * len(set(req.pages)) + 12})

    @app.post("/jobs/undo", dependencies=[Depends(require_auth)])
    async def undo(req: UndoRequest):
        def make():
            d = resolve_book_dir(root, req.book_dir)
            return runner.regen_argv(d, None, req.page), d
        return start_pipeline(make, ["export", "review"])

    @app.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_auth)])
    async def cancel(job_id: str):
        job = jobs.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return {"cancelled": await runner.cancel(job)}

    @app.get("/events/{job_id}", dependencies=[Depends(require_auth)])
    async def events(job_id: str):
        job = jobs.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return StreamingResponse(jobs.stream(job), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/shutdown", dependencies=[Depends(require_auth)])
    async def shutdown():
        runner.kill_all()
        if on_shutdown:
            on_shutdown()
        return {"ok": True}

    return app
