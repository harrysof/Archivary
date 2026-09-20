import csv

from archivary.services import spreadsheet


def _write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_read_csv_roundtrip(tmp_path):
    path = tmp_path / "batch.csv"
    _write_csv(
        path,
        [{"identifier": "item1", "title": "Hello", "subject": "a|b"}],
        ["identifier", "title", "subject"],
    )
    headers, rows = spreadsheet.read_table(str(path))
    assert "identifier" in headers
    assert rows[0]["title"] == "Hello"


def test_parse_upload_rows_splits_lists(tmp_path):
    path = tmp_path / "up.csv"
    _write_csv(
        path,
        [{"identifier": "item1", "file": "a.mp4|b.mp4", "subject": "one|two"}],
        ["identifier", "file", "subject"],
    )
    _, rows = spreadsheet.read_table(str(path))
    batches = spreadsheet.parse_upload_rows(rows)
    assert batches[0]["identifier"] == "item1"
    assert batches[0]["files"] == ["a.mp4", "b.mp4"]
    assert batches[0]["metadata"]["subject"] == ["one", "two"]


def test_parse_metadata_rows_skips_reserved(tmp_path):
    path = tmp_path / "meta.csv"
    _write_csv(
        path,
        [{"identifier": "item1", "file": "a.mp4", "title": "T"}],
        ["identifier", "file", "title"],
    )
    _, rows = spreadsheet.read_table(str(path))
    updates = spreadsheet.parse_metadata_rows(rows)
    assert updates == [("item1", {"title": "T"})]


def test_export_results_csv_and_json(tmp_path):
    rows = [{"identifier": "x", "subject": ["a", "b"]}]
    csv_path = spreadsheet.export_results(str(tmp_path / "out.csv"), rows)
    json_path = spreadsheet.export_results(str(tmp_path / "out.json"), rows)
    assert "x" in (tmp_path / "out.csv").read_text(encoding="utf-8")
    assert "identifier" in (tmp_path / "out.json").read_text(encoding="utf-8")
    assert csv_path.endswith("out.csv")
    assert json_path.endswith("out.json")
