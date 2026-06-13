"""Fetch integrity logic: local-file verification, bootstrap, mismatch, missing."""

from pathlib import Path

from portdoc.ingestion import fetch
from portdoc.ingestion.manifest import ManifestEntry


def _local_entry(sha256=None) -> ManifestEntry:
    # No url -> a local-only doc that must already be present in raw/.
    return ManifestEntry(
        id="doc", sha256=sha256, doc_type="report", authority="ANP", year=2024, lang="fr"
    )


def _write(raw: Path, name: str, data: bytes) -> str:
    (raw / name).write_bytes(data)
    return fetch._sha256_file(raw / name)


def test_local_file_with_correct_hash_verifies(tmp_path: Path):
    h = _write(tmp_path, "doc.pdf", b"hello port")
    status, detail = fetch.fetch_entry(_local_entry(sha256=h), tmp_path)
    assert status == "verified"


def test_local_file_without_hash_bootstraps(tmp_path: Path):
    h = _write(tmp_path, "doc.pdf", b"hello port")
    status, digest = fetch.fetch_entry(_local_entry(sha256=None), tmp_path)
    assert status == "bootstrapped"
    assert digest == h  # the printed hash matches the file, ready to lock in


def test_local_file_wrong_hash_mismatches(tmp_path: Path):
    _write(tmp_path, "doc.pdf", b"hello port")
    status, _ = fetch.fetch_entry(_local_entry(sha256="0" * 64), tmp_path)
    assert status == "MISMATCH"


def test_missing_local_file_without_url_is_reported(tmp_path: Path):
    # No file on disk and no url to fetch from -> actionable MISSING, not a crash.
    status, detail = fetch.fetch_entry(_local_entry(sha256="abc"), tmp_path)
    assert status == "MISSING"
    assert "raw/" in detail
