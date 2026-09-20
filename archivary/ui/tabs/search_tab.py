"""Search tab: query archive.org and route results to other tabs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivary.constants import DEFAULT_SEARCH_FIELDS, MEDIATYPES
from archivary.services.spreadsheet import export_results
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import PageHeader

SORT_CHOICES = {
    "Relevance": None,
    "Most downloaded": ["downloads desc"],
    "Newest first": ["date desc"],
    "Oldest first": ["date asc"],
    "Title A-Z": ["title asc"],
}


class SearchTab(BaseTab):
    title = "Search"

    def build(self) -> None:
        self._rows: list[dict] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Search",
                "Search the Internet Archive. Send any result straight to "
                "Download, Metadata or the file List.",
            )
        )
        outer.addWidget(self._build_query_group())
        outer.addWidget(self._build_results_group(), 1)

    # -- sections ----------------------------------------------------------
    def _build_query_group(self) -> QGroupBox:
        group = QGroupBox("Query")
        layout = QVBoxLayout(group)

        mode_row = QHBoxLayout()
        self.simple_radio = QRadioButton("Simple")
        self.advanced_radio = QRadioButton("Advanced (field:value)")
        self.simple_radio.setChecked(True)
        self.simple_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.simple_radio)
        mode_row.addWidget(self.advanced_radio)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.mode_stack = QStackedWidget()
        simple_page = QWidget()
        simple_layout = QVBoxLayout(simple_page)
        simple_layout.setContentsMargins(0, 0, 0, 0)
        self.simple_edit = QLineEdit()
        self.simple_edit.setPlaceholderText("market street")
        self.simple_edit.returnPressed.connect(self._run_search)
        simple_layout.addWidget(self.simple_edit)
        self.mode_stack.addWidget(simple_page)

        advanced_page = QWidget()
        advanced_layout = QVBoxLayout(advanced_page)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.advanced_edit = QPlainTextEdit()
        self.advanced_edit.setPlaceholderText('subject:"market street" collection:prelinger')
        self.advanced_edit.setFixedHeight(60)
        advanced_layout.addWidget(self.advanced_edit)
        builder = QHBoxLayout()
        self.field_combo = QComboBox()
        self.field_combo.setEditable(True)
        self.field_combo.addItems(
            [
                "title",
                "creator",
                "subject",
                "collection",
                "mediatype",
                "identifier",
                "description",
                "date",
                "language",
            ]
        )
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("value")
        self.value_edit.returnPressed.connect(self._append_field)
        add_button = QPushButton("Add field")
        add_button.clicked.connect(self._append_field)
        builder.addWidget(QLabel("Field"))
        builder.addWidget(self.field_combo)
        builder.addWidget(QLabel("Value"))
        builder.addWidget(self.value_edit, 1)
        builder.addWidget(add_button)
        advanced_layout.addLayout(builder)
        self.mode_stack.addWidget(advanced_page)
        layout.addWidget(self.mode_stack)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Media type"))
        self.mediatype_combo = QComboBox()
        self.mediatype_combo.addItem("Any", "")
        for mediatype in MEDIATYPES:
            self.mediatype_combo.addItem(mediatype, mediatype)
        filters.addWidget(self.mediatype_combo)
        filters.addWidget(QLabel("Collection"))
        self.collection_edit = QLineEdit()
        self.collection_edit.setPlaceholderText("optional collection filter")
        filters.addWidget(self.collection_edit, 1)
        filters.addWidget(QLabel("Sort"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(list(SORT_CHOICES))
        filters.addWidget(self.sort_combo)
        filters.addWidget(QLabel("Max results"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 10000)
        self.limit_spin.setValue(100)
        filters.addWidget(self.limit_spin)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("Primary")
        self.search_button.clicked.connect(self._run_search)
        actions.addWidget(self.search_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return group

    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("Results")
        layout = QVBoxLayout(group)
        self.summary = QLabel("No search yet.")
        self.summary.setObjectName("Muted")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Title", "Identifier", "Media type", "Date", "Size", "Downloads"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.doubleClicked.connect(lambda _: self._send_metadata())
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        to_download = QPushButton("Send to Download")
        to_download.clicked.connect(self._send_download)
        to_metadata = QPushButton("Send to Metadata")
        to_metadata.clicked.connect(self._send_metadata)
        to_list = QPushButton("Open in List")
        to_list.clicked.connect(self._send_list)
        export_button = QPushButton("Export...")
        export_button.clicked.connect(self._export)
        actions.addWidget(to_download)
        actions.addWidget(to_metadata)
        actions.addWidget(to_list)
        actions.addStretch(1)
        actions.addWidget(export_button)
        layout.addLayout(actions)
        return group

    # -- query building ----------------------------------------------------
    def _on_mode_changed(self, *_: object) -> None:
        self.mode_stack.setCurrentIndex(0 if self.simple_radio.isChecked() else 1)

    def _append_field(self) -> None:
        field = self.field_combo.currentText().strip()
        value = self.value_edit.text().strip()
        if not field or not value:
            return
        snippet = f'{field}:"{value}"'
        existing = self.advanced_edit.toPlainText().strip()
        self.advanced_edit.setPlainText(f"{existing} {snippet}".strip())
        self.value_edit.clear()

    def _build_query(self) -> str:
        if self.simple_radio.isChecked():
            raw = self.simple_edit.text().strip()
            query = raw
        else:
            query = self.advanced_edit.toPlainText().strip()
        mediatype = self.mediatype_combo.currentData()
        if mediatype:
            query = f"({query}) AND mediatype:{mediatype}" if query else f"mediatype:{mediatype}"
        collection = self.collection_edit.text().strip()
        if collection:
            query = f"({query}) AND collection:{collection}" if query else f"collection:{collection}"
        return query or "*:*"

    # -- search ------------------------------------------------------------
    def _run_search(self) -> None:
        query = self._build_query()
        sorts = SORT_CHOICES.get(self.sort_combo.currentText())
        limit = self.limit_spin.value()
        self.summary.setText("Searching...")
        self.search_button.setEnabled(False)

        def work(reporter):
            return self.ctx.service.search(
                query,
                fields=DEFAULT_SEARCH_FIELDS,
                sorts=sorts,
                limit=limit,
                reporter=reporter,
            )

        job = self.ctx.submit("search", "Search archive.org", work, pausable=False)

        def done(result) -> None:
            rows, total = result
            self._populate(rows, total)

        self.watch_job(job, done, announce_failure=True)
        job.changed.connect(self._reenable_on_finish)

    def _reenable_on_finish(self, job) -> None:
        from archivary.core.jobs import JobStatus

        if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
            self.search_button.setEnabled(True)

    def _populate(self, rows: list[dict], total: int) -> None:
        self._rows = rows
        self.table.setRowCount(0)
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            title = row.get("title", "")
            if isinstance(title, list):
                title = title[0] if title else ""
            self.table.setItem(index, 0, QTableWidgetItem(str(title)))
            identifier_item = QTableWidgetItem(str(row.get("identifier", "")))
            identifier_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(index, 1, identifier_item)
            self.table.setItem(index, 2, QTableWidgetItem(str(row.get("mediatype", ""))))
            self.table.setItem(index, 3, QTableWidgetItem(str(row.get("date", ""))))
            self.table.setItem(index, 4, QTableWidgetItem(_format_size(row.get("item_size"))))
            self.table.setItem(index, 5, QTableWidgetItem(str(row.get("downloads", ""))))
        shown = len(rows)
        self.summary.setText(
            f"Showing {shown} of {total} result(s). Double-click a row for metadata."
        )

    def _selected_identifiers(self) -> list[str]:
        identifiers: list[str] = []
        for model_index in self.table.selectionModel().selectedRows():
            item = self.table.item(model_index.row(), 1)
            if item:
                identifiers.append(item.text())
        return identifiers

    def _selected_identifier(self) -> str:
        identifiers = self._selected_identifiers()
        return identifiers[0] if identifiers else ""

    def _send_download(self) -> None:
        identifier = self._selected_identifier()
        if not identifier:
            self.ctx.notify_warning("No selection", "Select a search result first.")
            return
        if self.ctx.window:
            self.ctx.window.open_download(identifier)

    def _send_metadata(self) -> None:
        identifier = self._selected_identifier()
        if not identifier:
            self.ctx.notify_warning("No selection", "Select a search result first.")
            return
        if self.ctx.window:
            self.ctx.window.open_metadata(identifier)

    def _send_list(self) -> None:
        identifier = self._selected_identifier()
        if not identifier:
            self.ctx.notify_warning("No selection", "Select a search result first.")
            return
        if self.ctx.window:
            self.ctx.window.open_list(identifier)

    def _export(self) -> None:
        if not self._rows:
            self.ctx.notify_warning("Nothing to export", "Run a search first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export results",
            "archive-search.csv",
            "CSV (*.csv);;JSON (*.json)",
        )
        if not path:
            return
        try:
            export_results(path, self._rows)
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify_error("Export failed", str(exc))
            return
        self.ctx.notify_info("Exported", f"Saved results to {path}.")

    def on_profile_changed(self) -> None:
        pass


def _format_size(value) -> str:
    from archivary.services.ia_service import human_size

    try:
        return human_size(float(value))
    except (TypeError, ValueError):
        return ""
