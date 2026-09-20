"""Reusable widgets shared across the feature tabs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivary.constants import LOGO_FILE

try:  # pragma: no cover - optional Qt module
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover
    QSvgRenderer = None

LOGO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def logo_pixmap(size: int, color: str) -> QPixmap:
    """Render the app logo at ``size`` px, tinted to ``color``.

    The bundled SVG is a single flat-colour path, so we render it and then
    recolour it with ``SourceIn`` to keep it visible on either theme.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if QSvgRenderer is None or not LOGO_FILE.exists():
        return pixmap
    renderer = QSvgRenderer(str(LOGO_FILE))
    if not renderer.isValid():
        return pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return pixmap


def logo_icon(color: str) -> QIcon:
    """A multi-resolution :class:`QIcon` built from the app logo."""
    icon = QIcon()
    for size in LOGO_SIZES:
        icon.addPixmap(logo_pixmap(size, color))
    return icon


class PageHeader(QWidget):
    """A page title with an optional descriptive subtitle."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("Muted")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)


class PathPicker(QWidget):
    """A line edit paired with a Browse button."""

    pathChanged = Signal(str)

    def __init__(
        self,
        mode: str = "file",
        caption: str = "Choose",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.caption = caption
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("")
        self.edit.textChanged.connect(self.pathChanged)
        button = QPushButton("Browse...")
        button.clicked.connect(self._browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def _browse(self) -> None:
        if self.mode == "dir":
            chosen = QFileDialog.getExistingDirectory(self, self.caption, self.edit.text())
        elif self.mode == "save":
            chosen, _ = QFileDialog.getSaveFileName(self, self.caption, self.edit.text())
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, self.caption, self.edit.text())
        if chosen:
            self.edit.setText(chosen)

    def path(self) -> str:
        return self.edit.text().strip()

    def set_path(self, value: str) -> None:
        self.edit.setText(value)


class FilesDropList(QWidget):
    """A list of files/folders that accepts drag-and-drop."""

    changed = Signal()

    def __init__(self, allow_folders: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.allow_folders = allow_folders
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.list = _PathListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setAlternatingRowColors(True)
        self.list.setMinimumHeight(110)
        self.list.setToolTip("Drag files or folders here, or use the buttons below.")
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        add_files = QPushButton("Add files...")
        add_files.clicked.connect(self._add_files)
        add_folder = QPushButton("Add folder...")
        add_folder.clicked.connect(self._add_folder)
        add_folder.setEnabled(allow_folders)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_selected)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        buttons.addWidget(add_files)
        buttons.addWidget(add_folder)
        buttons.addStretch(1)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        layout.addLayout(buttons)

    def _add_files(self) -> None:
        chosen, _ = QFileDialog.getOpenFileNames(self, "Add files")
        if chosen:
            self.add_paths(chosen)

    def _add_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Add folder")
        if chosen:
            self.add_paths([chosen])

    def _remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.changed.emit()

    def add_paths(self, paths: list[str]) -> None:
        existing = {self.list.item(i).text() for i in range(self.list.count())}
        for path in paths:
            if path not in existing:
                self.list.addItem(QListWidgetItem(path))
                existing.add(path)
        self.changed.emit()

    def clear(self) -> None:
        self.list.clear()
        self.changed.emit()

    def paths(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]


class _PathListWidget(QListWidget):
    def __init__(self, owner: FilesDropList) -> None:
        super().__init__()
        self._owner = owner
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local and Path(local).exists():
                    paths.append(local)
            self._owner.add_paths(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class KeyValueEditor(QWidget):
    """A small two-column table for arbitrary metadata key/value pairs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Key", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(120)
        self.table.setToolTip(
            "Custom metadata. Repeat the same key to add multiple values."
        )
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add = QPushButton("Add row")
        add.clicked.connect(lambda: self.add_pair("", ""))
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_selected)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def add_pair(self, key: str, value: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(key))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def pairs(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if key:
                result.append((key, value))
        return result

    def as_metadata(self) -> dict:
        """Collapse pairs into a metadata dict, combining repeated keys."""
        metadata: dict = {}
        for key, value in self.pairs():
            if key in metadata:
                existing = metadata[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    metadata[key] = [existing, value]
            else:
                metadata[key] = value
        return metadata

    def set_metadata(self, metadata: dict) -> None:
        self.table.setRowCount(0)
        for key, value in metadata.items():
            if isinstance(value, (list, tuple)):
                for entry in value:
                    self.add_pair(str(key), str(entry))
            else:
                self.add_pair(str(key), "" if value is None else str(value))


class LabeledRow(QWidget):
    """A label on the left and an arbitrary widget on the right."""

    def __init__(self, label: str, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label_widget = QLabel(label)
        label_widget.setMinimumWidth(150)
        label_widget.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(label_widget)
        layout.addWidget(widget, 1)

    @property
    def control(self) -> QWidget:
        return self.layout().itemAt(1).widget()


def make_combo(options: list[str], editable: bool = False) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(editable)
    combo.addItems(options)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return combo


def stretch_label() -> QLabel:
    label = QLabel("")
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label
