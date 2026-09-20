"""The Archivary main window: sidebar navigation plus a resizable bottom panel."""

from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from archivary import __app_name__, __version__
from archivary.constants import CONFIG_DIR, ensure_dirs
from archivary.ui.context import AppContext
from archivary.ui.job_panel import JobPanel
from archivary.ui.log_panel import LogPanel
from archivary.ui.tabs.download_tab import DownloadTab
from archivary.ui.tabs.list_tab import ListTab
from archivary.ui.tabs.metadata_tab import MetadataTab
from archivary.ui.tabs.search_tab import SearchTab
from archivary.ui.tabs.settings_tab import SettingsTab
from archivary.ui.tabs.tasks_tab import TasksTab
from archivary.ui.tabs.upload_tab import UploadTab
from archivary.ui.theme import DARK, LIGHT, apply_theme, resolve_theme
from archivary.ui.widgets import logo_icon, logo_pixmap

log = logging.getLogger(__name__)

TAB_ORDER = [
    ("upload", "Upload", UploadTab),
    ("download", "Download", DownloadTab),
    ("search", "Search", SearchTab),
    ("metadata", "Metadata", MetadataTab),
    ("list", "List & Delete", ListTab),
    ("tasks", "Tasks", TasksTab),
    ("settings", "Settings", SettingsTab),
]

