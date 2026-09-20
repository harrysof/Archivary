"""Small JSON-backed application settings store (no Qt dependency)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from archivary.constants import SETTINGS_FILE, ensure_dirs

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "theme": "system",  # system | dark | light
    "max_concurrent_jobs": 3,
    "download_dir": str(Path.home() / "Downloads" / "Archivary"),
    "default_identifier": "",
    "verify_checksums": False,
    "count_views": False,
    "checksum_skip": True,
    "delete_local_after_upload": False,
    "queue_derive": True,
    "upload_retries": 3,
    "download_concurrency": 3,
    "raw_logging": False,
    "bottom_panel_visible": True,
    "bottom_splitter_sizes": [520, 340],
    "window_geometry": "",
}


class SettingsStore:
    """Dictionary-like settings with defaults and JSON persistence."""

    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self.path = path
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self._data.update(stored)
        except (ValueError, OSError):
            log.warning("settings.json was unreadable; using defaults.")

    def save(self) -> None:
        ensure_dirs()
        try:
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            log.warning("Could not save settings: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, *, autosave: bool = True) -> None:
        self._data[key] = value
        if autosave:
            self.save()

    def update(self, values: dict[str, Any], *, autosave: bool = True) -> None:
        self._data.update(values)
        if autosave:
            self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
