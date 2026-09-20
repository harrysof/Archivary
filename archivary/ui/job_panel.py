"""The persistent transfer queue panel.

Lives in a draggable splitter at the bottom of the main window and shows every
queued, running and completed transfer regardless of which tab is open.  Rows
are deliberately compact so a long history stays readable, and each row only
shows the actions that apply to its current state.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from archivary.core.jobs import Job, JobQueue, JobStatus
from archivary.services.ia_service import human_eta, human_size, human_speed

STATUS_TEXT = {
    JobStatus.QUEUED: "Queued",
    JobStatus.RUNNING: "Running",
    JobStatus.PAUSED: "Paused",
    JobStatus.RETRYING: "Retrying",
    JobStatus.DONE: "Done",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
}

STATUS_OBJECT = {
    JobStatus.DONE: "Status_ok",
    JobStatus.FAILED: "Status_err",
    JobStatus.CANCELLED: "Status_warn",
    JobStatus.PAUSED: "Status_warn",
}

KIND_ICON = {
    "upload": "UP",
    "download": "DL",
    "search": "SR",
    "metadata": "MD",
    "delete": "DEL",
    "tasks": "TSK",
    "account": "ACC",
}

FILTER_OPTIONS = ("All", "Active only", "Problems")


class ElidedLabel(QLabel):
    """A label that shortens its text with an ellipsis instead of clipping."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        self._full = text
        super().setText(text)
        self.setToolTip(text)

    def full_text(self) -> str:
        return self._full

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, self.width()
        )
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), int(self.alignment()), elided)
        painter.end()


def _mini_button(text: str, slot) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Mini")
    button.setFixedHeight(22)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(slot)
    return button


class JobRow(QFrame):
    """A single, compact transfer row."""

    def __init__(self, job: Job, queue: JobQueue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.queue = queue
        self.setObjectName("JobCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        kind = QLabel(KIND_ICON.get(job.kind, job.kind[:3].upper()))
        kind.setObjectName("Muted")
        kind.setFixedWidth(30)
        kind.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(kind)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(1)
        self.title = ElidedLabel(job.title)
        self.title.setObjectName("JobTitle")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail = ElidedLabel("")
        self.detail.setObjectName("Muted")
        font = self.detail.font()
        font.setPointSizeF(max(7.5, font.pointSizeF() - 1.0))
        self.detail.setFont(font)
        center.addWidget(self.title)
        center.addWidget(self.detail)
        layout.addLayout(center, 1)

        self.bar = QProgressBar()
        self.bar.setObjectName("JobBar")
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")
        self.bar.setFixedHeight(16)
        self.bar.setFixedWidth(160)
        self.bar.setRange(0, 1000)
        layout.addWidget(self.bar)

        self.status = QLabel()
        self.status.setFixedWidth(72)
        self.status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.status)

        self.pause_button = _mini_button("Pause", self._toggle_pause)
        self.cancel_button = _mini_button("Cancel", lambda: self.queue.cancel(self.job.id))
        self.retry_button = _mini_button("Retry", lambda: self.queue.retry(self.job.id))
        self.remove_button = _mini_button("Remove", lambda: self.queue.remove(self.job.id))
        for button in (
            self.pause_button,
            self.cancel_button,
            self.retry_button,
            self.remove_button,
        ):
            layout.addWidget(button)

        job.changed.connect(self.refresh)
        self.refresh(job)

    def _toggle_pause(self) -> None:
        if self.job.status == JobStatus.PAUSED:
            self.queue.resume(self.job.id)
        else:
            self.queue.pause(self.job.id)

    def refresh(self, job: Job) -> None:
        if job.total:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(job.fraction * 1000))
        elif job.status == JobStatus.RUNNING:
            self.bar.setRange(0, 0)  # indeterminate
        else:
            self.bar.setRange(0, 1000)
            self.bar.setValue(0)

        status_text = STATUS_TEXT.get(job.status, job.status.value)
        if job.status == JobStatus.FAILED and job.error:
            status_text = job.error.title
        self.status.setText(status_text)
        self.status.setObjectName(STATUS_OBJECT.get(job.status, ""))
        self.status.setToolTip(job.error.message if job.error else status_text)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        message = job.message or ""
        if job.total:
            detail = (
                f"{human_size(job.processed)} / {human_size(job.total)}"
                f"  -  {human_speed(job.speed)}  -  ETA {human_eta(job.eta)}"
            )
            if message:
                detail = f"{message}  -  {detail}"
        else:
            detail = message
        if job.subtitle and not job.total:
            detail = f"{job.subtitle}  -  {detail}" if detail else job.subtitle
        self.detail.setText(detail)

        if job.status == JobStatus.PAUSED:
            self.pause_button.setText("Resume")
        else:
            self.pause_button.setText("Pause")

        running = job.status in (JobStatus.RUNNING, JobStatus.PAUSED)
        queued = job.status == JobStatus.QUEUED
        failed = job.status in (JobStatus.FAILED, JobStatus.CANCELLED)
        done = job.status == JobStatus.DONE

        self.pause_button.setVisible(job.pausable and running)
        self.cancel_button.setVisible(queued or running)
        self.retry_button.setVisible(failed)
        self.remove_button.setVisible(done or failed)


