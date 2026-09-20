"""Qt-aware job queue.

Every upload, download, metadata edit or long search becomes a :class:`Job`.
Jobs are scheduled onto lightweight :class:`QThread` workers with a
configurable concurrency limit, so several large transfers can run at once
without ever blocking the GUI thread.  Each job exposes queued / running /
paused / done / failed / cancelled states plus live speed and ETA.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QObject, QThread, Signal

from archivary.core.errors import FriendlyError, describe_exception
from archivary.core.task import JobCancelled, ProgressUpdate, Reporter

log = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)


TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED}

JobFunction = Callable[[Reporter], object]


class Job(QObject):
    """A single unit of work tracked by the :class:`JobQueue`."""

    changed = Signal(object)

    def __init__(
        self,
        kind: str,
        title: str,
        fn: JobFunction,
        *,
        subtitle: str = "",
        total: int | None = None,
        pausable: bool = True,
        metadata: dict | None = None,
    ) -> None:
        super().__init__()
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.title = title
        self.subtitle = subtitle
        self.fn = fn
        self.total = total or 0
        self.processed = 0
        self.message = ""
        self.stage = ""
        self.status = JobStatus.QUEUED
        self.error: FriendlyError | None = None
        self.result: object = None
        self.retry_count = 0
        self.pausable = pausable
        self.metadata = metadata or {}

        self.speed = 0.0  # bytes/second
        self.eta: float | None = None
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None

        self.reporter = Reporter()
        self.reporter.subscribe(self._on_progress)
        self._samples: deque[tuple[float, int]] = deque(maxlen=20)
        self._last_emit = 0.0
        self._emit_interval = 0.05

    # -- progress plumbing -------------------------------------------------
    def _on_progress(self, update: ProgressUpdate) -> None:
        force = update.stage is not None
        if update.total is not None:
            self.total = update.total
        if update.processed is not None:
            self.processed = update.processed
        if update.message is not None:
            self.message = update.message
        if update.stage is not None:
            self.stage = update.stage
        self._recompute_speed()
        self._emit(force=force)

    def _recompute_speed(self) -> None:
        now = time.monotonic()
        self._samples.append((now, self.processed))
        if len(self._samples) < 2:
            return
        t0, p0 = self._samples[0]
        elapsed = now - t0
        if elapsed <= 0:
            return
        delta = self.processed - p0
        # Ignore resets (e.g. a retry restarting the byte count).
        self.speed = max(0.0, delta / elapsed)
        if self.total and self.speed > 0 and self.processed <= self.total:
            self.eta = (self.total - self.processed) / self.speed
        else:
            self.eta = None

    def _emit(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_emit) < self._emit_interval:
            return
        self._last_emit = now
        self.changed.emit(self)

    @property
    def progress(self) -> int:
        if not self.total:
            return 0
        return min(100, int(self.processed * 100 / self.total))

    @property
    def fraction(self) -> float:
        if not self.total:
            return 0.0
        return min(1.0, self.processed / self.total)

    # -- state transitions -------------------------------------------------
    def set_status(self, status: JobStatus, message: str | None = None) -> None:
        self.status = status
        if message is not None:
            self.message = message
        if status == JobStatus.RUNNING and self.started_at is None:
            self.started_at = time.time()
        if status.terminal:
            self.finished_at = time.time()
            if status == JobStatus.DONE:
                self.processed = self.total or self.processed
                self.speed = 0.0
                self.eta = None
        self._emit(force=True)

    def pause(self) -> None:
        if self.pausable and self.status == JobStatus.RUNNING:
            self.reporter.pause()
            self.set_status(JobStatus.PAUSED, "Paused")

    def resume(self) -> None:
        if self.status == JobStatus.PAUSED:
            self.reporter.resume()
            self.set_status(JobStatus.RUNNING, "Resumed")

    def cancel(self) -> None:
        self.reporter.cancel()
        if self.status == JobStatus.QUEUED:
            self.set_status(JobStatus.CANCELLED, "Cancelled")

    def reset(self) -> None:
        self.reporter = Reporter()
        self.reporter.subscribe(self._on_progress)
        self.processed = 0
        self.speed = 0.0
        self.eta = None
        self.error = None
        self.message = ""
        self.stage = ""
        self.result = None
        self.finished_at = None
        self._samples.clear()
        self.set_status(JobStatus.QUEUED, "Queued")

    # -- invoked by the worker --------------------------------------------
    def _start(self) -> None:
        self.set_status(JobStatus.RUNNING, "Starting...")

    def _finish_done(self) -> None:
        self.set_status(JobStatus.DONE, self.message or "Done")

    def _finish_cancelled(self) -> None:
        self.set_status(JobStatus.CANCELLED, "Cancelled")

    def _finish_failed(self, exc: BaseException) -> None:
        self.error = describe_exception(exc)
        log.error("Job %s failed: %s", self.title, exc, exc_info=True)
        self.set_status(JobStatus.FAILED, self.error.title)


class _JobWorker(QThread):
    completed = Signal(str)

    def __init__(self, job: Job, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job = job

    def run(self) -> None:  # noqa: D102 - QThread entry point
        job = self.job
        job._start()
        try:
            job.result = job.fn(job.reporter)
        except JobCancelled:
            job._finish_cancelled()
        except BaseException as exc:  # noqa: BLE001 - surfaced as a friendly error
            job._finish_failed(exc)
        else:
            job._finish_done()
        self.completed.emit(job.id)


class JobQueue(QObject):
    """Schedules jobs, respecting a maximum number of concurrent workers."""

    jobAdded = Signal(object)
    jobChanged = Signal(object)
    jobRemoved = Signal(str)
    queueChanged = Signal()

    def __init__(self, max_concurrent: int = 3, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._max_concurrent = max(1, int(max_concurrent))
        self._jobs: list[Job] = []
        self._pending: list[Job] = []
        self._workers: dict[str, _JobWorker] = {}

    # -- configuration -----------------------------------------------------
    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def set_max_concurrent(self, value: int) -> None:
        self._max_concurrent = max(1, int(value))
        self._schedule()

    @property
    def active_count(self) -> int:
        return len(self._workers)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def job(self, job_id: str) -> Job | None:
        for item in self._jobs:
            if item.id == job_id:
                return item
        return None

    # -- queue operations --------------------------------------------------
    def submit(self, job: Job) -> Job:
        self._jobs.append(job)
        self._pending.append(job)
        self.jobAdded.emit(job)
        self._schedule()
        return job

    def _schedule(self) -> None:
        while self._pending and len(self._workers) < self._max_concurrent:
            job = self._pending.pop(0)
            if job.status in TERMINAL_STATUSES:
                continue
            worker = _JobWorker(job, parent=self)
            worker.completed.connect(self._on_worker_completed)
            self._workers[job.id] = worker
            worker.start()
        self.queueChanged.emit()

    def _on_worker_completed(self, job_id: str) -> None:
        worker = self._workers.pop(job_id, None)
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self._schedule()

    def pause(self, job_id: str) -> None:
        job = self.job(job_id)
        if job:
            job.pause()

    def resume(self, job_id: str) -> None:
        job = self.job(job_id)
        if job:
            job.resume()

    def cancel(self, job_id: str) -> None:
        job = self.job(job_id)
        if not job:
            return
        job.cancel()
        if job.status == JobStatus.QUEUED and job in self._pending:
            self._pending.remove(job)
            self.queueChanged.emit()

    def retry(self, job_id: str) -> None:
        job = self.job(job_id)
        if not job or not job.status.terminal:
            return
        job.retry_count += 1
        job.reset()
        self._pending.append(job)
        self.jobAdded.emit(job)
        self._schedule()

    def remove(self, job_id: str) -> None:
        job = self.job(job_id)
        if not job:
            return
        if job_id in self._workers:
            job.cancel()
            return
        if job in self._pending:
            self._pending.remove(job)
        if job in self._jobs:
            self._jobs.remove(job)
        self.jobRemoved.emit(job_id)
        self.queueChanged.emit()

    def clear_finished(self) -> None:
        for job in list(self._jobs):
            if job.status in TERMINAL_STATUSES and job.id not in self._workers:
                self._jobs.remove(job)
                self.jobRemoved.emit(job.id)
        self.queueChanged.emit()

    def shutdown(self) -> None:
        """Cancel everything and wait for workers to stop (app exit)."""
        for job in self._jobs:
            if job.status in TERMINAL_STATUSES:
                continue
            job.cancel()
            if job in self._pending:
                self._pending.remove(job)
        for worker in list(self._workers.values()):
            worker.wait(5000)
