"""Application bootstrap: wires logging, theme, services and the main window."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from archivary import __app_name__, __org_name__, __version__
from archivary.constants import ensure_dirs
from archivary.core.credentials import CredentialStore
from archivary.core.jobs import JobQueue
from archivary.core.logbus import apply_raw_logging, install_logging
from archivary.core.settings import SettingsStore
from archivary.services.ia_service import IAService
from archivary.ui.context import AppContext
from archivary.ui.main_window import MainWindow
from archivary.ui.theme import DARK, LIGHT, apply_theme
from archivary.ui.widgets import logo_icon

log = logging.getLogger(__name__)


def _set_windows_app_user_model_id() -> None:
    """Give the process its own taskbar identity on Windows.

    Without an explicit AppUserModelID the shell groups the window under the
    interpreter (``python.exe``/``pythonw.exe``) and shows *its* icon in the
    taskbar, ignoring the window icon we set on the ``QApplication``.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"{__org_name__}.{__app_name__}"
        )
    except Exception:  # pragma: no cover - restricted environments
        log.debug("Could not set Windows AppUserModelID", exc_info=True)


def build_context() -> AppContext:
    store = CredentialStore()
    settings = SettingsStore()
    service = IAService(store.active_profile())
    queue = JobQueue(max_concurrent=int(settings.get("max_concurrent_jobs", 3)))
    return AppContext(store, settings, service, queue)


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setOrganizationName(__org_name__)
    app.setApplicationVersion(__version__)
    return app


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    install_logging()
    _set_windows_app_user_model_id()
    app = create_application(argv)

    context = build_context()
    apply_raw_logging(bool(context.settings.get("raw_logging")))
    theme = apply_theme(app, context.settings.get("theme", "system"))
    app.setWindowIcon(logo_icon((DARK if theme == "dark" else LIGHT)["text"]))

    window = MainWindow(context)
    window.show()
    log.info("Archivary %s started", __version__)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
