"""Translate raw exceptions into plain-language messages for the UI.

The GUI should almost never show a raw traceback.  :func:`describe_exception`
maps the failure modes Archivary actually encounters (bad credentials, item
already exists, network timeouts, rate limiting) onto a short human title plus
an actionable sentence, while preserving the original text as ``detail`` for
the "show details" log-panel toggle.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

try:  # pragma: no cover - import guard only
    from requests import exceptions as rexc
except Exception:  # pragma: no cover
    rexc = None

try:  # pragma: no cover - import guard only
    from internetarchive import exceptions as iaexc
except Exception:  # pragma: no cover
    iaexc = None


@dataclass
class FriendlyError:
    """A UI-friendly rendering of an exception."""

    title: str
    message: str
    detail: str = ""
    retryable: bool = False
    hints: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        if self.detail:
            return f"{self.title}\n\n{self.message}\n\nDetails: {self.detail}"
        return f"{self.title}\n\n{self.message}"


def _http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def describe_exception(exc: BaseException) -> FriendlyError:
    """Return a :class:`FriendlyError` describing ``exc``."""
    detail = f"{type(exc).__name__}: {exc}"

    # --- Internet Archive specific errors ---------------------------------
    if iaexc is not None:
        if isinstance(exc, getattr(iaexc, "AuthenticationError", ())):
            return FriendlyError(
                "Sign-in failed",
                "The Internet Archive did not accept these credentials.",
                detail,
                hints=["Check the access and secret key.", "Re-copy them from archive.org/account/s3.php"],
            )
        if isinstance(exc, getattr(iaexc, "ItemLocateError", ())):
            return FriendlyError(
                "Item not found",
                "That item either does not exist or is marked as dark (unavailable).",
                detail,
            )
        if isinstance(exc, getattr(iaexc, "InvalidChecksumError", ())):
            return FriendlyError(
                "Checksum mismatch",
                "A downloaded file did not match its Internet Archive checksum and was removed.",
                detail,
                retryable=True,
            )
        if isinstance(exc, getattr(iaexc, "AccountAPIError", ())):
            return FriendlyError(
                "Account API error",
                "The Internet Archive account service returned an error.",
                detail,
                retryable=True,
            )

    # --- Network ----------------------------------------------------------
    if rexc is not None:
        if isinstance(exc, getattr(rexc, "Timeout", ())) or isinstance(
            exc, (socket.timeout,)
        ):
            return FriendlyError(
                "Request timed out",
                "The Internet Archive did not respond in time. This is usually temporary.",
                detail,
                retryable=True,
            )
        if isinstance(exc, getattr(rexc, "ConnectionError", ())):
            return FriendlyError(
                "Network unavailable",
                "Archivary could not reach archive.org. Check your internet connection.",
                detail,
                retryable=True,
            )
        if isinstance(exc, getattr(rexc, "HTTPError", ())):
            status = _http_status(exc)
            text = str(exc)
            if "privileges to write to those collections" in text or (
                "Access Denied" in text and "collection" in text.lower()
            ):
                return FriendlyError(
                    "Cannot write to that collection",
                    "Your account does not have permission to upload into the "
                    "collection(s) you specified. Archive.org only lets you add items "
                    "to collections you own or that are open for public contribution.",
                    detail,
                    hints=[
                        "Remove the 'Collection' field in the Upload tab, or use an open "
                        "collection such as 'opensource' or 'community'.",
                        "Make sure the item identifier does not already belong to another "
                        "account.",
                    ],
                )
            if "already exists" in text.lower() or "item already exists" in text.lower():
                return FriendlyError(
                    "Item already exists",
                    "An item with that identifier already exists and cannot be "
                    "overwritten with these settings.",
                    detail,
                    hints=["Choose a new identifier, or enable Keep old version."],
                )
            if status in (401, 403):
                return FriendlyError(
                    "Permission denied",
                    "The Internet Archive refused this request. Your keys may be missing or lack "
                    "permission for this item.",
                    detail,
                    hints=["Verify the item identifier.", "Make sure you own the item."],
                )
            if status == 404:
                return FriendlyError(
                    "Not found",
                    "The requested item or file does not exist on archive.org.",
                    detail,
                )
            if status == 429:
                return FriendlyError(
                    "Rate limited",
                    "Too many requests were sent. Wait a minute and try again.",
                    detail,
                    retryable=True,
                )
            if status == 503:
                return FriendlyError(
                    "Internet Archive is busy",
                    "Archive.org S3 is temporarily overloaded (503 SlowDown). Try again shortly.",
                    detail,
                    retryable=True,
                )
            if status and status >= 500:
                return FriendlyError(
                    "Internet Archive server error",
                    f"archive.org returned HTTP {status}. This is a server-side problem.",
                    detail,
                    retryable=True,
                )
            return FriendlyError(
                "Request failed",
                f"archive.org returned HTTP {status}.",
                detail,
                retryable=bool(status and status >= 500),
            )

    # --- Local filesystem -------------------------------------------------
    if isinstance(exc, FileNotFoundError):
        return FriendlyError("File not found", f"A local file could not be found: {exc}", detail)
    if isinstance(exc, PermissionError):
        return FriendlyError(
            "Permission denied",
            "Archivary could not read or write a file. Check file permissions.",
            detail,
        )
    if isinstance(exc, (OSError, IOError)):
        return FriendlyError("File system error", str(exc), detail)
    if isinstance(exc, KeyboardInterrupt):
        return FriendlyError("Cancelled", "The operation was cancelled.", detail)

    # --- Fallback ---------------------------------------------------------
    message = str(exc).strip() or "An unexpected error occurred."
    return FriendlyError("Something went wrong", message, detail, retryable=True)
