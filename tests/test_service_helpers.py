import hashlib

from archivary.services.ia_service import (
    IAService,
    UploadFile,
    collect_upload_files,
    friendly_url_to_identifier,
    human_eta,
    human_size,
    human_speed,
    md5_file,
)


def test_friendly_url_to_identifier():
    assert friendly_url_to_identifier("https://archive.org/details/nasa") == "nasa"
    assert (
        friendly_url_to_identifier("https://archive.org/download/nasa/file.txt") == "nasa"
    )
    assert friendly_url_to_identifier("  plain_id  ") == "plain_id"
    assert friendly_url_to_identifier("") == ""


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(512) == "512 B"
    assert human_size(2048).endswith("KB")
    assert human_speed(2048).endswith("/s")


def test_human_eta():
    assert human_eta(None) == "--:--"
    assert human_eta(65) == "01:05"
    assert human_eta(3661) == "1:01:01"


def test_collect_upload_files_preserves_folders(tmp_path):
    root = tmp_path / "tapes"
    (root / "sub").mkdir(parents=True)
    (root / "a.mp4").write_text("a")
    (root / "sub" / "b.mp4").write_text("b")
    files = collect_upload_files([str(root)])
    keys = sorted(f.key for f in files)
    assert keys == ["tapes/a.mp4", "tapes/sub/b.mp4"]


def test_collect_upload_files_flat(tmp_path):
    root = tmp_path / "tapes"
    root.mkdir()
    (root / "a.mp4").write_text("a")
    files = collect_upload_files([str(root)], flatten=True)
    assert [f.key for f in files] == ["a.mp4"]


def test_md5_file(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"hello world")
    assert md5_file(str(target)) == hashlib.md5(b"hello world").hexdigest()


def test_service_without_profile_is_unconfigured():
    service = IAService()
    assert service.configured is False


def test_upload_file_size_detected(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"12345")
    spec = UploadFile(str(target), "f.bin")
    assert spec.size == 5
