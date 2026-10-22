

def test_finished_jobs_are_forgotten_after_a_while_but_running_ones_never():
    import asyncio
    from picturebook_sidecar.jobs import JobManager

    async def go():
        m = JobManager()
        running = m.create()
        for _ in range(120):
            j = m.create(); await j.emit("done", {}, final=True)
        m.create()                                                  # triggers one more cleanup
        assert running.id in m.jobs
        assert sum(1 for j in m.jobs.values() if j.finished) <= JobManager.KEEP_FINISHED
    asyncio.run(go())
