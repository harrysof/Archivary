"""Metadata tab: view and edit item metadata, including batch edits."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from archivary.services.ia_service import friendly_url_to_identifier, human_size
from archivary.services.spreadsheet import parse_metadata_rows, read_table
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import PageHeader

READ_ONLY_FIELDS = {"identifier"}


class MetadataTab(BaseTab):
    title = "Metadata"

    def build(self) -> None:
        self._raw_metadata: dict = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Metadata",
                "Load an item, edit its fields, and save. Use Append to add values "
                "without clobbering existing multi-value fields.",
            )
        )
        outer.addWidget(self._build_lookup_group())
        outer.addWidget(self._build_editor_group(), 1)
        outer.addWidget(self._build_batch_group())

    # -- sections ----------------------------------------------------------
    def _build_lookup_group(self) -> QGroupBox:
        group = QGroupBox("Item")
        row = QHBoxLayout(group)
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText("identifier or archive.org URL")
        self.identifier_edit.returnPressed.connect(self._load)
        load = QPushButton("Load")
        load.clicked.connect(self._load)
        row.addWidget(self.identifier_edit, 1)
        row.addWidget(load)
        return group

    def _build_editor_group(self) -> QGroupBox:
        group = QGroupBox("Fields")
        layout = QVBoxLayout(group)

        self.info_label = QLabel("No item loaded.")
        self.info_label.setObjectName("Muted")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Field", "Value (separate multiple values with |)"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(140)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add_field = QPushButton("Add field")
        add_field.clicked.connect(lambda: self._add_row("", ""))
        remove_field = QPushButton("Remove selected field(s)")
        remove_field.setObjectName("Danger")
        remove_field.clicked.connect(self._remove_fields)
        save = QPushButton("Save (overwrite)")
        save.setObjectName("Primary")
        save.clicked.connect(lambda: self._save(append=False))
        append = QPushButton("Append values")
        append.clicked.connect(lambda: self._save(append=True))
        reload_button = QPushButton("Reload")
        reload_button.clicked.connect(self._load)
        buttons.addWidget(add_field)
        buttons.addWidget(reload_button)
        buttons.addStretch(1)
        buttons.addWidget(append)
        buttons.addWidget(save)
        buttons.addWidget(remove_field)
        layout.addLayout(buttons)

        warning = QLabel(
            "Overwrite replaces the whole value of the fields you submit. Append "
            "(append_list) adds new values to existing ones and never duplicates."
        )
        warning.setObjectName("Muted")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        return group

    def _build_batch_group(self) -> QGroupBox:
        group = QGroupBox("Batch edit from spreadsheet")
        layout = QVBoxLayout(group)
        hint = QLabel(
            "Each row is an item: an 'identifier' column plus any metadata columns. "
            "Separate multiple values with |."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.batch_append_radio = QRadioButton("Append values")
        self.batch_overwrite_radio = QRadioButton("Overwrite values")
        self.batch_append_radio.setChecked(True)
        row.addWidget(self.batch_append_radio)
        row.addWidget(self.batch_overwrite_radio)
        row.addStretch(1)
        import_button = QPushButton("Import spreadsheet...")
        import_button.clicked.connect(self._batch_import)
        row.addWidget(import_button)
        layout.addLayout(row)
        return group

    # -- helpers -----------------------------------------------------------
    def _identifier(self) -> str:
        return friendly_url_to_identifier(self.identifier_edit.text())

    def _add_row(self, key: str, value: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(key))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def _load(self) -> None:
        identifier = self._identifier()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier.")
            return

        def work(reporter):
            reporter.report(message=f"Loading {identifier}", stage="metadata")
            return self.ctx.service.item_metadata(identifier)

        job = self.ctx.submit(
            "metadata", f"Load metadata for {identifier}", work, pausable=False
        )
        self.watch_job(job, self._populate)

    def _populate(self, item_metadata: dict) -> None:
        metadata = dict(item_metadata.get("metadata", {}))
        self._raw_metadata = metadata
        self.table.setRowCount(0)
        for key, value in metadata.items():
            if isinstance(value, (list, tuple)):
                text = " | ".join(str(v) for v in value)
            else:
                text = "" if value is None else str(value)
            self._add_row(key, text)

        files = item_metadata.get("files", [])
        total_size = 0
        for entry in files:
            try:
                total_size += int(entry.get("size", 0) or 0)
            except (TypeError, ValueError):
                pass
        title = metadata.get("title", "")
        if isinstance(title, list):
            title = title[0] if title else ""
        self.info_label.setText(
            f"{metadata.get('identifier', '')}  -  {title}  -  "
            f"{metadata.get('mediatype', '')}  -  {len(files)} file(s), "
            f"{human_size(total_size)}"
        )

    def _table_metadata(self) -> dict:
        metadata: dict = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if not key:
                continue
            parts = [part.strip() for part in value.split("|") if part.strip()]
            metadata[key] = parts if len(parts) > 1 else (parts[0] if parts else "")
        return metadata

    def _save(self, append: bool) -> None:
        if not self.ctx.require_profile():
            return
        identifier = self._identifier()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier.")
            return
        metadata = self._table_metadata()
        if not metadata:
            self.ctx.notify_warning("No metadata", "There is nothing to save.")
            return
        mode = "Append" if append else "Overwrite"

        def work(reporter):
            return self.ctx.service.modify_metadata(
                identifier, metadata, append=append, append_list=append, reporter=reporter
            )

        job = self.ctx.submit(
            "metadata",
            f"{mode} metadata for {identifier}",
            work,
            pausable=False,
        )
        self.watch_job(
            job,
            lambda _result: self._load(),
            announce_success=(f"{mode} saved", "Metadata updated on archive.org."),
        )

    def _remove_fields(self) -> None:
        if not self.ctx.require_profile():
            return
        identifier = self._identifier()
        fields = []
        for model_index in self.table.selectionModel().selectedRows():
            item = self.table.item(model_index.row(), 0)
            if item and item.text().strip() and item.text().strip() not in READ_ONLY_FIELDS:
                fields.append(item.text().strip())
        if not identifier or not fields:
            self.ctx.notify_warning(
                "Nothing selected",
                "Select the metadata field rows you want to remove.",
            )
            return
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "Remove fields",
            f"Remove these fields from {identifier}?\n\n"
            + ", ".join(fields)
            + "\n\nThis cannot be undone automatically.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        payload = {field: "REMOVE_TAG" for field in fields}

        def work(reporter):
            return self.ctx.service.modify_metadata(identifier, payload, reporter=reporter)

        job = self.ctx.submit(
            "metadata", f"Remove fields from {identifier}", work, pausable=False
        )
        self.watch_job(
            job,
            lambda _result: self._load(),
            announce_success=("Fields removed", "Metadata updated on archive.org."),
        )

    def _batch_import(self) -> None:
        if not self.ctx.require_profile():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose spreadsheet", "", "Spreadsheets (*.csv *.xlsx *.xlsm)"
        )
        if not path:
            return
        try:
            _, rows = read_table(path)
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify_error("Could not read spreadsheet", str(exc))
            return
        updates = parse_metadata_rows(rows)
        if not updates:
            self.ctx.notify_warning(
                "Nothing to update",
                "The spreadsheet has no rows with an 'identifier' column.",
            )
            return
        append = self.batch_append_radio.isChecked()

        def work(reporter):
            return self.ctx.service.batch_modify_metadata(
                updates, append=False, append_list=append, reporter=reporter
            )

        job = self.ctx.submit(
            "metadata",
            f"Batch metadata ({len(updates)} items)",
            work,
            total=len(updates),
            pausable=False,
        )

        def done(result: dict) -> None:
            failed = result.get("failed", [])
            message = f"Updated {len(result.get('succeeded', []))} item(s)."
            if failed:
                message += f" {len(failed)} failed."
            self.ctx.notify_info("Batch metadata", message)

        self.watch_job(job, done)

    def prefill(self, identifier: str) -> None:
        self.identifier_edit.setText(identifier)
        self._load()

    def on_profile_changed(self) -> None:
        pass
