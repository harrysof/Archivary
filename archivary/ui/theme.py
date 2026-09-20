"""Light/dark theming for Archivary.

``system`` follows the operating system's colour scheme (Qt 6.5+ exposes this
through ``QStyleHints.colorScheme()``).  Both themes are defined as a palette
plus a matching stylesheet so widgets stay legible in either mode.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK = {
    "bg": "#1e1f22",
    "panel": "#2b2d30",
    "alt": "#232427",
    "text": "#e6e6e6",
    "muted": "#9aa0a6",
    "accent": "#4c9aff",
    "accent_hover": "#6cb0ff",
    "accent_text": "#ffffff",
    "border": "#3a3d41",
    "border_soft": "#303236",
    "danger": "#e5534b",
    "success": "#3fb950",
    "warning": "#d29922",
    "disabled": "#6f7377",
}

LIGHT = {
    "bg": "#f4f5f7",
    "panel": "#ffffff",
    "alt": "#eef0f3",
    "text": "#1f2328",
    "muted": "#57606a",
    "accent": "#0a66c2",
    "accent_hover": "#0b74db",
    "accent_text": "#ffffff",
    "border": "#d0d7de",
    "border_soft": "#e4e7eb",
    "danger": "#cf222e",
    "success": "#1a7f37",
    "warning": "#9a6700",
    "disabled": "#8c959f",
}


def resolve_theme(app: QApplication, mode: str) -> str:
    """Return ``"dark"`` or ``"light"`` for the requested mode."""
    if mode in ("dark", "light"):
        return mode
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"
    except Exception:  # pragma: no cover - older Qt
        pass
    return "dark"


def build_palette(name: str) -> QPalette:
    colors = DARK if name == "dark" else LIGHT
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(colors["danger"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["accent_text"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(colors["disabled"]),
    )
    return palette


def build_stylesheet(name: str) -> str:
    c = DARK if name == "dark" else LIGHT
    return f"""
    /* Base: no background on every QWidget, otherwise labels/containers paint
       opaque rectangles ("black boxes") over the cards they sit on. */
    QWidget {{
        color: {c["text"]};
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {c["bg"]}; }}

    QWidget#Sidebar {{
        background-color: {c["panel"]};
        border-right: 1px solid {c["border"]};
    }}

    QLabel {{ background: transparent; }}
    QLabel#Muted, QLabel#Hint {{ color: {c["muted"]}; }}
    QLabel#SectionTitle {{ font-size: 15px; font-weight: 700; }}
    QLabel#PageTitle {{ font-size: 21px; font-weight: 700; }}
    QLabel#JobTitle {{ font-weight: 600; }}
    QLabel#Status_ok {{ color: {c["success"]}; }}
    QLabel#Status_err {{ color: {c["danger"]}; }}
    QLabel#Status_warn {{ color: {c["warning"]}; }}

    /* Cards ----------------------------------------------------------------- */
    QFrame#Card {{
        background-color: {c["panel"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
    }}

    /* Group boxes render as cards with the heading inside the panel, so there
       is no dark margin strip behind the title. */
    QGroupBox {{
        background-color: {c["panel"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        margin-top: 0px;
        padding: 36px 16px 16px 16px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: padding;
        subcontrol-position: top left;
        left: 16px;
        top: 12px;
        padding: 0;
        color: {c["text"]};
        font-size: 14px;
        font-weight: 700;
        background: transparent;
    }}

    /* Inputs ---------------------------------------------------------------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QDateEdit {{
        background-color: {c["alt"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {c["accent"]};
        selection-color: {c["accent_text"]};
    }}
    QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover,
    QSpinBox:hover, QComboBox:hover, QDateEdit:hover {{
        border-color: {c["muted"]};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
        border: 1px solid {c["accent"]};
    }}
    QLineEdit[readOnly="true"] {{ color: {c["muted"]}; }}
    QComboBox::drop-down {{ border: none; background: transparent; width: 22px; }}
    QComboBox QAbstractItemView {{
        background-color: {c["panel"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {c["accent"]};
        selection-color: {c["accent_text"]};
    }}

    /* Buttons --------------------------------------------------------------- */
    QPushButton {{
        background-color: {c["alt"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 7px 16px;
        color: {c["text"]};
    }}
    QPushButton:hover {{ border-color: {c["accent"]}; }}
    QPushButton:pressed {{ background-color: {c["bg"]}; }}
    QPushButton:disabled {{ color: {c["disabled"]}; border-color: {c["border_soft"]}; }}
    QPushButton#Primary {{
        background-color: {c["accent"]};
        color: {c["accent_text"]};
        border: 1px solid {c["accent"]};
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {c["accent_hover"]}; border-color: {c["accent_hover"]}; }}
    QPushButton#Primary:pressed {{ background-color: {c["accent"]}; }}
    QPushButton#Danger {{
        background-color: {c["danger"]};
        color: #ffffff;
        border: 1px solid {c["danger"]};
        font-weight: 600;
    }}
    QPushButton#Mini {{
        padding: 1px 9px;
        font-size: 11px;
        border-radius: 6px;
        background: transparent;
        border: 1px solid {c["border"]};
    }}
    QPushButton#Mini:hover {{ border-color: {c["accent"]}; }}

    QFrame#JobCard {{
        background-color: {c["alt"]};
        border: 1px solid {c["border_soft"]};
        border-radius: 8px;
    }}
    QProgressBar#JobBar {{
        min-height: 14px;
        max-height: 16px;
    }}

    /* Sidebar navigation ---------------------------------------------------- */
    QPushButton#NavButton {{
        text-align: left;
        padding: 9px 12px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {c["muted"]};
        font-weight: 500;
    }}
    QPushButton#NavButton:hover {{ background-color: {c["alt"]}; color: {c["text"]}; }}
    QPushButton#NavButton:checked {{
        background-color: {c["accent"]};
        color: {c["accent_text"]};
        font-weight: 600;
    }}

    /* Lists and tables ------------------------------------------------------ */
    QListWidget, QTreeWidget, QTableWidget, QTableView {{
        background-color: {c["panel"]};
        alternate-background-color: {c["alt"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        gridline-color: {c["border_soft"]};
        selection-background-color: {c["accent"]};
        selection-color: {c["accent_text"]};
    }}
    QHeaderView::section {{
        background-color: {c["alt"]};
        color: {c["muted"]};
        border: none;
        border-right: 1px solid {c["border"]};
        border-bottom: 1px solid {c["border"]};
        padding: 7px 10px;
        font-weight: 600;
    }}

    QProgressBar {{
        background-color: {c["alt"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        text-align: center;
        height: 18px;
        color: {c["text"]};
    }}
    QProgressBar::chunk {{
        background-color: {c["accent"]};
        border-radius: 7px;
    }}

    QScrollBar:vertical, QScrollBar:horizontal {{
        background: transparent;
        border: none;
        margin: 0;
        width: 12px;
        height: 12px;
    }}
    QScrollBar::handle {{
        background: {c["border"]};
        border-radius: 6px;
        min-height: 24px;
        min-width: 24px;
    }}
    QScrollBar::handle:hover {{ background: {c["muted"]}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    QTabWidget::pane {{ border: none; border-top: 1px solid {c["border"]}; }}
    QTabBar::tab {{
        background: transparent;
        padding: 8px 16px;
        border: none;
        color: {c["muted"]};
    }}
    QTabBar::tab:hover {{ color: {c["text"]}; }}
    QTabBar::tab:selected {{
        color: {c["text"]};
        border-bottom: 2px solid {c["accent"]};
        font-weight: 600;
    }}

    QDockWidget {{ titlebar-close-icon: none; }}
    QDockWidget::title {{
        background-color: {c["alt"]};
        padding: 5px 8px;
        border-bottom: 1px solid {c["border"]};
    }}

    QMenuBar {{ background-color: {c["panel"]}; border-bottom: 1px solid {c["border"]}; }}
    QMenuBar::item {{ padding: 5px 10px; background: transparent; }}
    QMenuBar::item:selected {{ background-color: {c["alt"]}; border-radius: 6px; }}
    QMenu {{
        background-color: {c["panel"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{
        background-color: {c["accent"]};
        color: {c["accent_text"]};
    }}
    QMenu::separator {{ height: 1px; background: {c["border"]}; margin: 4px 8px; }}

    QToolBar {{ background-color: {c["panel"]}; border: none; }}
    QStatusBar {{
        background-color: {c["panel"]};
        color: {c["muted"]};
        border-top: 1px solid {c["border"]};
    }}
    QSplitter::handle {{ background-color: transparent; }}
    QSplitter::handle:hover {{ background-color: {c["border"]}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
    }}
    QToolTip {{
        background-color: {c["panel"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        padding: 4px;
    }}
    """


def apply_theme(app: QApplication, mode: str = "system") -> str:
    """Apply the theme to ``app`` and return the resolved name."""
    resolved = resolve_theme(app, mode)
    app.setPalette(build_palette(resolved))
    app.setStyleSheet(build_stylesheet(resolved))
    return resolved
