import hashlib
import os

from archivary.core.task import Reporter
from archivary.services.ia_service import IAService, UploadFile, UploadOptions


class _FakeFile:
    def __init__(self, md5: str | None = None) -> None:
        self.exists = md5 is not None
        self.md5 = md5


class _FakeItem:
    """Mimics the parts of internetarchive.Item that upload_files uses."""

    def __init__(self, remote_md5: str | None = None) -> None:
        self.remote_md5 = remote_md5
        self.upload_calls: list[dict] = []

    def get_file(self, key):
        return _FakeFile(self.remote_md5)

    def upload_file(self, body, key=None, metadata=None, queue_derive=False, headers=None,
                    retries=0, validate_identifier=False):
        size = 0
        # The library measures size by seeking (no read).
        body.seek(0, os.SEEK_END)
        size = body.tell()
        body.seek(0)
        # Requests then streams the payload, reading to EOF.
        read_total = 0
        while True:
            chunk = body.read(8192)
            if not chunk:
                break
            read_total += len(chunk)
        body.close()
        self.upload_calls.append(
            {
                "key": key,
                "size": size,
                "read_total": read_total,
                "headers": headers,
                "metadata": metadata,
            }
        )
        return object()


def test_upload_reports_progress_and_md5(tmp_path):
    payload = os.urandom(2 * 1024 * 1024 + 321)
    path = tmp_path / "a.bin"
    path.write_bytes(payload)

    item = _FakeItem()
    service = IAService()
    service.get_item = lambda identifier: item  # type: ignore[assignment]

    reporter = Reporter()
    updates: list[int] = []
    reporter.subscribe(lambda update: updates.append(update.processed or 0))

    result = service.upload_files(
        "item1",
        [UploadFile(str(path), "a.bin")],
        UploadOptions(verify=True),
        reporter,
    )

    assert result["uploaded"] == ["a.bin"]
    assert item.upload_calls[0]["read_total"] == len(payload)
    assert item.upload_calls[0]["headers"]["Content-MD5"] == hashlib.md5(payload).hexdigest()
    assert updates[-1] >= len(payload)


def test_checksum_skip_avoids_upload(tmp_path):
    payload = b"identical bytes"
    path = tmp_path / "a.bin"
    path.write_bytes(payload)
    local_md5 = hashlib.md5(payload).hexdigest()

    item = _FakeItem(remote_md5=local_md5)
    service = IAService()
    service.get_item = lambda identifier: item  # type: ignore[assignment]

    result = service.upload_files(
        "item1",
        [UploadFile(str(path), "a.bin")],
        UploadOptions(checksum_skip=True),
        Reporter(),
    )

    assert result["skipped"] == ["a.bin"]
    assert result["uploaded"] == []
    assert item.upload_calls == []
