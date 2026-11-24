"""Background jobs with progress, cancel and resume (ADR-0007).

Jobs run as asyncio tasks in this process and their state is persisted, so a restart
knows what was interrupted. Work is resumable when it checkpoints its own progress
(a match does: every ply is durable), in which case running it again continues.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from duckgambit.domain.errors import DomainError
from duckgambit.domain.events import Event, JobFinished, JobProgressed
from duckgambit.services.errors import ServiceError
from duckgambit.services.events import EventLog, iso
from duckgambit.services.ports import Clock, EngineError, IdGenerator, Store
from duckgambit.services.records import JobRecord

log = logging.getLogger(__name__)


class JobCancelled(Exception):
    """Raised by work when it notices a cancel request."""


class JobHandle:
    def __init__(self, runner: JobRunner, job_id: str) -> None:
        self._runner = runner
        self.job_id = job_id
        self._cancel = asyncio.Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        """Call between units of work; raises if the job should stop."""
        if self._cancel.is_set():
            raise JobCancelled

    async def progress(self, done: int, total: int) -> None:
        await self._runner._progress(self.job_id, done, total)


Work = Callable[[JobHandle], Awaitable[None]]


def stream_of(job_id: str) -> str:
    return f"job:{job_id}"


class JobRunner:
    def __init__(self, store: Store, events: EventLog, clock: Clock, ids: IdGenerator) -> None:
        self._store = store
        self._events = events
        self._clock = clock
        self._ids = ids
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._handles: dict[str, JobHandle] = {}

    def new_id(self) -> str:
        return self._ids.new("job")

    async def recover(self) -> list[str]:
        """At startup: anything still marked as active was interrupted by the last shutdown."""
        interrupted = []
        for job in await asyncio.to_thread(self._store.jobs.list_unfinished):
            await self._save(replace(job, state="interrupted", finished_at=iso(self._clock)))
            interrupted.append(job.id)
        return interrupted

    async def create(self, job_id: str, kind: str, params: dict[str, Any], total: int) -> JobRecord:
        job = JobRecord(job_id, kind, "queued", params, 0, total, iso(self._clock))
        await asyncio.to_thread(self._store.jobs.add, job)
        return job

    async def get(self, job_id: str) -> JobRecord:
        job = await asyncio.to_thread(self._store.jobs.get, job_id)
        if job is None:
            raise ServiceError("job.not_found", "No such job", 404)
        return job

    def is_active(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    async def start(self, job_id: str, work: Work) -> JobRecord:
        """Run (or re-run) the job's work in the background."""
        job = await self.get(job_id)
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            if not job.finished:
                raise ServiceError("job.already_running", "The job is already running", 409)
            # The state is settled but the task is still publishing its last event.
            await asyncio.wait([task])
        if job.state == "succeeded":
            raise ServiceError("job.finished", "The job has already finished", 409)
        job = replace(
            job,
            state="queued",
            started_at=None,
            finished_at=None,
            error_code=None,
            error_detail=None,
        )
        await self._save(job)
        handle = JobHandle(self, job_id)
        self._handles[job_id] = handle
        self._tasks[job_id] = asyncio.create_task(self._run(handle, work), name=f"job-{job_id}")
        return job

    async def _run(self, handle: JobHandle, work: Work) -> None:
        job_id = handle.job_id
        job = replace(await self.get(job_id), state="running", started_at=iso(self._clock))
        await self._save(job)
        state, code, detail = "succeeded", None, None
        try:
            await work(handle)
        except JobCancelled:
            state = "cancelled"
        except asyncio.CancelledError:
            state = "interrupted"
            await asyncio.shield(self._finish(job_id, state, None, None))
            raise
        except (DomainError, EngineError, ServiceError) as exc:
            state, code, detail = "failed", exc.code, exc.message
        except Exception:
            log.exception("Job %s crashed", job_id, extra={"job": job_id})
            state, code, detail = "failed", "job.crashed", "The job stopped unexpectedly"
        await self._finish(job_id, state, code, detail)

    async def _finish(self, job_id: str, state: str, code: str | None, detail: str | None) -> None:
        job = await self.get(job_id)
        job = replace(
            job, state=state, finished_at=iso(self._clock), error_code=code, error_detail=detail
        )
        await self._save_with_event(job, JobFinished(job_id, state, code))
        self._handles.pop(job_id, None)

    async def _progress(self, job_id: str, done: int, total: int) -> None:
        job = replace(await self.get(job_id), done=done, total=total)
        await self._save_with_event(job, JobProgressed(job_id, job.state, done, total))

    async def _save_with_event(self, job: JobRecord, event: Event) -> None:
        """Commit the job's new state and its event together, so a reader that sees the
        state also sees the event (a client polling the job, then reading the stream)."""

        def write() -> None:
            with self._store.atomic():
                self._store.jobs.save(job)
                self._events.append(stream_of(job.id), [event])

        await asyncio.to_thread(write)
        self._events.notify()

    async def _save(self, job: JobRecord) -> None:
        await asyncio.to_thread(self._store.jobs.save, job)

    async def cancel(self, job_id: str) -> JobRecord:
        job = await self.get(job_id)
        handle = self._handles.get(job_id)
        if handle is None or job.finished:
            raise ServiceError("job.not_running", "The job is not running", 409)
        handle._cancel.set()
        return job

    async def wait(self, job_id: str) -> JobRecord:
        """Wait for a running job to settle (used by tests and by shutdown)."""
        task = self._tasks.get(job_id)
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(task)
        return await self.get(job_id)

    async def shutdown(self) -> None:
        """Stop all work. Running jobs become `interrupted` and can be resumed later."""
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
