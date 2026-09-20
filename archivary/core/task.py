"""GUI-independent task primitives: cancellation, pausing and progress.

The service layer (and therefore anything that calls it) talks to a
:class:`Reporter`.  This keeps the service modules free of any PySide6 import
while still giving the Qt job queue everything it needs to drive progress bars,
pause/resume and cancellation.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


class JobCancelled(Exception):
    """Raised inside a running task when the user cancels it."""


class CancelToken:
    """A cooperative cancellation and pause token.

    Long-running loops call :meth:`checkpoint` at safe boundaries.  While paused
    the call blocks; on cancel it raises :class:`JobCancelled`.
    """

    def __init__(self) -> None:
        self._cancel = threading.Event()
        self._paused = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def paused(self) -> bool:
        return self._paused.is_set() and not self._cancel.is_set()

    def cancel(self) -> None:
        self._paused.clear()
        self._cancel.set()

    def pause(self) -> None:
        if not self._cancel.is_set():
            self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def checkpoint(self) -> None:
        """Block while paused, raise if cancelled, otherwise return at once."""
        while self._paused.is_set() and not self._cancel.is_set():
            time.sleep(0.1)
        if self._cancel.is_set():
            raise JobCancelled()


@dataclass
class ProgressUpdate:
    """A snapshot of progress for a single job or file."""

    processed: int | None = None
    total: int | None = None
    message: str | None = None
    stage: str | None = None


ProgressCallback = Callable[[ProgressUpdate], None]


class Reporter:
    """Collects progress updates and drives a :class:`CancelToken`.

    Service functions accept a ``Reporter`` instance.  Callers that do not care
    about progress can pass ``None``; a private no-op reporter is created then.
    """

    def __init__(self) -> None:
        self.token = CancelToken()
        self._callbacks: list[ProgressCallback] = []
        self.last = ProgressUpdate()

    # -- subscription ------------------------------------------------------
    def subscribe(self, callback: ProgressCallback) -> None:
        self._callbacks.append(callback)

    def unsubscribe(self, callback: ProgressCallback) -> None:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    # -- reporting ---------------------------------------------------------
    def report(
        self,
        processed: int | None = None,
        total: int | None = None,
        message: str | None = None,
        stage: str | None = None,
    ) -> None:
        self.last = ProgressUpdate(processed, total, message, stage)
        for callback in list(self._callbacks):
            try:
                callback(self.last)
            except Exception:  # pragma: no cover - a listener must not kill the task
                pass

    @property
    def cancelled(self) -> bool:
        return self.token.cancelled

    @property
    def paused(self) -> bool:
        return self.token.paused

    def checkpoint(self) -> None:
        self.token.checkpoint()

    def cancel(self) -> None:
        self.token.cancel()

    def pause(self) -> None:
        self.token.pause()

    def resume(self) -> None:
        self.token.resume()


class NullReporter(Reporter):
    """Reporter used when a caller does not need progress reporting."""


def reporter_or_null(reporter: Reporter | None) -> Reporter:
    return reporter if reporter is not None else NullReporter()
