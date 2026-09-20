"""Upload tab: build items and send files to the Internet Archive."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from archivary.constants import MEDIATYPES
from archivary.services.ia_service import UploadOptions, collect_upload_files
from archivary.services.spreadsheet import parse_upload_rows, read_table
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import FilesDropList, KeyValueEditor, PageHeader


class UploadTab(BaseTab):
    title = "Upload"

    def build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Upload",
                "Drag files or folders, fill in the item metadata, and upload. "
                "Large uploads keep running in the Transfers panel.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_item_group())
        layout.addWidget(self._build_metadata_group())
        layout.addWidget(self._build_files_group())
        layout.addWidget(self._build_options_group())
        layout.addWidget(self._build_actions())
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # -- sections ----------------------------------------------------------
    def _build_item_group(self) -> QGroupBox:
        group = QGroupBox("Destination item")
        form = QFormLayout(group)
        row = QHBoxLayout()
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText(
            "unique-identifier (letters, numbers, dashes, underscores)"
        )
        row.addWidget(self.identifier_edit, 1)
        form.addRow("Identifier", row)
        hint = QLabel(
            "The identifier is permanent and is how the item will be addressed at "
            "archive.org/details/<identifier>."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return group

    def _build_metadata_group(self) -> QGroupBox:
        group = QGroupBox("Metadata")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.creator_edit = QLineEdit()
        self.collection_edit = QLineEdit()
        self.collection_edit.setPlaceholderText("community_video, opensource_movies")
        self.mediatype_combo = QComboBox()
        self.mediatype_combo.setEditable(True)
        self.mediatype_combo.addItems(MEDIATYPES)
        self.mediatype_combo.setCurrentText("movies")
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("tag one, tag two")
        self.license_edit = QLineEdit()
        self.license_edit.setPlaceholderText("https://creativecommons.org/licenses/...")
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("What is this item about?")
        self.description_edit.setFixedHeight(80)

        form.addRow("Title", self.title_edit)
        form.addRow("Creator", self.creator_edit)
        form.addRow("Collection", self.collection_edit)
        form.addRow("Media type", self.mediatype_combo)
        form.addRow("Subject tags", self.subject_edit)
        form.addRow("License URL", self.license_edit)
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)

        custom_label = QLabel("Custom metadata")
        custom_label.setObjectName("Muted")
        layout.addWidget(custom_label)
        self.custom_editor = KeyValueEditor()
        layout.addWidget(self.custom_editor)
        return group

    def _build_files_group(self) -> QGroupBox:
        group = QGroupBox("Files")
        layout = QVBoxLayout(group)
        self.files_list = FilesDropList(allow_folders=True)
        layout.addWidget(self.files_list)
        self.flatten_check = QCheckBox("Flatten folders (do not preserve directory names)")
        self.flatten_check.setChecked(False)
        layout.addWidget(self.flatten_check)
        hint = QLabel(
            "Interrupted uploads can be resumed by re-running with "
            "\"Skip unchanged files\" enabled."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.derive_check = QCheckBox("Queue derive task after upload")
        self.derive_check.setChecked(bool(self.ctx.settings.get("queue_derive")))
        self.checksum_check = QCheckBox("Skip unchanged files (checksum)")
        self.checksum_check.setChecked(bool(self.ctx.settings.get("checksum_skip")))
        self.verify_check = QCheckBox("Verify uploads with Content-MD5")
        self.verify_check.setChecked(bool(self.ctx.settings.get("verify_checksums")))
        self.delete_check = QCheckBox("Delete local files after successful upload")
        self.delete_check.setChecked(bool(self.ctx.settings.get("delete_local_after_upload")))
        self.keep_old_check = QCheckBox("Keep old version (do not overwrite)")
        self.validate_check = QCheckBox("Validate identifier before uploading")

        for check in (
            self.derive_check,
            self.checksum_check,
            self.verify_check,
            self.delete_check,
            self.keep_old_check,
            self.validate_check,
        ):
            layout.addWidget(check)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 20)
        self.retries_spin.setValue(int(self.ctx.settings.get("upload_retries", 3)))
        retries_row = QHBoxLayout()
        retries_row.setSpacing(8)
        retries_row.addWidget(QLabel("Retries on overload"))
        retries_row.addWidget(self.retries_spin)
        retries_row.addStretch(1)
        layout.addLayout(retries_row)
        return group

    def _build_actions(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.upload_button = QPushButton("Start upload")
        self.upload_button.setObjectName("Primary")
        self.upload_button.clicked.connect(self._start_upload)
        batch_button = QPushButton("Batch upload from spreadsheet...")
        batch_button.clicked.connect(self._start_batch)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear)
        row.addWidget(self.upload_button)
        row.addWidget(batch_button)
        row.addStretch(1)
        row.addWidget(clear_button)
        return widget

    # -- metadata ----------------------------------------------------------
    @staticmethod
    def _split(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    def _metadata_payload(self) -> dict:
        metadata: dict = {}
        if self.title_edit.text().strip():
            metadata["title"] = self.title_edit.text().strip()
        if self.creator_edit.text().strip():
            metadata["creator"] = self.creator_edit.text().strip()
        collections = self._split(self.collection_edit.text())
        if collections:
            metadata["collection"] = collections
        if self.mediatype_combo.currentText().strip():
            metadata["mediatype"] = self.mediatype_combo.currentText().strip()
        subjects = self._split(self.subject_edit.text())
        if subjects:
            metadata["subject"] = subjects
        if self.license_edit.text().strip():
            metadata["licenseurl"] = self.license_edit.text().strip()
        if self.description_edit.toPlainText().strip():
            metadata["description"] = self.description_edit.toPlainText().strip()
        metadata.update(self.custom_editor.as_metadata())
        return metadata

    def _upload_options(self) -> UploadOptions:
        return UploadOptions(
            metadata=self._metadata_payload(),
            queue_derive=self.derive_check.isChecked(),
            checksum_skip=self.checksum_check.isChecked(),
            verify=self.verify_check.isChecked() or self.delete_check.isChecked(),
            delete_local=self.delete_check.isChecked(),
            keep_old_version=self.keep_old_check.isChecked(),
            retries=self.retries_spin.value(),
            validate_identifier=self.validate_check.isChecked(),
        )

    # -- actions -----------------------------------------------------------
    def _start_upload(self) -> None:
        if not self.ctx.require_profile():
            return
        identifier = self.identifier_edit.text().strip()
        if not identifier:
            self.ctx.notify_warning("Identifier required", "Enter an item identifier.")
            return
        paths = self.files_list.paths()
        if not paths:
            self.ctx.notify_warning("No files", "Add at least one file or folder to upload.")
            return
        files = collect_upload_files(paths, flatten=self.flatten_check.isChecked())
        if not files:
            self.ctx.notify_warning("No files", "The selected folders contain no files.")
            return

        options = self._upload_options()
        total = sum(f.size for f in files)
        subtitle = f"{len(files)} file(s) -> {identifier}"

        def work(reporter):
            return self.ctx.service.upload_files(identifier, files, options, reporter)

        job = self.ctx.submit(
            "upload",
            f"Upload to {identifier}",
            work,
            subtitle=subtitle,
            total=total,
        )
        self.ctx.window.show_job_panel()
        self.watch_job(
            job,
            announce_success=(
                "Upload complete",
                f"Files are being processed at https://archive.org/details/{identifier}",
            ),
        )

    def _start_batch(self) -> None:
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
        batches = parse_upload_rows(rows)
        if not batches:
            self.ctx.notify_warning(
                "Nothing to upload",
                "The spreadsheet has no rows with an 'identifier' column.",
            )
            return

        base_dir = Path(path).parent
        options = self._upload_options()
        queued = 0
        for batch in batches:
            identifier = batch["identifier"]
            file_paths = [str(base_dir / f) if not Path(f).is_absolute() else f for f in batch["files"]]
            files = collect_upload_files(file_paths, flatten=self.flatten_check.isChecked())
            if not files:
                continue
            metadata = dict(options.metadata)
            metadata.update(batch["metadata"])
            batch_options = UploadOptions(
                metadata=metadata,
                queue_derive=options.queue_derive,
                checksum_skip=options.checksum_skip,
                verify=options.verify,
                delete_local=options.delete_local,
                keep_old_version=options.keep_old_version,
                retries=options.retries,
                validate_identifier=options.validate_identifier,
            )
            total = sum(f.size for f in files)

            def work(reporter, ident=identifier, fs=files, opts=batch_options):
                return self.ctx.service.upload_files(ident, fs, opts, reporter)

            self.ctx.submit(
                "upload",
                f"Upload to {identifier}",
                work,
                subtitle=f"{len(files)} file(s) (batch)",
                total=total,
            )
            queued += 1

        self.ctx.window.show_job_panel()
        self.ctx.notify_info(
            "Batch queued",
            f"Queued {queued} upload job(s) from {Path(path).name}.",
        )

    def _clear(self) -> None:
        self.files_list.clear()
        self.identifier_edit.clear()
        self.title_edit.clear()
        self.creator_edit.clear()
        self.collection_edit.clear()
        self.subject_edit.clear()
        self.license_edit.clear()
        self.description_edit.clear()
        self.custom_editor.set_metadata({})

    def prefill(self, identifier: str) -> None:
        self.identifier_edit.setText(identifier)

    def on_profile_changed(self) -> None:
        pass
