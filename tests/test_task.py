import time

import pytest

from archivary.core.task import CancelToken, JobCancelled, Reporter


def test_checkpoint_raises_when_cancelled():
    token = CancelToken()
    token.cancel()
    with pytest.raises(JobCancelled):
        token.checkpoint()


def test_pause_blocks_until_resumed():
    token = CancelToken()
    token.pause()
    start = time.monotonic()

    def resume_soon():
        time.sleep(0.15)
        token.resume()

    import threading

    threading.Thread(target=resume_soon, daemon=True).start()
    token.checkpoint()
    assert time.monotonic() - start >= 0.1


def test_cancel_unblocks_paused():
    token = CancelToken()
    token.pause()
    import threading

    threading.Thread(target=lambda: (time.sleep(0.1), token.cancel()), daemon=True).start()
    with pytest.raises(JobCancelled):
        token.checkpoint()


def test_reporter_notifies_subscribers():
    reporter = Reporter()
    updates = []
    reporter.subscribe(updates.append)
    reporter.report(processed=5, total=10, message="half")
    assert updates[-1].processed == 5
    assert updates[-1].total == 10


def test_reporter_survives_bad_listener():
    reporter = Reporter()

    def boom(update):
        raise ValueError("nope")

    reporter.subscribe(boom)
    reporter.report(processed=1)  # must not raise
    assert reporter.last.processed == 1
