"""Tasks tab: the catalog task queue for the user's items."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivary.services.ia_service import friendly_url_to_identifier
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import PageHeader

STATUS_COLORS = {
    "running": "#4c9aff",
    "queued": "#d29922",
    "paused": "#d29922",
    "error": "#e5534b",
    "done": "#3fb950",
}


class TaskLogDialog(QDialog):
    def __init__(self, task_id: str, log_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Task log {task_id}")
        self.resize(820, 520)
        layout = QVBoxLayout(self)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setPlainText(log_text or "(empty)")
        layout.addWidget(self.view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class TasksTab(BaseTab):
    title = "Tasks"

    def build(self) -> None:
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Tasks",
                "Catalog tasks such as derive processing. Leave the identifier blank "
                "to see tasks for all of your uploads.",
            )
        )
        outer.addWidget(self._build_controls())
        outer.addWidget(self._build_table(), 1)

        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self._auto_refresh)

    def _build_controls(self) -> QGroupBox:
        group = QGroupBox("Filters")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("Identifier"))
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText("(optional) item identifier")
        self.identifier_edit.returnPressed.connect(self._refresh)
        layout.addWidget(self.identifier_edit, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh)
        layout.addWidget(self.refresh_button)
        self.auto_check = QCheckBox("Auto-refresh")
        self.auto_check.toggled.connect(self._on_auto_toggled)
        layout.addWidget(self.auto_check)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 600)
        self.interval_spin.setValue(15)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.valueChanged.connect(
            lambda value: self.timer.setInterval(value * 1000)
        )
        layout.addWidget(self.interval_spin)
        return group

    def _build_table(self) -> QGroupBox:
        group = QGroupBox("Tasks")
        layout = QVBoxLayout(group)
        self.summary = QLabel("No tasks loaded.")
        self.summary.setObjectName("Muted")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Task ID", "Identifier", "Command", "Status", "Submitted", "Server"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(lambda _: self._show_log())
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        log_button = QPushButton("View task log")
        log_button.clicked.connect(self._show_log)
        row.addWidget(log_button)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    # -- loading -----------------------------------------------------------
    def _on_auto_toggled(self, enabled: bool) -> None:
        if enabled:
            self.timer.start()
        else:
            self.timer.stop()

    def _auto_refresh(self) -> None:
        if not self._loading and self.isVisible():
            self._refresh(silent=True)

    def _refresh(self, silent: bool = False) -> None:
        if self._loading:
            return
        if not self.ctx.active_profile:
            if not silent:
                self.ctx.notify_warning(
                    "No account", "Select an account before loading tasks."
                )
            return
        identifier = friendly_url_to_identifier(self.identifier_edit.text())
        self._loading = True
        if not silent:
            self.summary.setText("Loading tasks...")

        def work(reporter):
            return self.ctx.service.get_tasks(identifier, reporter=reporter)

        job = self.ctx.submit("tasks", "Load catalog tasks", work, pausable=False)
        self.watch_job(job, self._populate, announce_failure=not silent)
        job.changed.connect(self._on_job_done)

    def _on_job_done(self, job) -> None:
        from archivary.core.jobs import JobStatus

        if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
            self._loading = False

    def _populate(self, rows: list[dict]) -> None:
        self.table.setRowCount(0)
        for task in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            self.table.setItem(index, 0, QTableWidgetItem(str(task.get("task_id", ""))))
            self.table.setItem(index, 1, QTableWidgetItem(str(task.get("identifier", ""))))
            self.table.setItem(index, 2, QTableWidgetItem(str(task.get("cmd", ""))))
            status = str(task.get("status", ""))
            status_item = QTableWidgetItem(status or "done")
            color = STATUS_COLORS.get(status)
            if color:
                from PySide6.QtGui import QColor

                status_item.setForeground(QColor(color))
            self.table.setItem(index, 3, status_item)
            self.table.setItem(index, 4, QTableWidgetItem(str(task.get("submittime", ""))))
            self.table.setItem(index, 5, QTableWidgetItem(str(task.get("server", ""))))
        self.summary.setText(f"{len(rows)} task(s). Double-click to view a task log.")

    def _show_log(self) -> None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            self.ctx.notify_warning("No task selected", "Select a task first.")
            return
        row = selection[0].row()
        task_id_item = self.table.item(row, 0)
        if not task_id_item or not task_id_item.text():
            return
        task_id = task_id_item.text()

        def work(reporter):
            reporter.report(message="Fetching task log", stage="tasks")
            return self.ctx.service.get_task_log(task_id)

        job = self.ctx.submit("tasks", f"Load log for task {task_id}", work, pausable=False)

        def done(log_text: str) -> None:
            dialog = TaskLogDialog(task_id, log_text, self)
            dialog.exec()

        self.watch_job(job, done)

    def on_profile_changed(self) -> None:
        if self._built and self.isVisible():
            self._refresh(silent=True)

    def on_shown(self) -> None:
        self._refresh(silent=True)
