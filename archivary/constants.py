"""Central place for filesystem paths and application-wide defaults."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from archivary import __app_name__

APP_NAME = __app_name__


def _config_root() -> Path:
    """Return the platform-appropriate application config directory."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def _data_root() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    return _config_root() / "data"


def _resource_root() -> Path:
    """Root that holds bundled read-only resources (assets, etc.).

    PyInstaller unpacks one-file builds into ``sys._MEIPASS``; in a source
    checkout the resources live at the project root next to the package.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


CONFIG_DIR = _config_root()
DATA_DIR = _data_root()
CACHE_DIR = DATA_DIR / "cache"

ASSETS_DIR = _resource_root() / "assets"
LOGO_FILE = ASSETS_DIR / "IA_logo.svg"

PROFILES_FILE = CONFIG_DIR / "profiles.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
FALLBACK_SECRET_FILE = CONFIG_DIR / "secrets.enc"
LOG_FILE = DATA_DIR / "archivary.log"
CHECKSUM_ARCHIVE = CACHE_DIR / "_checksum_archive.txt"

KEYRING_SERVICE = "Archivary"


def ensure_dirs() -> None:
    """Create the directories Archivary writes to if they are missing."""
    for directory in (CONFIG_DIR, DATA_DIR, CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# Upload chunk size used by internetarchive's verbose streaming path. Archivary
# relies on this constant to distinguish real upload payload reads from the
# library's internal checksum/seek passes when reporting progress.
UPLOAD_CHUNK_SIZE = 1048576

DEFAULT_SEARCH_FIELDS = [
    "identifier",
    "title",
    "mediatype",
    "date",
    "creator",
    "collection",
    "item_size",
    "downloads",
]

MEDIATYPES = [
    "data",
    "texts",
    "audio",
    "movies",
    "image",
    "software",
    "web",
    "collection",
    "etree",
]
