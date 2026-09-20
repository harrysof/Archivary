"""Download tab: fetch items or selected files from the Internet Archive."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
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
from archivary.ui.widgets import PageHeader, PathPicker


class DownloadTab(BaseTab):
    title = "Download"

    def build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Download",
                "Paste an item identifier or archive.org URL, choose a destination, "
                "and optionally filter which files to fetch.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_source_group())
        layout.addWidget(self._build_options_group())
        layout.addWidget(self._build_files_group())
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # -- sections ----------------------------------------------------------
    def _build_source_group(self) -> QGroupBox:
        group = QGroupBox("Source and destination")
        form = QFormLayout(group)

        row = QHBoxLayout()
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText(
            "identifier or https://archive.org/details/identifier"
        )
        paste = QPushButton("Paste")
        paste.clicked.connect(self._paste)
        load = QPushButton("Load file list")
        load.clicked.connect(self._load_files)
        row.addWidget(self.identifier_edit, 1)
        row.addWidget(paste)
        row.addWidget(load)
        form.addRow("Item", row)

        self.dest_picker = PathPicker("dir", "Choose destination folder")
        self.dest_picker.set_path(str(self.ctx.settings.get("download_dir", "")))
        self.dest_picker.pathChanged.connect(
            lambda value: self.ctx.settings.set("download_dir", value)
        )
        form.addRow("Download to", self.dest_picker)

        self.glob_edit = QLineEdit()
        self.glob_edit.setPlaceholderText("*.mp4, *.jpg   (comma separated)")
        self.exclude_edit = QLineEdit()
        self.exclude_edit.setPlaceholderText("*_thumb.jpg, *.xml")
        self.formats_edit = QLineEdit()
        self.formats_edit.setPlaceholderText("MPEG4, JPEG")
        form.addRow("Include globs", self.glob_edit)
        form.addRow("Exclude globs", self.exclude_edit)
        form.addRow("Formats", self.formats_edit)
        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        self.skip_existing = QCheckBox("Skip files that already exist")
        self.skip_existing.setChecked(True)
        self.verify_check = QCheckBox("Verify checksums after download")
        self.verify_check.setChecked(bool(self.ctx.settings.get("verify_checksums")))
        self.no_dirs = QCheckBox("Flatten output (no item subfolder)")
        self.resume_check = QCheckBox("Resume partial downloads")
        self.resume_check.setChecked(True)
        self.count_views = QCheckBox("Count this download as a view")
        self.count_views.setChecked(bool(self.ctx.settings.get("count_views")))

        for check in (
            self.skip_existing,
            self.verify_check,
            self.no_dirs,
            self.resume_check,
            self.count_views,
        ):
            layout.addWidget(check)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 16)
        self.concurrency_spin.setValue(int(self.ctx.settings.get("download_concurrency", 3)))
        self.concurrency_spin.valueChanged.connect(
            lambda value: self.ctx.settings.set("download_concurrency", value)
        )
        concurrency_row = QHBoxLayout()
        concurrency_row.setSpacing(8)
        concurrency_row.addWidget(QLabel("Concurrent downloads"))
        concurrency_row.addWidget(self.concurrency_spin)
        concurrency_row.addStretch(1)
        layout.addLayout(concurrency_row)
        return group

    def _build_files_group(self) -> QGroupBox:
        group = QGroupBox("Files")
        layout = QVBoxLayout(group)
        self.summary = QLabel("Load an item to see its files.")
        self.summary.setObjectName("Muted")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "File", "Size", "Format"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        select_none = QPushButton("Select none")
        select_none.clicked.connect(lambda: self._set_all_checked(False))
        self.download_selected = QPushButton("Download selected / all listed")
        self.download_selected.setObjectName("Primary")
        self.download_selected.clicked.connect(self._download_listed)
        self.download_matching = QPushButton("Download everything matching filters")
        self.download_matching.clicked.connect(self._download_matching)
        buttons.addWidget(select_all)
        buttons.addWidget(select_none)
        buttons.addStretch(1)
        buttons.addWidget(self.download_selected)
        buttons.addWidget(self.download_matching)
        layout.addLayout(buttons)
        return group

    # -- helpers -----------------------------------------------------------
    def _identifier(self) -> str:
        return friendly_url_to_identifier(self.identifier_edit.text())

    def _paste(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard().text().strip()
        if clipboard:
            self.identifier_edit.setText(friendly_url_to_identifier(clipboard))

    def _patterns(self, line_edit: QLineEdit) -> list[str]:
        return [part.strip() for part in line_edit.text().split(",") if part.strip()]

    def _options(self) -> DownloadOptions:
        return DownloadOptions(
            ignore_existing=self.skip_existing.isChecked(),
            verify_checksum=self.verify_check.isChecked(),
            no_directory=self.no_dirs.isChecked(),
            count_views=self.count_views.isChecked(),
            resume=self.resume_check.isChecked(),
            concurrency=self.concurrency_spin.value(),
            glob_patterns=self._patterns(self.glob_edit),
            exclude_patterns=self._patterns(self.exclude_edit),
            formats=self._patterns(self.formats_edit),
        )

    # -- actions -----------------------------------------------------------
    def _load_files(self) -> None:
        identifier = self._identifier()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier or URL.")
            return
        options = self._options()

        def work(reporter):
            reporter.report(message=f"Listing {identifier}", stage="download")
            return self.ctx.service.list_files(
                identifier,
                glob_patterns=options.glob_patterns,
                exclude_patterns=options.exclude_patterns,
                formats=options.formats,
            )

        job = self.ctx.submit("download", f"List files in {identifier}", work, pausable=False)
        self.watch_job(job, self._populate_files)

    def _populate_files(self, specs: list[DownloadSpec]) -> None:
        self.table.setRowCount(0)
        total = 0
        for spec in specs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            name_item = QTableWidgetItem(spec.name)
            name_item.setData(Qt.ItemDataRole.UserRole, spec)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(human_size(spec.size)))
            self.table.setItem(row, 3, QTableWidgetItem(spec.format))
            total += spec.size
        self.summary.setText(
            f"{len(specs)} file(s) - {human_size(total)}. "
            "Uncheck files you do not want, then download."
        )

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)

    def _selected_specs(self) -> list[DownloadSpec]:
        specs: list[DownloadSpec] = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if check and name_item and check.checkState() == Qt.CheckState.Checked:
                spec = name_item.data(Qt.ItemDataRole.UserRole)
                if spec is not None:
                    specs.append(spec)
        return specs

    def _download_listed(self) -> None:
        specs = self._selected_specs()
        if specs:
            self._start_download(specs)
        else:
            self._download_matching()

    def _download_matching(self) -> None:
        self._start_download(None)

    def _start_download(self, specs: list[DownloadSpec] | None) -> None:
        # Public items can be downloaded anonymously; credentials are optional.
        identifier = self._identifier()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier or URL.")
            return
        destdir = self.dest_picker.path()
        if not destdir:
            self.ctx.notify_warning("Destination required", "Choose a download folder.")
            return
        Path(destdir).mkdir(parents=True, exist_ok=True)
        options = self._options()
        total = sum(s.size for s in specs) if specs else 0
        subtitle = f"{len(specs)} file(s) -> {destdir}" if specs else f"all matching -> {destdir}"

        def work(reporter):
            return self.ctx.service.download_files(
                identifier, destdir, specs, options, reporter
            )

        job = self.ctx.submit(
            "download",
            f"Download {identifier}",
            work,
            subtitle=subtitle,
            total=total or None,
        )
        self.ctx.window.show_job_panel()
        self.watch_job(
            job,
            announce_success=("Download complete", f"Files saved to {destdir}."),
        )

    def prefill(self, identifier: str) -> None:
        self.identifier_edit.setText(identifier)

    def on_profile_changed(self) -> None:
        pass
