"""Account and application settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from archivary.core.credentials import Profile
from archivary.ui.tabs.base import BaseTab
from archivary.ui.widgets import PageHeader, PathPicker


class SettingsTab(BaseTab):
    title = "Settings"

    # -- construction ------------------------------------------------------
    def build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addWidget(
            PageHeader(
                "Settings",
                "Manage Internet Archive accounts and Archivary preferences. "
                "Credentials are stored in your operating system's keychain.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_account_group())
        layout.addWidget(self._build_password_group())
        layout.addWidget(self._build_preferences_group())
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self.refresh_profiles()

    def _build_account_group(self) -> QGroupBox:
        group = QGroupBox("Account")
        layout = QVBoxLayout(group)

        top = QHBoxLayout()
        top.addWidget(QLabel("Saved profiles:"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        top.addWidget(self.profile_combo, 1)
        self.set_active_button = QPushButton("Set active")
        self.set_active_button.clicked.connect(self._set_active)
        top.addWidget(self.set_active_button)
        layout.addLayout(top)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. personal")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("you@example.com")
        self.access_edit = QLineEdit()
        self.access_edit.setPlaceholderText("IAS3 access key")
        self.secret_edit = QLineEdit()
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_edit.setPlaceholderText("IAS3 secret key")
        self.host_edit = QLineEdit("archive.org")
        form.addRow("Profile name", self.name_edit)
        form.addRow("Email (optional)", self.email_edit)
        form.addRow("Access key", self.access_edit)
        form.addRow("Secret key", self.secret_edit)
        form.addRow("Host", self.host_edit)
        layout.addLayout(form)

        self.show_secret = QCheckBox("Show secret key")
        self.show_secret.toggled.connect(
            lambda shown: self.secret_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(self.show_secret)

        buttons = QHBoxLayout()
        save = QPushButton("Save profile")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_profile)
        delete = QPushButton("Delete profile")
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete_profile)
        test = QPushButton("Test connection")
        test.clicked.connect(self._test_connection)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addStretch(1)
        buttons.addWidget(delete)
        layout.addLayout(buttons)

        self.storage_label = QLabel()
        self.storage_label.setObjectName("Muted")
        self.storage_label.setWordWrap(True)
        layout.addWidget(self.storage_label)
        return group

    def _build_password_group(self) -> QGroupBox:
        group = QGroupBox("Sign in with email and password")
        layout = QVBoxLayout(group)
        hint = QLabel(
            "Archivary exchanges your email and password for IAS3 keys through "
            "archive.org. The password itself is never stored."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("you@example.com")
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Email", self.login_email)
        form.addRow("Password", self.login_password)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.login_button = QPushButton("Fetch keys")
        self.login_button.clicked.connect(self._sign_in)
        row.addWidget(self.login_button)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    def _build_preferences_group(self) -> QGroupBox:
        group = QGroupBox("Preferences")
        layout = QFormLayout(group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "dark", "light"])
        self.theme_combo.setCurrentText(str(self.ctx.settings.get("theme")))
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        layout.addRow("Theme", self.theme_combo)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 12)
        self.concurrent_spin.setValue(int(self.ctx.settings.get("max_concurrent_jobs", 3)))
        self.concurrent_spin.valueChanged.connect(self._on_concurrency_changed)
        layout.addRow("Concurrent jobs", self.concurrent_spin)

        self.download_picker = PathPicker("dir", "Choose default download folder")
        self.download_picker.set_path(str(self.ctx.settings.get("download_dir", "")))
        self.download_picker.pathChanged.connect(
            lambda value: self.ctx.settings.set("download_dir", value)
        )
        layout.addRow("Default download folder", self.download_picker)

        self.verify_check = self._check(
            "verify_checksums", "Verify checksums after download"
        )
        self.count_views_check = self._check(
            "count_views", "Count downloads as a view by default"
        )
        self.checksum_skip_check = self._check(
            "checksum_skip", "Skip uploads whose checksums already match"
        )
        self.delete_local_check = self._check(
            "delete_local_after_upload", "Delete local file after successful upload"
        )
        self.derive_check = self._check("queue_derive", "Queue derive tasks after upload")
        self.raw_log_check = self._check("raw_logging", "Raw HTTP logging in the console")

        for check in (
            self.verify_check,
            self.count_views_check,
            self.checksum_skip_check,
            self.delete_local_check,
            self.derive_check,
        ):
            layout.addRow("", check)

        advanced = QLabel("Advanced")
        advanced.setObjectName("Muted")
        layout.addRow("", advanced)
        layout.addRow("", self.raw_log_check)

        backend = QLabel(f"Credential storage: {self.ctx.store.backend_name}")
        backend.setObjectName("Muted")
        layout.addRow("", backend)
        return group

    def _check(self, key: str, label: str) -> QCheckBox:
        check = QCheckBox(label)
        check.setChecked(bool(self.ctx.settings.get(key)))
        check.toggled.connect(lambda value, k=key: self.ctx.settings.set(k, value))
        return check

    # -- profile handling --------------------------------------------------
    def refresh_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        profiles = self.ctx.store.list_profiles()
        active = self.ctx.store.active_name
        for profile in profiles:
            label = profile.name
            if profile.screenname:
                label += f"  ({profile.screenname})"
            self.profile_combo.addItem(label, profile.name)
        index = self.profile_combo.findData(active)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self.storage_label.setText(
            "Multiple profiles are supported. The selected profile is used for "
            "all uploads and downloads."
        )
        self._on_profile_selected(self.profile_combo.currentIndex())

    def _on_profile_selected(self, index: int) -> None:
        name = self.profile_combo.itemData(index)
        if not name:
            return
        profile = self.ctx.store.get_profile(name)
        if profile is None:
            return
        self.name_edit.setText(profile.name)
        self.email_edit.setText(profile.email)
        self.access_edit.setText(profile.access_key)
        self.secret_edit.setText(profile.secret_key)
        self.host_edit.setText(profile.host)

    def _save_profile(self) -> None:
        name = self.name_edit.text().strip()
        access = self.access_edit.text().strip()
        secret = self.secret_edit.text().strip()
        if not name:
            self.ctx.notify_warning("Profile name required", "Give this profile a name.")
            return
        if not access or not secret:
            self.ctx.notify_warning(
                "Keys required",
                "Enter both the IAS3 access key and secret key, or use the email "
                "and password sign-in above.",
            )
            return
        profile = Profile(
            name=name,
            access_key=access,
            secret_key=secret,
            email=self.email_edit.text().strip(),
            host=self.host_edit.text().strip() or "archive.org",
        )
        self.ctx.store.save_profile(profile)
        if not self.ctx.store.active_name:
            self.ctx.store.set_active(name)
        self.refresh_profiles()
        self.ctx.reload_service()
        self.ctx.notify_info("Profile saved", f"Saved profile '{name}'.")

    def _delete_profile(self) -> None:
        name = self.profile_combo.currentData()
        if not name:
            return
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "Delete profile",
            f"Delete the saved profile '{name}'? The stored keys will be removed "
            "from your keychain. Uploaded items are not affected.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.ctx.store.delete_profile(name)
        self.refresh_profiles()
        self.ctx.reload_service()

    def _set_active(self) -> None:
        name = self.profile_combo.currentData()
        if not name:
            return
        self.ctx.set_active_profile(name)
        self.refresh_profiles()

    def _test_connection(self) -> None:
        access = self.access_edit.text().strip()
        secret = self.secret_edit.text().strip()
        if not access or not secret:
            profile = self.ctx.require_profile()
            if not profile:
                return
            access, secret = profile.access_key, profile.secret_key

        def work(reporter):
            reporter.report(message="Contacting archive.org", stage="account")
            return self.ctx.service.test_connection(access, secret)

        job = self.ctx.submit("account", "Test connection", work, pausable=False)

        def done(info: dict) -> None:
            username = info.get("username") or info.get("screenname") or "connected"
            self.ctx.notify_info("Connection OK", f"Signed in as {username}.")

        self.watch_job(job, done)

    def _sign_in(self) -> None:
        email = self.login_email.text().strip()
        password = self.login_password.text()
        if not email or not password:
            self.ctx.notify_warning(
                "Email and password required",
                "Enter the email address and password for your archive.org account.",
            )
            return
        host = self.host_edit.text().strip() or "archive.org"

        def work(reporter):
            reporter.report(message="Requesting IAS3 keys", stage="account")
            return self.ctx.service.login_with_password(email, password, host)

        job = self.ctx.submit("account", "Sign in", work, pausable=False)

        def done(result: dict) -> None:
            self.access_edit.setText(result.get("access_key", ""))
            self.secret_edit.setText(result.get("secret_key", ""))
            self.email_edit.setText(email)
            self.host_edit.setText(host)
            if result.get("screenname") and not self.name_edit.text().strip():
                self.name_edit.setText(result["screenname"])
            self.ctx.notify_info(
                "Keys retrieved",
                "Your IAS3 keys were filled in. Give the profile a name and click "
                "Save profile to keep them.",
            )

        self.watch_job(job, done)

    # -- preferences -------------------------------------------------------
    def _on_theme_changed(self, value: str) -> None:
        from PySide6.QtWidgets import QApplication

        self.ctx.settings.set("theme", value)
        from archivary.ui.theme import apply_theme

        apply_theme(QApplication.instance(), value)

    def _on_concurrency_changed(self, value: int) -> None:
        self.ctx.settings.set("max_concurrent_jobs", value)
        self.ctx.queue.set_max_concurrent(value)

    def on_profile_changed(self) -> None:
        if self._built:
            self.refresh_profiles()
