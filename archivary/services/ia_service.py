"""Service layer around the official ``internetarchive`` library.

Nothing in this module imports PySide6.  Every network operation takes an
optional :class:`~archivary.core.task.Reporter`, through which it publishes
progress and observes pause/cancel requests.  This makes the whole backend
drivable from a plain script or a CLI-less test suite.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import internetarchive
from internetarchive import exceptions as ia_exceptions

from archivary.core.credentials import Profile
from archivary.core.task import JobCancelled, Reporter, reporter_or_null

log = logging.getLogger(__name__)

DEFAULT_RETRIES = 3
DOWNLOAD_CHUNK = 1024 * 1024


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------
@dataclass
class UploadFile:
    """A local file to upload and the remote name it should get."""

    path: str
    key: str
    size: int = 0

    def __post_init__(self) -> None:
        if not self.size:
            try:
                self.size = os.path.getsize(self.path)
            except OSError:
                self.size = 0


@dataclass
class DownloadSpec:
    """A single file selected for download."""

    name: str
    size: int = 0
    format: str = ""
    md5: str = ""
    sha1: str = ""
    mtime: float = 0.0
    url: str = ""

    @classmethod
    def from_file(cls, ia_file) -> DownloadSpec:
        return cls(
            name=ia_file.name,
            size=int(ia_file.size or 0),
            format=ia_file.format or "",
            md5=ia_file.md5 or "",
            sha1=getattr(ia_file, "sha1", "") or "",
            mtime=float(ia_file.mtime or 0),
            url=getattr(ia_file, "url", "") or "",
        )


@dataclass
class UploadOptions:
    metadata: dict = field(default_factory=dict)
    queue_derive: bool = True
    checksum_skip: bool = False
    verify: bool = False
    delete_local: bool = False
    keep_old_version: bool = False
    retries: int = DEFAULT_RETRIES
    validate_identifier: bool = False


@dataclass
class DownloadOptions:
    ignore_existing: bool = True
    verify_checksum: bool = False
    no_directory: bool = False
    count_views: bool = False
    resume: bool = True
    retries: int = DEFAULT_RETRIES
    concurrency: int = 3
    glob_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def collect_upload_files(paths: Iterable[str], flatten: bool = False) -> list[UploadFile]:
    """Expand files and folders into upload targets, preserving folder names.

    A directory ``/data/vhs/tapes`` containing ``a.mp4`` and ``sub/b.mp4``
    yields keys ``tapes/a.mp4`` and ``tapes/sub/b.mp4``.
    """
    results: list[UploadFile] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            base_parent = path.parent
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    key = child.name if flatten else child.relative_to(base_parent).as_posix()
                    results.append(UploadFile(str(child), key))
        elif path.is_file():
            results.append(UploadFile(str(path), path.name))
    return results


def md5_file(path: str, reporter: Reporter | None = None) -> str:
    """Compute the MD5 of a local file, yielding to pause/cancel checks."""
    digest = hashlib.md5()  # noqa: S324 - MD5 is required by the IA-S3 protocol
    size = 0
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    with open(path, "rb") as handle:
        done = 0
        while True:
            if reporter is not None:
                reporter.checkpoint()
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            done += len(chunk)
            if reporter is not None:
                reporter.report(
                    processed=done, total=size, message="Hashing", stage="hashing"
                )
    return digest.hexdigest()


class _UploadReader:
    """File-like wrapper that reports upload progress and honours cancel/pause.

    The library's own checksum passes are bypassed by the service (we compute
    MD5 ourselves and pass it as a ``Content-MD5`` header), so every byte read
    here is genuine upload payload.
    """

    def __init__(self, path: str, on_read) -> None:
        self._path = path
        self._fh = open(path, "rb")  # noqa: SIM115 - closed by internetarchive
        self._on_read = on_read
        self.processed = 0

    @property
    def name(self) -> str:
        return self._path

    def read(self, size: int = -1) -> bytes:
        if self._fh.closed:
            return b""
        data = self._fh.read(size)
        if data:
            self.processed += len(data)
            self._on_read(self.processed)
        return data

    def seek(self, offset: int, whence: int = 0):
        if offset == 0 and whence == 0 and self.processed:
            self.processed = 0
            self._on_read(0)
        return self._fh.seek(offset, whence)

    def tell(self) -> int:
        return self._fh.tell()

    def close(self) -> None:
        try:
            if not self._fh.closed:
                self._fh.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class IAService:
    """Thin, GUI-free wrapper around the ``internetarchive`` library."""

    def __init__(self, profile: Profile | None = None) -> None:
        self.profile = profile
        self._session = None

    # -- session -----------------------------------------------------------
    def set_profile(self, profile: Profile | None) -> None:
        self.profile = profile
        self._session = None

    @property
    def configured(self) -> bool:
        return bool(self.profile and self.profile.access_key and self.profile.secret_key)

    @property
    def session(self):
        if self._session is None:
            config: dict = {"general": {"secure": True}}
            if self.profile:
                config["s3"] = {
                    "access": self.profile.access_key,
                    "secret": self.profile.secret_key,
                }
                if self.profile.host:
                    config["general"]["host"] = self.profile.host
                config["general"]["user_agent_suffix"] = "Archivary"
            self._session = internetarchive.get_session(config)
        return self._session

    def connect(self, access_key: str, secret_key: str, host: str = "archive.org"):
        """Return an ad-hoc session for testing credentials before saving."""
        config = {
            "s3": {"access": access_key, "secret": secret_key},
            "general": {"secure": True, "host": host, "user_agent_suffix": "Archivary"},
        }
        return internetarchive.get_session(config)

    # -- account -----------------------------------------------------------
    def test_connection(self, access_key: str | None = None, secret_key: str | None = None) -> dict:
        """Validate credentials and return the account description."""
        if access_key and secret_key:
            info = internetarchive.get_user_info(access_key, secret_key)
            return dict(info)
        if not self.configured:
            raise RuntimeError("No credentials configured.")
        info = internetarchive.get_user_info(
            self.profile.access_key, self.profile.secret_key
        )
        return dict(info)

    def whoami(self) -> str:
        try:
            return self.session.whoami()
        except Exception:  # noqa: BLE001
            return ""

    def login_with_password(
        self, email: str, password: str, host: str = "archive.org"
    ) -> dict:
        """Exchange an email/password for IAS3 keys without writing a config file."""
        from internetarchive import config as ia_config

        auth_config = ia_config.get_auth_config(email, password, host)
        return {
            "access_key": auth_config.get("s3", {}).get("access", ""),
            "secret_key": auth_config.get("s3", {}).get("secret", ""),
            "screenname": auth_config.get("general", {}).get("screenname", ""),
        }

    # -- item metadata / listing ------------------------------------------
    def get_item(self, identifier: str):
        return internetarchive.get_item(identifier, archive_session=self.session)

    def item_metadata(self, identifier: str) -> dict:
        item = self.get_item(identifier)
        return dict(item.item_metadata)

    def list_files(
        self,
        identifier: str,
        *,
        glob_patterns: Sequence[str] | None = None,
        exclude_patterns: Sequence[str] | None = None,
        formats: Sequence[str] | None = None,
        on_the_fly: bool = False,
    ) -> list[DownloadSpec]:
        item = self.get_item(identifier)
        files = item.get_files(
            formats=list(formats) if formats else None,
            glob_pattern=_join_patterns(glob_patterns),
            exclude_pattern=_join_patterns(exclude_patterns),
            on_the_fly=on_the_fly,
        )
        return [DownloadSpec.from_file(f) for f in files]

    def list_file_objects(self, identifier: str, names: Sequence[str]):
        item = self.get_item(identifier)
        return [item.get_file(name) for name in names]

    # -- search ------------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        fields: Sequence[str] | None = None,
        sorts: Sequence[str] | None = None,
        params: dict | None = None,
        limit: int | None = None,
        full_text_search: bool = False,
        reporter: Reporter | None = None,
    ) -> tuple[list[dict], int]:
        reporter = reporter_or_null(reporter)
        params = dict(params or {})
        if limit:
            params.setdefault("rows", min(limit, 1000))
        results: list[dict] = []
        search = internetarchive.search_items(
            query,
            fields=list(fields) if fields else None,
            sorts=list(sorts) if sorts else None,
            params=params,
            full_text_search=full_text_search,
            archive_session=self.session,
        )
        total = int(getattr(search, "num_found", 0) or 0)
        for row in search:
            reporter.checkpoint()
            results.append(dict(row))
            if limit and len(results) >= limit:
                break
            if len(results) % 25 == 0 or len(results) == 1:
                reporter.report(
                    processed=len(results),
                    total=total or None,
                    message=f"{len(results)} results",
                    stage="search",
                )
        reporter.report(
            processed=len(results), total=total or len(results), message="Done", stage="search"
        )
        return results, total

    # -- upload ------------------------------------------------------------
    def upload_files(
        self,
        identifier: str,
        files: Sequence[UploadFile],
        options: UploadOptions | None = None,
        reporter: Reporter | None = None,
    ) -> dict:
        reporter = reporter_or_null(reporter)
        options = options or UploadOptions()
        files = list(files)
        if not files:
            raise ValueError("No files selected for upload.")

        item = self.get_item(identifier)
        grand_total = sum(f.size for f in files) or 1
        base = 0
        uploaded: list[str] = []
        skipped: list[str] = []

        existing_md5: dict[str, str | None] = {}
        if options.checksum_skip:
            for target in files:
                try:
                    remote = item.get_file(target.key)
                    existing_md5[target.key] = (
                        remote.md5 if getattr(remote, "exists", False) else None
                    )
                except Exception:  # noqa: BLE001
                    existing_md5[target.key] = None

        for index, target in enumerate(files, start=1):
            reporter.checkpoint()
            remote_md5 = None
            if options.checksum_skip or options.verify or options.delete_local:
                reporter.report(
                    processed=base,
                    total=grand_total,
                    message=f"Hashing {target.key}",
                    stage="hashing",
                )
                local_md5 = md5_file(target.path, reporter)
                remote_md5 = existing_md5.get(target.key)
                if options.checksum_skip and remote_md5 and remote_md5 == local_md5:
                    base += target.size
                    skipped.append(target.key)
                    reporter.report(
                        processed=base,
                        total=grand_total,
                        message=f"Skipped {target.key} (already uploaded)",
                        stage="upload",
                    )
                    continue

            headers: dict[str, str] = {}
            if remote_md5 is not None or options.verify or options.delete_local:
                headers["Content-MD5"] = local_md5
            if options.keep_old_version:
                headers["x-archive-keep-old-version"] = "1"

            def on_read(done: int, _base=base) -> None:
                reporter.report(
                    processed=_base + done,
                    total=grand_total,
                    message=f"Uploading {target.key} ({index}/{len(files)})",
                    stage="upload",
                )

            reader = _UploadReader(target.path, on_read)
            reporter.report(
                processed=base,
                total=grand_total,
                message=f"Uploading {target.key} ({index}/{len(files)})",
                stage="upload",
            )
            item.upload_file(
                reader,
                key=target.key,
                metadata=options.metadata or None,
                queue_derive=options.queue_derive,
                headers=headers,
                retries=options.retries,
                validate_identifier=options.validate_identifier and index == 1,
            )
            base += target.size
            uploaded.append(target.key)
            reporter.report(
                processed=base,
                total=grand_total,
                message=f"Uploaded {target.key}",
                stage="upload",
            )
            if options.delete_local:
                try:
                    os.remove(target.path)
                except OSError as exc:  # noqa: BLE001
                    log.warning("Could not delete %s: %s", target.path, exc)

        reporter.report(
            processed=grand_total, total=grand_total, message="Upload complete", stage="done"
        )
        return {
            "identifier": identifier,
            "uploaded": uploaded,
            "skipped": skipped,
            "url": f"https://archive.org/details/{identifier}",
        }

    # -- download ----------------------------------------------------------
    def download_files(
        self,
        identifier: str,
        destdir: str,
        specs: Sequence[DownloadSpec] | None = None,
        options: DownloadOptions | None = None,
        reporter: Reporter | None = None,
    ) -> dict:
        reporter = reporter_or_null(reporter)
        options = options or DownloadOptions()
        if specs is None:
            specs = self.list_files(
                identifier,
                glob_patterns=options.glob_patterns,
                exclude_patterns=options.exclude_patterns,
                formats=options.formats,
            )
        specs = list(specs)
        if not specs:
            reporter.report(processed=1, total=1, message="No matching files", stage="done")
            return {"identifier": identifier, "files": [], "destdir": destdir}

        dest = Path(destdir)
        total = sum(s.size for s in specs) or 1
        lock = threading.Lock()
        state = {"processed": 0}

        def bump(delta: int, message: str) -> None:
            with lock:
                state["processed"] += delta
                reporter.report(
                    processed=min(state["processed"], total) if delta >= 0 else state["processed"],
                    total=total,
                    message=message,
                    stage="download",
                )

        skipped: list[str] = []
        downloaded: list[str] = []

        workers = max(1, min(options.concurrency, len(specs)))
        reporter.report(processed=0, total=total, message="Starting download", stage="download")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self._download_one,
                    spec,
                    dest,
                    identifier,
                    options,
                    reporter,
                    bump,
                ): spec
                for spec in specs
            }
            try:
                for future in as_completed(futures):
                    spec = futures[future]
                    try:
                        result = future.result()
                    except JobCancelled:
                        raise
                    if result == "skipped":
                        skipped.append(spec.name)
                    else:
                        downloaded.append(spec.name)
            except JobCancelled:
                for future in futures:
                    future.cancel()
                raise

        reporter.report(
            processed=total, total=total, message="Download complete", stage="done"
        )
        return {
            "identifier": identifier,
            "files": downloaded,
            "skipped": skipped,
            "destdir": str(dest),
        }

    def _download_one(
        self,
        spec: DownloadSpec,
        dest: Path,
        identifier: str,
        options: DownloadOptions,
        reporter: Reporter,
        bump,
    ) -> str:
        if options.no_directory:
            file_path = dest / os.path.basename(spec.name)
        else:
            file_path = dest / identifier / spec.name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if options.ignore_existing and file_path.exists() and file_path.stat().st_size == spec.size:
            bump(spec.size, f"Skipping existing {spec.name}")
            return "skipped"

        if options.verify_checksum and file_path.exists() and spec.md5:
            reporter.checkpoint()
            if file_path.stat().st_size == spec.size and md5_file(str(file_path)) == spec.md5:
                bump(spec.size, f"Skipping verified {spec.name}")
                return "skipped"

        headers: dict[str, str] = {}
        mode = "wb"
        resume_from = 0
        if options.resume and file_path.exists():
            existing = file_path.stat().st_size
            if 0 < existing < spec.size:
                resume_from = existing
                headers["Range"] = f"bytes={existing}-"
                mode = "ab"

        params = {} if options.count_views else {"cnt": "0"}
        url = spec.url or f"https://archive.org/download/{identifier}/{spec.name}"
        request_kwargs: dict = {"stream": True, "timeout": 120, "params": params}
        # archive.org public files need no auth; the session carries credentials
        # for restricted items automatically.

        response = self.session.get(url, headers=headers, **request_kwargs)
        try:
            # A 416 means the local partial file is already complete (or the
            # remote changed). Fall back to a full download rather than failing.
            if response.status_code == 416 and resume_from:
                response.close()
                resume_from = 0
                mode = "wb"
                headers.pop("Range", None)
                response = self.session.get(url, headers=headers, **request_kwargs)
            response.raise_for_status()

            with open(file_path, mode) as handle:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
                    reporter.checkpoint()
                    if not chunk:
                        continue
                    handle.write(chunk)
                    bump(len(chunk), f"Downloading {spec.name}")
        finally:
            response.close()

        if options.verify_checksum and spec.md5:
            if md5_file(str(file_path)) != spec.md5:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                raise ia_exceptions.InvalidChecksumError(
                    f"{spec.name} checksum did not match after download"
                )

        if spec.mtime:
            try:
                os.utime(file_path, (spec.mtime, spec.mtime))
            except OSError:
                pass
        return "downloaded"

    # -- metadata ----------------------------------------------------------
    def modify_metadata(
        self,
        identifier: str,
        metadata: dict,
        *,
        append: bool = False,
        append_list: bool = False,
        reporter: Reporter | None = None,
    ):
        reporter = reporter_or_null(reporter)
        reporter.report(message="Updating metadata", stage="metadata")
        item = self.get_item(identifier)
        response = item.modify_metadata(
            metadata, append=append, append_list=append_list, refresh=False
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        reporter.report(processed=1, total=1, message="Metadata updated", stage="done")
        return response

    def remove_metadata_field(
        self,
        identifier: str,
        field_name: str,
        reporter: Reporter | None = None,
    ):
        """Remove a metadata field by sending the IA ``REMOVE_TAG`` sentinel."""
        return self.modify_metadata(identifier, {field_name: "REMOVE_TAG"}, reporter=reporter)

    def batch_modify_metadata(
        self,
        updates: Sequence[tuple[str, dict]],
        *,
        append: bool = False,
        append_list: bool = False,
        reporter: Reporter | None = None,
    ) -> dict:
        reporter = reporter_or_null(reporter)
        total = len(updates)
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        for index, (identifier, metadata) in enumerate(updates, start=1):
            reporter.checkpoint()
            try:
                self.modify_metadata(
                    identifier, metadata, append=append, append_list=append_list
                )
                succeeded.append(identifier)
            except JobCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                failed.append((identifier, str(exc)))
            reporter.report(
                processed=index,
                total=total,
                message=f"Updated {identifier} ({index}/{total})",
                stage="metadata",
            )
        return {"succeeded": succeeded, "failed": failed}

    # -- delete ------------------------------------------------------------
    def delete_files(
        self,
        identifier: str,
        names: Sequence[str],
        *,
        cascade_delete: bool = False,
        reporter: Reporter | None = None,
    ) -> dict:
        reporter = reporter_or_null(reporter)
        if not names:
            raise ValueError("No files selected for deletion.")
        names = list(names)
        total = len(names)
        deleted: list[str] = []
        for index, name in enumerate(names, start=1):
            reporter.checkpoint()
            reporter.report(
                processed=index - 1,
                total=total,
                message=f"Deleting {name}",
                stage="delete",
            )
            responses = internetarchive.delete(
                identifier,
                files=[name],
                cascade_delete=cascade_delete,
                access_key=self.profile.access_key if self.profile else None,
                secret_key=self.profile.secret_key if self.profile else None,
                archive_session=self.session,
            )
            for response in responses:
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            deleted.append(name)
        reporter.report(processed=total, total=total, message="Deleted", stage="done")
        return {"identifier": identifier, "deleted": deleted}

    # -- tasks -------------------------------------------------------------
    def get_tasks(
        self,
        identifier: str = "",
        params: dict | None = None,
        reporter: Reporter | None = None,
    ) -> list[dict]:
        reporter = reporter_or_null(reporter)
        reporter.report(message="Fetching tasks", stage="tasks")
        tasks = internetarchive.get_tasks(
            identifier=identifier,
            params=params or {"catalog": "1", "history": "1", "summary": "0", "limit": "0"},
            archive_session=self.session,
        )
        rows = []
        for task in tasks:
            data = dict(task.task_dict)
            data["task_id"] = getattr(task, "task_id", None)
            rows.append(data)
        rows.sort(key=lambda r: str(r.get("submittime", "")), reverse=True)
        reporter.report(processed=len(rows), total=len(rows), message="Tasks loaded", stage="done")
        return rows

    def get_task_log(self, task_id) -> str:
        from internetarchive.catalog import CatalogTask

        return CatalogTask.get_task_log(task_id, self.session)

    def submit_task(
        self,
        identifier: str,
        cmd: str,
        comment: str = "",
        priority: int = 0,
        data: dict | None = None,
    ):
        catalog = internetarchive.Catalog(self.session)
        response = catalog.submit_task(
            identifier, cmd, comment=comment or None, priority=priority, data=data
        )
        response.raise_for_status()
        return response


def _join_patterns(patterns: Sequence[str] | None) -> str | list[str] | None:
    if not patterns:
        return None
    cleaned = [p.strip() for p in patterns if p and p.strip()]
    return cleaned or None


def friendly_url_to_identifier(value: str) -> str:
    """Extract an identifier from an archive.org URL, or return the input.

    Handles ``https://archive.org/details/<id>``,
    ``https://archive.org/download/<id>/file`` and bare identifiers.
    """
    text = value.strip()
    if not text:
        return ""
    if "archive.org" not in text:
        return text
    for marker in ("/details/", "/download/", "/metadata/", "/embed/"):
        if marker in text:
            tail = text.split(marker, 1)[1]
            return tail.split("/", 1)[0].split("?", 1)[0]
    if "identifier=" in text:
        return text.split("identifier=", 1)[1].split("&", 1)[0]
    return text.rstrip("/").split("/")[-1]


def human_size(num: float) -> str:
    """Format a byte count as a short human-readable string."""
    if not num:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} EB"


def human_speed(bytes_per_second: float) -> str:
    return f"{human_size(bytes_per_second)}/s"


def human_eta(seconds: float | None) -> str:
    if not seconds or seconds != seconds or seconds <= 0 or seconds > 10 * 365 * 86400:
        return "--:--"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


__all__ = [
    "IAService",
    "UploadFile",
    "DownloadSpec",
    "UploadOptions",
    "DownloadOptions",
    "collect_upload_files",
    "md5_file",
    "friendly_url_to_identifier",
    "human_size",
    "human_speed",
    "human_eta",
]
