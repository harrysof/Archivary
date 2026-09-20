"""Logging bridge between the Python logging module and the Qt GUI.

The log panel subscribes to :class:`QtLogHandler`'s signal.  A bounded deque of
recent records is kept in memory so the UI can render the persistent console
immediately on startup instead of only showing records emitted after the panel
was created.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from archivary.constants import LOG_FILE, ensure_dirs

MAX_RECORDS = 5000


class LogEmitter(QObject):
    """Qt signal carrier so the handler itself need not be a QObject."""

    message = Signal(str, int, str, str)


class LogRecordBuffer:
    """Thread-safe(ish) ring buffer of formatted log records for the UI."""

    def __init__(self, maxlen: int = MAX_RECORDS) -> None:
        self._records: deque[dict] = deque(maxlen=maxlen)

    def append(self, text: str, levelno: int, levelname: str, logger_name: str) -> None:
        self._records.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "text": text,
                "levelno": levelno,
                "levelname": levelname,
                "logger": logger_name,
            }
        )

    def records(self) -> list[dict]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


class QtLogHandler(logging.Handler):
    """A logging handler that re-emits records on a Qt signal."""

    def __init__(self, buffer: LogRecordBuffer | None = None) -> None:
        super().__init__()
        self.emitter = LogEmitter()
        self.buffer = buffer or LogRecordBuffer()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
        except Exception:  # pragma: no cover - logging must never raise
            self.handleError(record)
            return
        if record.exc_info and not record.exc_text:
            # Append traceback text to the buffer for the "show details" view.
            text = f"{text}\n{self.formatException(record.exc_info)}"
        self.buffer.append(text, record.levelno, record.levelname, record.name)
        try:
            self.emitter.message.emit(text, record.levelno, record.levelname, record.name)
        except RuntimeError:  # pragma: no cover - Qt object already destroyed
            pass


_LOG_HANDLER: QtLogHandler | None = None


def install_logging(level: int = logging.INFO) -> QtLogHandler:
    """Wire up file + memory logging for the whole application."""
    global _LOG_HANDLER
    if _LOG_HANDLER is not None:
        return _LOG_HANDLER

    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = QtLogHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)

    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover - disk full / permissions
        pass

    # Keep third-party libraries from flooding the panel unless raw mode is on.
    apply_raw_logging(False)

    _LOG_HANDLER = handler
    return handler


def apply_raw_logging(enabled: bool) -> None:
    """Toggle verbose HTTP request/response logging."""
    third_parties = ["urllib3", "requests", "internetarchive", "s3transfer"]
    for name in third_parties:
        logging.getLogger(name).setLevel(logging.DEBUG if enabled else logging.WARNING)


def get_handler() -> QtLogHandler | None:
    return _LOG_HANDLER
