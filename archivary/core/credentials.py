"""Credential and profile storage.

Secrets (IAS3 access/secret keys) are kept in the OS keychain via the
``keyring`` package.  If no keychain backend is available (headless Linux, a
frozen build without a secret service, ...) Archivary falls back to an
encrypted file in the user's config directory.  Non-secret profile metadata is
always stored as plain JSON so the account list can be shown without unlocking
the keychain.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import logging
import platform
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from archivary.constants import (
    FALLBACK_SECRET_FILE,
    KEYRING_SERVICE,
    PROFILES_FILE,
    ensure_dirs,
)

log = logging.getLogger(__name__)

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_IMPORTED = True
except Exception:  # pragma: no cover - optional dependency
    keyring = None  # type: ignore[assignment]
    KeyringError = Exception  # type: ignore[misc,assignment]
    KEYRING_IMPORTED = False

try:
    from cryptography.fernet import Fernet, InvalidToken

    CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[misc,assignment]
    CRYPTO_AVAILABLE = False


_SECRET_FIELDS = ("access_key", "secret_key")


@dataclass
class Profile:
    """A saved Internet Archive account."""

    name: str
    access_key: str = ""
    secret_key: str = ""
    email: str = ""
    host: str = "archive.org"
    screenname: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def public_dict(self) -> dict:
        data = asdict(self)
        for key in _SECRET_FIELDS:
            data.pop(key, None)
        return data


def _machine_id() -> str:
    """Best-effort stable machine identifier used for fallback encryption."""
    if platform.system() == "Windows":
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as handle:
                value, _ = winreg.QueryValueEx(handle, "MachineGuid")
                return str(value)
        except Exception:
            pass
    try:
        node = uuid.getnode()
    except Exception:
        node = 0
    return f"{platform.node()}-{getpass.getuser()}-{node}"


def _fernet_key() -> bytes:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        _machine_id().encode("utf-8"),
        b"archivary-fallback-v1",
        200_000,
    )
    return base64.urlsafe_b64encode(raw)


class EncryptedFileSecretStore:
    """Fallback secret store: a Fernet-encrypted JSON file.

    Without the ``cryptography`` package this degrades to Base64 obfuscation;
    that is only ever used when no OS keychain exists, and a warning is logged.
    """

    def __init__(self, path: Path = FALLBACK_SECRET_FILE) -> None:
        self.path = path

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_bytes()
            if CRYPTO_AVAILABLE:
                token = Fernet(_fernet_key())
                raw = token.decrypt(raw)
            else:
                raw = base64.b64decode(raw)
            return json.loads(raw.decode("utf-8"))
        except (InvalidToken, ValueError, OSError):
            log.warning("Could not read the encrypted credential fallback file.")
            return {}

    def _save(self, data: dict[str, dict]) -> None:
        ensure_dirs()
        raw = json.dumps(data).encode("utf-8")
        if CRYPTO_AVAILABLE:
            raw = Fernet(_fernet_key()).encrypt(raw)
        else:
            log.warning(
                "cryptography is not installed; fallback credentials are not "
                "securely encrypted."
            )
            raw = base64.b64encode(raw)
        self.path.write_bytes(raw)
        try:
            self.path.chmod(0o600)
        except OSError:  # pragma: no cover - Windows / FAT
            pass

    def get(self, name: str) -> dict | None:
        return self._load().get(name)

    def set(self, name: str, secret: dict) -> None:
        data = self._load()
        data[name] = secret
        self._save(data)

    def delete(self, name: str) -> None:
        data = self._load()
        if name in data:
            del data[name]
            self._save(data)


class CredentialStore:
    """Manages saved profiles and their secrets."""

    def __init__(self, profiles_file: Path = PROFILES_FILE) -> None:
        ensure_dirs()
        self.profiles_file = profiles_file
        self._fallback = EncryptedFileSecretStore()
        self._active = ""

    # -- profile metadata --------------------------------------------------
    def _load_meta(self) -> dict:
        if not self.profiles_file.exists():
            return {"profiles": [], "active": ""}
        try:
            return json.loads(self.profiles_file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            log.warning("profiles.json was unreadable; starting fresh.")
            return {"profiles": [], "active": ""}

    def _save_meta(self, meta: dict) -> None:
        ensure_dirs()
        self.profiles_file.write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    # -- secret backends ---------------------------------------------------
    @property
    def backend_name(self) -> str:
        if KEYRING_IMPORTED:
            try:
                backend = keyring.get_keyring()
                if "fail" not in backend.__class__.__name__.lower():
                    return f"keyring ({backend.__class__.__name__})"
            except Exception:
                pass
        if CRYPTO_AVAILABLE:
            return "encrypted file"
        return "obfuscated file"

    def _secret_key(self, name: str) -> str:
        return f"profile::{name}"

    def _get_secret(self, name: str) -> dict | None:
        if KEYRING_IMPORTED:
            try:
                blob = keyring.get_password(KEYRING_SERVICE, self._secret_key(name))
                if blob:
                    return json.loads(blob)
            except (KeyringError, ValueError, Exception) as exc:  # noqa: BLE001
                log.debug("keyring read failed for %s: %s", name, exc)
        return self._fallback.get(name)

    def _set_secret(self, name: str, secret: dict) -> None:
        if KEYRING_IMPORTED:
            try:
                keyring.set_password(
                    KEYRING_SERVICE, self._secret_key(name), json.dumps(secret)
                )
                return
            except (KeyringError, Exception) as exc:  # noqa: BLE001
                log.warning("keyring write failed, using fallback file: %s", exc)
        self._fallback.set(name, secret)

    def _delete_secret(self, name: str) -> None:
        if KEYRING_IMPORTED:
            try:
                keyring.delete_password(KEYRING_SERVICE, self._secret_key(name))
            except Exception:  # noqa: BLE001
                pass
        self._fallback.delete(name)

    # -- public API --------------------------------------------------------
    def list_profiles(self) -> list[Profile]:
        meta = self._load_meta()
        profiles: list[Profile] = []
        for entry in meta.get("profiles", []):
            name = entry.get("name", "")
            if not name:
                continue
            secret = self._get_secret(name) or {}
            profiles.append(
                Profile(
                    name=name,
                    access_key=secret.get("access_key", ""),
                    secret_key=secret.get("secret_key", ""),
                    email=entry.get("email", ""),
                    host=entry.get("host", "archive.org"),
                    screenname=entry.get("screenname", ""),
                )
            )
        return profiles

    def get_profile(self, name: str) -> Profile | None:
        for profile in self.list_profiles():
            if profile.name == name:
                return profile
        return None

    def save_profile(self, profile: Profile) -> None:
        meta = self._load_meta()
        entries = [e for e in meta.get("profiles", []) if e.get("name") != profile.name]
        entries.append(
            {
                "name": profile.name,
                "email": profile.email,
                "host": profile.host,
                "screenname": profile.screenname,
            }
        )
        entries.sort(key=lambda e: e["name"].lower())
        meta["profiles"] = entries
        if not meta.get("active"):
            meta["active"] = profile.name
        self._save_meta(meta)
        self._set_secret(
            profile.name,
            {"access_key": profile.access_key, "secret_key": profile.secret_key},
        )

    def delete_profile(self, name: str) -> None:
        meta = self._load_meta()
        meta["profiles"] = [e for e in meta.get("profiles", []) if e.get("name") != name]
        if meta.get("active") == name:
            meta["active"] = meta["profiles"][0]["name"] if meta["profiles"] else ""
        self._save_meta(meta)
        self._delete_secret(name)

    @property
    def active_name(self) -> str:
        return self._load_meta().get("active", "")

    def set_active(self, name: str) -> None:
        meta = self._load_meta()
        meta["active"] = name
        self._save_meta(meta)

    def active_profile(self) -> Profile | None:
        name = self.active_name
        return self.get_profile(name) if name else None
