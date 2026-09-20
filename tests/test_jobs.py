import time

from PySide6.QtWidgets import QApplication

from archivary.core.jobs import Job, JobQueue, JobStatus


def _app() -> QApplication:
    # A full QApplication (not just QCoreApplication) is required because the
    # UI smoke tests later in the same process need widget support.
    return QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout=5.0):
    app = _app()
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _counting_work(reporter):
    for i in range(5):
        reporter.checkpoint()
        reporter.report(processed=i + 1, total=5, message=f"step {i}")
        time.sleep(0.01)
    return "ok"


def test_job_runs_to_completion():
    _app()
    queue = JobQueue(max_concurrent=1)
    job = Job("test", "job", _counting_work)
    queue.submit(job)
    assert _wait_until(lambda: job.status == JobStatus.DONE)
    assert job.result == "ok"
    assert job.progress == 100


def test_job_failure_is_friendly():
    _app()
    queue = JobQueue(max_concurrent=1)

    def boom(reporter):
        raise ValueError("bad thing")

    job = Job("test", "failing", boom)
    queue.submit(job)
    assert _wait_until(lambda: job.status == JobStatus.FAILED)
    assert job.error is not None
    assert job.error.title


def test_job_can_be_cancelled():
    _app()
    queue = JobQueue(max_concurrent=1)

    def forever(reporter):
        while True:
            reporter.checkpoint()
            time.sleep(0.01)

    job = Job("test", "cancel me", forever)
    queue.submit(job)
    assert _wait_until(lambda: job.status == JobStatus.RUNNING)
    queue.cancel(job.id)
    assert _wait_until(lambda: job.status == JobStatus.CANCELLED)


def test_concurrency_limit_queues_extra_jobs():
    _app()
    queue = JobQueue(max_concurrent=1)
    job_a = Job("test", "a", _counting_work)
    job_b = Job("test", "b", _counting_work)
    queue.submit(job_a)
    queue.submit(job_b)
    assert _wait_until(lambda: job_a.status == JobStatus.RUNNING)
    assert job_b.status == JobStatus.QUEUED
    assert _wait_until(lambda: job_a.status == JobStatus.DONE)
    assert _wait_until(lambda: job_b.status == JobStatus.DONE)


def test_retry_resets_job():
    _app()
    queue = JobQueue(max_concurrent=1)
    attempts = {"n": 0}

    def flaky(reporter):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("first try fails")
        return "second try"

    job = Job("test", "flaky", flaky)
    queue.submit(job)
    assert _wait_until(lambda: job.status == JobStatus.FAILED)
    queue.retry(job.id)
    assert _wait_until(lambda: job.status == JobStatus.DONE)
    assert job.result == "second try"
