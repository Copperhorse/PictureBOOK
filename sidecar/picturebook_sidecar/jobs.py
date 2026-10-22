"""In-memory job manager: each job owns an append-only event list that SSE subscribers replay and then follow."""
import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    events: list[dict] = field(default_factory=list)
    finished: bool = False
    cancel_requested: bool = False
    pipeline: bool = False
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def emit(self, event: str, data: dict, final: bool = False) -> None:
        async with self.cond:
            self.events.append({"event": event, "data": data})
            self.finished = self.finished or final
            self.cond.notify_all()


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()

    KEEP_FINISHED = 50                      # a long session must not grow without bound; recent jobs stay so a reconnecting window can still replay them

    def create(self) -> Job:
        finished = [j for j in self.jobs.values() if j.finished]          # dicts keep insertion order: oldest first
        for old in finished[: max(0, len(finished) - self.KEEP_FINISHED + 1)]:
            del self.jobs[old.id]
        job = Job(id=uuid.uuid4().hex)
        self.jobs[job.id] = job
        return job

    def spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run_demo(self, job: Job, steps: int, delay_s: float) -> None:
        try:
            for i in range(1, steps + 1):
                await asyncio.sleep(delay_s)
                await job.emit("progress", {"fraction": i / steps, "message": f"step {i} of {steps}"})
            await job.emit("done", {"result": {"steps": steps}}, final=True)
        except Exception as exc:  # pragma: no cover - defensive
            await job.emit("error", {"code": "demo_failed", "message": str(exc)}, final=True)

    async def stream(self, job: Job):
        """Yield SSE frames: replay history, then follow until the job finishes."""
        index = 0
        while True:
            async with job.cond:
                await job.cond.wait_for(lambda: index < len(job.events) or job.finished)
                batch = job.events[index:]
                index = len(job.events)
                finished = job.finished
            for ev in batch:
                yield _frame(ev["event"], ev["data"])
            if finished and index >= len(job.events):
                return


def _frame(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
