"""Shared application context handed to every tab.

Bundles the credential store, settings, service, job queue and a reference to
the main window so tabs can navigate or surface errors without importing each
other.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from archivary.core.credentials import CredentialStore, Profile
from archivary.core.jobs import Job, JobFunction, JobQueue
from archivary.core.settings import SettingsStore
from archivary.services.ia_service import IAService

if TYPE_CHECKING:  # pragma: no cover
    from archivary.ui.main_window import MainWindow


class AppContext:
    def __init__(
        self,
        store: CredentialStore,
        settings: SettingsStore,
        service: IAService,
        queue: JobQueue,
    ) -> None:
        self.store = store
        self.settings = settings
        self.service = service
        self.queue = queue
        self.window: "MainWindow | None" = None

    # -- profile -----------------------------------------------------------
    @property
    def active_profile(self) -> Profile | None:
        return self.store.active_profile()

    def set_active_profile(self, name: str) -> None:
        self.store.set_active(name)
        self.service.set_profile(self.store.get_profile(name))
        if self.window is not None:
            self.window.on_profile_changed()

    def reload_service(self) -> None:
        self.service.set_profile(self.store.active_profile())
        if self.window is not None:
            self.window.on_profile_changed()

    def require_profile(self) -> Profile | None:
        profile = self.active_profile
        if profile is None or not profile.is_complete:
            self.notify_warning(
                "No account selected",
                "Add or select an Internet Archive account in Settings before "
                "performing this action.",
            )
            return None
        return profile

    # -- jobs --------------------------------------------------------------
    def submit(
        self,
        kind: str,
        title: str,
        fn: JobFunction,
        *,
        subtitle: str = "",
        total: int | None = None,
        pausable: bool = True,
    ) -> Job:
        job = Job(
            kind,
            title,
            fn,
            subtitle=subtitle,
            total=total,
            pausable=pausable,
        )
        self.queue.submit(job)
        return job

    # -- notifications -----------------------------------------------------
    def notify_info(self, title: str, message: str) -> None:
        QMessageBox.information(self.window, title, message)

    def notify_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self.window, title, message)

    def notify_error(self, title: str, message: str, details: str = "") -> None:
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(message)
        if details:
            box.setDetailedText(details)
        if self.window is not None:
            show_log = box.addButton("Show in console", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is show_log:
                self.window.show_log_panel()
        else:  # pragma: no cover
            box.exec()

    def run_async(self, description: str, fn: Callable[[], object]) -> Job:
        """Run ``fn`` as a non-pausable job (used for quick account calls)."""
        return self.submit("account", description, lambda reporter: fn(), pausable=False)