class JobPanel(QWidget):
    """Scrollable list of all jobs managed by the :class:`JobQueue`."""

    def __init__(self, queue: JobQueue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.queue = queue
        self._rows: dict[str, JobRow] = {}
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.summary = QLabel("No jobs")
        self.summary.setObjectName("Muted")
        toolbar.addWidget(self.summary, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(FILTER_OPTIONS))
        self.filter_combo.setToolTip("Choose which transfers are listed below.")
        self.filter_combo.currentTextChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.filter_combo)

        self.autoscroll_check = QCheckBox("Follow newest")
        self.autoscroll_check.setChecked(True)
        toolbar.addWidget(self.autoscroll_check)

        clear_button = QPushButton("Clear finished")
        clear_button.clicked.connect(self.queue.clear_finished)
        toolbar.addWidget(clear_button)
        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(4)
        self._container_layout.addStretch(1)
        self.scroll.setWidget(self._container)
        layout.addWidget(self.scroll, 1)

        queue.jobAdded.connect(self._on_job_added)
        queue.jobRemoved.connect(self._on_job_removed)
        queue.queueChanged.connect(self._update_summary)
        for job in queue.jobs():
            self._on_job_added(job)

    # -- row management ----------------------------------------------------
    def _on_job_added(self, job: Job) -> None:
        if job.id in self._rows:
            self._apply_filter()
            self._maybe_scroll()
            return
        row = JobRow(job, self.queue)
        self._rows[job.id] = row
        self._container_layout.insertWidget(self._container_layout.count() - 1, row)
        self._apply_filter()
        if self.autoscroll_check.isChecked():
            self._maybe_scroll()

    def _on_job_removed(self, job_id: str) -> None:
        row = self._rows.pop(job_id, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self._update_summary()

    def _matches_filter(self, job: Job) -> bool:
        choice = self.filter_combo.currentText()
        if choice == "Active only":
            return job.status in (
                JobStatus.QUEUED,
                JobStatus.RUNNING,
                JobStatus.PAUSED,
                JobStatus.RETRYING,
            )
        if choice == "Problems":
            return job.status in (JobStatus.FAILED, JobStatus.CANCELLED)
        return True

    def _apply_filter(self) -> None:
        for job_id, row in self._rows.items():
            job = self.queue.job(job_id)
            if job is not None:
                row.setVisible(self._matches_filter(job))
        self._update_summary()

    def _maybe_scroll(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_summary(self) -> None:
        jobs = self.queue.jobs()
        running = sum(1 for j in jobs if j.status == JobStatus.RUNNING)
        queued = sum(1 for j in jobs if j.status == JobStatus.QUEUED)
        paused = sum(1 for j in jobs if j.status == JobStatus.PAUSED)
        failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
        done = sum(1 for j in jobs if j.status == JobStatus.DONE)
        if not jobs:
            self.summary.setText("No transfers yet")
            return
        parts = [f"{running} running", f"{queued} queued"]
        if paused:
            parts.append(f"{paused} paused")
        if failed:
            parts.append(f"{failed} failed")
        parts.append(f"{done} done")
        self.summary.setText("   -   ".join(parts))