DEFAULT_SPLITTER_SIZES = [520, 340]
TRANSFERS_TAB = 0
CONSOLE_TAB = 1


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.ctx = context
        context.window = self
        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(1220, 860)
        self.setMinimumSize(900, 620)

        self._tabs: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}

        self._theme = resolve_theme(
            QApplication.instance(), self.ctx.settings.get("theme", "system")
        )
        self._build_ui()
        self._build_menu()
        self._apply_brand()
        self._restore_geometry()
        self.ctx.queue.jobAdded.connect(self._on_job_submitted)
        self.on_profile_changed()

    # -- construction ------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self._build_bottom_panel())
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes(DEFAULT_SPLITTER_SIZES)

        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        for key, label, factory in TAB_ORDER:
            tab = factory(self.ctx)
            self._tabs[key] = tab
            self.stack.addWidget(tab)
            self._add_nav_button(key, label)
        self.switch_to("upload")

    def _build_bottom_panel(self) -> QWidget:
        self.job_panel = JobPanel(self.ctx.queue)
        self.log_panel = LogPanel()

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setDocumentMode(True)
        self.bottom_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.bottom_tabs.addTab(self.job_panel, "Transfers")
        self.bottom_tabs.addTab(self.log_panel, "Console")
        # A real minimum stops the central stack from squeezing the panel away.
        self.bottom_tabs.setMinimumHeight(200)
        return self.bottom_tabs

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(196)
        sidebar.setObjectName("Sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(4)

        brand_row = QWidget()
        brand_layout = QHBoxLayout(brand_row)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)

        self._logo_label = QLabel()
        self._logo_label.setFixedSize(32, 32)
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(self._logo_label, 0, Qt.AlignmentFlag.AlignVCenter)

        brand = QLabel(__app_name__)
        brand.setObjectName("PageTitle")
        brand_layout.addWidget(brand, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(brand_row)

        tagline = QLabel("Internet Archive desktop")
        tagline.setObjectName("Muted")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)
        layout.addSpacing(14)
        self._sidebar_layout = layout
        # Navigation buttons are inserted at this index (just below the brand);
        # the stretch and account details stay pinned to the bottom.
        self._nav_index = layout.count()

        layout.addStretch(1)

        self.account_label = QLabel("No account")
        self.account_label.setObjectName("Muted")
        self.account_label.setWordWrap(True)
        layout.addWidget(QLabel("Account:"))
        layout.addWidget(self.account_label)
        return sidebar

    def _add_nav_button(self, key: str, label: str) -> None:
        button = QPushButton(label)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _=False, k=key: self.switch_to(k))
        self._button_group.addButton(button)
        self._nav_buttons[key] = button
        self._sidebar_layout.insertWidget(self._nav_index, button)
        self._nav_index += 1

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")
        self.panel_toggle = QAction("Transfers && Console panel", self, checkable=True)
        self.panel_toggle.setChecked(True)
        self.panel_toggle.setShortcut(QKeySequence("Ctrl+J"))
        self.panel_toggle.toggled.connect(self.set_bottom_panel_visible)
        view_menu.addAction(self.panel_toggle)

        transfers_action = QAction("Transfers", self)
        transfers_action.setShortcut(QKeySequence("Ctrl+1"))
        transfers_action.triggered.connect(self.show_job_panel)
        view_menu.addAction(transfers_action)

        console_action = QAction("Console", self)
        console_action.setShortcut(QKeySequence("Ctrl+2"))
        console_action.triggered.connect(self.show_log_panel)
        view_menu.addAction(console_action)

        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for mode in ("system", "dark", "light"):
            action = QAction(mode.capitalize(), self, checkable=True)
            action.setChecked(self.ctx.settings.get("theme") == mode)
            action.triggered.connect(lambda _=False, m=mode: self.set_theme(m))
            self._theme_group.addAction(action)
            theme_menu.addAction(action)

        account_menu = menu_bar.addMenu("&Account")
        manage_action = QAction("Manage accounts...", self)
        manage_action.triggered.connect(lambda: self.switch_to("settings"))
        test_action = QAction("Test connection...", self)
        test_action.triggered.connect(self._test_connection)
        account_menu.addAction(manage_action)
        account_menu.addAction(test_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction(f"About {__app_name__}", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        status = self.statusBar()
        self._status_logo = QLabel()
        self._status_logo.setFixedSize(16, 16)
        status.addPermanentWidget(self._status_logo)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("Muted")
        status.addPermanentWidget(version_label)
        status.showMessage("Ready")

    # -- bottom panel ------------------------------------------------------
    def set_bottom_panel_visible(self, visible: bool) -> None:
        self.bottom_tabs.setVisible(visible)
        if self.panel_toggle.isChecked() != visible:
            self.panel_toggle.setChecked(visible)

    def show_job_panel(self) -> None:
        self.set_bottom_panel_visible(True)
        self.bottom_tabs.setCurrentIndex(TRANSFERS_TAB)

    def show_log_panel(self) -> None:
        self.set_bottom_panel_visible(True)
        self.bottom_tabs.setCurrentIndex(CONSOLE_TAB)
        self.log_panel.focus_details()

    def _on_job_submitted(self, job) -> None:
        # Make sure the panel is on screen when work starts, without stealing
        # the tab if the user is deliberately reading the console.
        if job.kind in ("upload", "download", "delete"):
            if not self.bottom_tabs.isVisible():
                self.show_job_panel()

    # -- navigation --------------------------------------------------------
    def switch_to(self, key: str) -> None:
        if key not in self._tabs:
            return
        self.stack.setCurrentWidget(self._tabs[key])
        button = self._nav_buttons.get(key)
        if button is not None and not button.isChecked():
            button.setChecked(True)
        tab = self._tabs[key]
        if hasattr(tab, "on_shown"):
            tab.on_shown()

    def open_download(self, identifier: str) -> None:
        self.switch_to("download")
        tab = self._tabs["download"]
        if hasattr(tab, "prefill"):
            tab.prefill(identifier)

    def open_metadata(self, identifier: str) -> None:
        self.switch_to("metadata")
        tab = self._tabs["metadata"]
        if hasattr(tab, "prefill"):
            tab.prefill(identifier)

    def open_list(self, identifier: str) -> None:
        self.switch_to("list")
        tab = self._tabs["list"]
        if hasattr(tab, "prefill"):
            tab.prefill(identifier)

    # -- theme / profile ---------------------------------------------------
    def _apply_brand(self) -> None:
        color = (DARK if self._theme == "dark" else LIGHT)["text"]
        icon = logo_icon(color)
        self.setWindowIcon(icon)
        self._logo_label.setPixmap(logo_pixmap(32, color))
        self._status_logo.setPixmap(logo_pixmap(16, color))

    def set_theme(self, mode: str) -> None:
        self.ctx.settings.set("theme", mode)
        self._theme = apply_theme(QApplication.instance(), mode)
        self._apply_brand()

    def on_profile_changed(self) -> None:
        profile = self.ctx.active_profile
        if profile and profile.is_complete:
            name = profile.screenname or profile.email or profile.name
            self.account_label.setText(name)
            self.account_label.setToolTip(f"Profile: {profile.name}")
            self.statusBar().showMessage(f"Signed in as {name}")
        else:
            self.account_label.setText("No account")
            self.statusBar().showMessage("No account selected")
        for tab in self._tabs.values():
            if hasattr(tab, "on_profile_changed"):
                tab.on_profile_changed()

    # -- misc --------------------------------------------------------------
    def _test_connection(self) -> None:
        profile = self.ctx.require_profile()
        if not profile:
            return
        self.ctx.submit(
            "account",
            "Test connection",
            lambda reporter: self._report_connection(),
            pausable=False,
        )

    def _report_connection(self) -> dict:
        info = self.ctx.service.test_connection()
        username = info.get("username") or info.get("screenname") or "unknown"
        self.statusBar().showMessage(f"Connected as {username}", 8000)
        return info

    def _show_about(self) -> None:
        self.ctx.notify_info(
            f"About {__app_name__}",
            f"{__app_name__} {__version__}\n\n"
            "A cross-platform desktop interface for the Internet Archive, "
            "built on the official internetarchive Python library.",
        )

    def _restore_geometry(self) -> None:
        saved = self.ctx.settings.get("window_geometry")
        if saved:
            try:
                self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
            except Exception:  # noqa: BLE001
                pass
        sizes = self.ctx.settings.get("bottom_splitter_sizes")
        if isinstance(sizes, list) and len(sizes) == 2 and all(sizes):
            self._pending_splitter_sizes = [int(sizes[0]), int(sizes[1])]
        else:
            self._pending_splitter_sizes = list(DEFAULT_SPLITTER_SIZES)
        # Widgets have no real geometry until after the first layout pass, so
        # apply the sizes on the next event-loop turn.
        QTimer.singleShot(0, self._apply_splitter_sizes)
        visible = self.ctx.settings.get("bottom_panel_visible", True)
        self.panel_toggle.setChecked(bool(visible))
        self.set_bottom_panel_visible(bool(visible))

    def _apply_splitter_sizes(self) -> None:
        sizes = getattr(self, "_pending_splitter_sizes", None)
        if sizes and len(sizes) == 2:
            self.splitter.setSizes(sizes)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        try:
            self.ctx.settings.set(
                "window_geometry",
                bytes(self.saveGeometry().toBase64()).decode("ascii"),
                autosave=False,
            )
            self.ctx.settings.set(
                "bottom_splitter_sizes", self.splitter.sizes(), autosave=False
            )
            self.ctx.settings.set(
                "bottom_panel_visible", self.bottom_tabs.isVisible(), autosave=False
            )
            self.ctx.settings.save()
        except Exception:  # noqa: BLE001
            pass
        self.ctx.queue.shutdown()
        super().closeEvent(event)


def open_config_folder() -> None:  # pragma: no cover - convenience
    ensure_dirs()
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_DIR)))
