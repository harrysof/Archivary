"""The persistent raw log console.

Kept separate from the friendly progress UI: this panel shows the underlying
request/response chatter and tracebacks for troubleshooting, with a filter by
severity and a "raw logging" toggle that raises third-party HTTP loggers to
DEBUG.
"""

from __future__ import annotations

import html
import logging

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from archivary.core import logbus

LEVEL_ORDER = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


class LogPanel(QWidget):
    """Collapsible console view of the application log."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[dict] = []
        self._min_level = logging.INFO

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Level"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Debug", "Info", "Warning", "Error"])
        self.level_combo.setCurrentText("Info")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self.level_combo)

        self.raw_check = QCheckBox("Raw HTTP logging")
        self.raw_check.toggled.connect(self._on_raw_toggled)
        toolbar.addWidget(self.raw_check)

        self.autoscroll_check = QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        toolbar.addWidget(self.autoscroll_check)

        toolbar.addStretch(1)
        copy_button = QPushButton("Copy all")
        copy_button.clicked.connect(self._copy_all)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear)
        self.details_button = QPushButton("Show details")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        toolbar.addWidget(self.details_button)
        toolbar.addWidget(copy_button)
        toolbar.addWidget(clear_button)
        layout.addLayout(toolbar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(logbus.MAX_RECORDS)
        font = QFont("Cascadia Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.view.setFont(font)
        layout.addWidget(self.view, 1)

        self._connect_handler()

    # -- wiring ------------------------------------------------------------
    def _connect_handler(self) -> None:
        handler = logbus.get_handler()
        if handler is not None:
            handler.emitter.message.connect(self._on_message)
            for record in handler.buffer.records():
                self._records.append(record)
            self._render()

    def _on_message(self, text: str, levelno: int, levelname: str, logger: str) -> None:
        self._records.append(
            {
                "time": "",
                "text": text,
                "levelno": levelno,
                "levelname": levelname,
                "logger": logger,
            }
        )
        if levelno >= self._min_level:
            self._append_html(text, levelno)
            if self.autoscroll_check.isChecked():
                self.view.verticalScrollBar().setValue(
                    self.view.verticalScrollBar().maximum()
                )

    # -- rendering ---------------------------------------------------------
    def _render(self) -> None:
        self.view.clear()
        for record in self._records:
            if record["levelno"] >= self._min_level:
                self._append_html(record["text"], record["levelno"])

    def _append_html(self, text: str, levelno: int) -> None:
        color = self._color_for(levelno)
        self.view.appendHtml(
            f'<span style="color:{color}; white-space:pre-wrap;">'
            f"{html.escape(text)}</span>"
        )

    @staticmethod
    def _color_for(levelno: int) -> str:
        if levelno >= logging.ERROR:
            return "#e5534b"
        if levelno >= logging.WARNING:
            return "#d29922"
        if levelno >= logging.INFO:
            return "#4c9aff"
        return "#9aa0a6"

    # -- actions -----------------------------------------------------------
    def _on_level_changed(self, text: str) -> None:
        self._min_level = LEVEL_ORDER.get(text.upper(), logging.INFO)
        self._render()

    def _on_raw_toggled(self, enabled: bool) -> None:
        logbus.apply_raw_logging(enabled)

    def _toggle_details(self, shown: bool) -> None:
        self.details_button.setText("Hide details" if shown else "Show details")
        if shown:
            self.autoscroll_check.setChecked(True)

    def _copy_all(self) -> None:
        self.view.selectAll()
        self.view.copy()

    def clear(self) -> None:
        self._records.clear()
        self.view.clear()

    def focus_details(self) -> None:
        """Called by error dialogs' 'show details' affordance."""
        self.details_button.setChecked(True)
        self.show()
        self.raise_()
