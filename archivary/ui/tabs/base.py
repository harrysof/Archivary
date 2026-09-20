"""Base class for feature tabs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget

from archivary.core.jobs import Job, JobStatus
from archivary.ui.context import AppContext


class BaseTab(QWidget):
    """Common behaviour for the sidebar pages."""

    #: Human-readable name used in the sidebar.
    title = "Tab"

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self._built = False
        self.build()
        self._built = True

    def build(self) -> None:
        """Construct the tab's widgets. Subclasses must implement."""

    def on_profile_changed(self) -> None:
        """Called when the active account changes."""

    def on_shown(self) -> None:
        """Called every time the tab becomes visible."""

    # -- job helpers -------------------------------------------------------
    def watch_job(
        self,
        job: Job,
        on_done: Callable[[Any], None] | None = None,
        *,
        announce_failure: bool = True,
        announce_success: tuple[str, str] | None = None,
    ) -> None:
        """Invoke ``on_done(job.result)`` once when ``job`` finishes.

        Failures raise a friendly dialog unless ``announce_failure`` is False.
        """
        state = {"handled": False}

        def handler(current: Job) -> None:
            if state["handled"]:
                return
            if current.status == JobStatus.DONE:
                state["handled"] = True
                if announce_success:
                    self.ctx.notify_info(*announce_success)
                if on_done is not None:
                    on_done(current.result)
            elif current.status == JobStatus.FAILED:
                state["handled"] = True
                if announce_failure and current.error is not None:
                    self.ctx.notify_error(
                        current.error.title, current.error.message, current.error.detail
                    )

        job.changed.connect(handler)
