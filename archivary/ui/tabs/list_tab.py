"""List & Delete tab: browse an item's files and delete them carefully."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivary.services.ia_service import (
    DownloadOptions,
    DownloadSpec,
    friendly_url_to_identifier,
    human_size,
)
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import PageHeader


class DeleteConfirmDialog(QDialog):
    """Two-step confirmation before deleting files from an item."""

    def __init__(self, identifier: str, names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm file deletion")
        self.setMinimumSize(560, 420)
        self._identifier = identifier

        layout = QVBoxLayout(self)
        warning = QLabel(
            f"You are about to permanently delete {len(names)} file(s) from "
            f"'{identifier}' on archive.org. This cannot be undone by Archivary."
        )
        warning.setWordWrap(True)
        warning.setObjectName("Status_err")
        layout.addWidget(warning)

        listing = QListWidget()
        listing.addItems(names)
        layout.addWidget(listing, 1)

        self.cascade_check = QCheckBox(
            "Also delete derivative files and the original (cascade delete)"
        )
        layout.addWidget(self.cascade_check)

        self.confirm_check = QCheckBox(
            "I understand these files will be permanently removed"
        )
        self.confirm_check.toggled.connect(self._on_confirm)
        layout.addWidget(self.confirm_check)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type the identifier to confirm:"))
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText(identifier)
        self.identifier_edit.textChanged.connect(self._on_confirm)
        type_row.addWidget(self.identifier_edit, 1)
        layout.addLayout(type_row)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Delete files")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Danger")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._on_confirm()

    def _on_confirm(self, *_: object) -> None:
        ready = (
            self.confirm_check.isChecked()
            and self.identifier_edit.text().strip() == self._identifier
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    @property
    def cascade_delete(self) -> bool:
        return self.cascade_check.isChecked()


class ListTab(BaseTab):
    title = "List & Delete"

    def build(self) -> None:
        self._specs: list[DownloadSpec] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "List & Delete",
                "Every file in an item, with size and checksums. Queue selected files "
                "for download or remove them - deletion is deliberately hard to trigger.",
            )
        )

        lookup = QGroupBox("Item")
        lookup_row = QHBoxLayout(lookup)
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText("identifier or archive.org URL")
        self.identifier_edit.returnPressed.connect(self._load)
        load = QPushButton("Load files")
        load.clicked.connect(self._load)
        lookup_row.addWidget(self.identifier_edit, 1)
        lookup_row.addWidget(load)
        outer.addWidget(lookup)

        files_group = QGroupBox("Files")
        files_layout = QVBoxLayout(files_group)
        self.summary = QLabel("No item loaded.")
        self.summary.setObjectName("Muted")
        files_layout.addWidget(self.summary)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "File", "Size", "Format", "MD5", "SHA-1"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        files_layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select none")
        select_none.clicked.connect(lambda: self._set_all(False))
        download = QPushButton("Download selected")
        download.setObjectName("Primary")
        download.clicked.connect(self._download_selected)
        delete = QPushButton("Delete selected...")
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete_selected)
        buttons.addWidget(select_all)
        buttons.addWidget(select_none)
        buttons.addStretch(1)
        buttons.addWidget(download)
        buttons.addWidget(delete)
        files_layout.addLayout(buttons)
        outer.addWidget(files_group, 1)

    # -- loading -----------------------------------------------------------
    def _identifier(self) -> str:
        return friendly_url_to_identifier(self.identifier_edit.text())

    def _load(self) -> None:
        identifier = self._identifier()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier.")
            return

        def work(reporter):
            reporter.report(message=f"Listing files in {identifier}", stage="download")
            return self.ctx.service.list_files(identifier)

        job = self.ctx.submit("download", f"List files in {identifier}", work, pausable=False)
        self.watch_job(job, self._populate)

    def _populate(self, specs: list[DownloadSpec]) -> None:
        self._specs = specs
        self.table.setRowCount(0)
        total = 0
        for spec in specs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            name_item = QTableWidgetItem(spec.name)
            name_item.setData(Qt.ItemDataRole.UserRole, spec)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(human_size(spec.size)))
            self.table.setItem(row, 3, QTableWidgetItem(spec.format))
            self.table.setItem(row, 4, QTableWidgetItem(spec.md5))
            self.table.setItem(row, 5, QTableWidgetItem(spec.sha1))
            total += spec.size
        self.summary.setText(f"{len(specs)} file(s) - {human_size(total)} total.")

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)

    def _checked_rows(self) -> list[int]:
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _checked_specs(self) -> list[DownloadSpec]:
        specs = []
        for row in self._checked_rows():
            name_item = self.table.item(row, 1)
            if name_item:
                spec = name_item.data(Qt.ItemDataRole.UserRole)
                if spec is not None:
                    specs.append(spec)
        return specs

    # -- actions -----------------------------------------------------------
    def _download_selected(self) -> None:
        # Public items can be downloaded anonymously; credentials are optional.
        identifier = self._identifier()
        specs = self._checked_specs()
        if not specs:
            self.ctx.notify_warning("No files selected", "Check the files to download.")
            return
        destdir = str(self.ctx.settings.get("download_dir", ""))
        Path(destdir).mkdir(parents=True, exist_ok=True)
        options = DownloadOptions(
            ignore_existing=True,
            verify_checksum=bool(self.ctx.settings.get("verify_checksums")),
            count_views=bool(self.ctx.settings.get("count_views")),
            concurrency=int(self.ctx.settings.get("download_concurrency", 3)),
        )
        total = sum(spec.size for spec in specs)

        def work(reporter):
            return self.ctx.service.download_files(
                identifier, destdir, specs, options, reporter
            )

        job = self.ctx.submit(
            "download",
            f"Download {len(specs)} file(s) from {identifier}",
            work,
            subtitle=f"-> {destdir}",
            total=total,
        )
        self.ctx.window.show_job_panel()
        self.watch_job(
            job, announce_success=("Download complete", f"Files saved to {destdir}.")
        )

    def _delete_selected(self) -> None:
        if not self.ctx.require_profile():
            return
        identifier = self._identifier()
        specs = self._checked_specs()
        if not identifier or not specs:
            self.ctx.notify_warning(
                "No files selected", "Check the files you intend to delete."
            )
            return
        dialog = DeleteConfirmDialog(identifier, [spec.name for spec in specs], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        names = [spec.name for spec in specs]
        cascade = dialog.cascade_delete

        def work(reporter):
            return self.ctx.service.delete_files(
                identifier, names, cascade_delete=cascade, reporter=reporter
            )

        job = self.ctx.submit(
            "delete",
            f"Delete {len(names)} file(s) from {identifier}",
            work,
            total=len(names),
            pausable=False,
        )
        self.ctx.window.show_job_panel()
        self.watch_job(
            job,
            lambda _result: self._load(),
            announce_success=("Deleted", f"Removed {len(names)} file(s) from archive.org."),
        )

    def prefill(self, identifier: str) -> None:
        self.identifier_edit.setText(identifier)
        self._load()

    def on_profile_changed(self) -> None:
        pass
