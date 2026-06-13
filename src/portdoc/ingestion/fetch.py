"""Fetch the corpus from the manifest, verifying integrity by sha256.

Two modes, decided per-entry by whether a hash is present:

  bootstrap (sha256 is null):  download, compute the hash, print it so you can
      paste it back into the manifest. The file is kept but flagged UNVERIFIED.
  verify (sha256 present):     download (or reuse a cached file), recompute the
      hash, and HARD-FAIL on mismatch. A corrupted/changed source never slips
      silently into the index.

Idempotent: an already-present file whose hash matches is skipped, so re-running
`make fetch` is cheap.

Usage:  python -m portdoc.ingestion.fetch
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import httpx

from portdoc.config import get_settings
from portdoc.ingestion.manifest import ManifestEntry, load_manifest

_CHUNK = 1 << 16  # 64 KiB streaming reads


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for block in r.iter_bytes(_CHUNK):
                f.write(block)
    tmp.replace(dest)  # atomic-ish: never leave a half file at the real path


def fetch_entry(entry: ManifestEntry, raw_dir: Path) -> tuple[str, str]:
    """Returns (status, detail). status in {verified, bootstrapped, MISSING, MISMATCH, ERROR}."""
    dest = entry.raw_path(raw_dir)

    # If the file isn't on disk, try to download it (only possible with a url).
    if not dest.exists():
        if not entry.is_fetchable:
            return "MISSING", f"no local file and no url — place {dest.name} in raw/"
        try:
            _download(str(entry.url), dest)
        except Exception as exc:  # noqa: BLE001 — surface any fetch failure per-entry
            return "ERROR", repr(exc)

    # File is present (shipped locally or just downloaded): fingerprint it.
    digest = _sha256_file(dest)

    if not entry.is_bootstrapped:
        return "bootstrapped", digest  # print so the hash can be locked in the manifest
    if digest != entry.sha256:
        return "MISMATCH", f"expected {entry.sha256}, got {digest}"
    return "verified", digest


def main() -> int:
    settings = get_settings()
    settings.ensure_dirs()
    manifest = load_manifest(settings.manifest_path)

    print(f"Manifest: {len(manifest)} docs -> {settings.raw_dir}\n")
    failures = 0
    bootstrapped: list[tuple[str, str]] = []

    for entry in manifest:
        status, detail = fetch_entry(entry, settings.raw_dir)
        clr = entry.effective_clearance
        line = f"[{status:>12}] {entry.id:<28} clr={int(clr)} {entry.doc_type:<10}"
        if status == "bootstrapped":
            bootstrapped.append((entry.id, detail))
            print(f"{line}  sha256={detail}")
        elif status in {"MISMATCH", "ERROR", "MISSING"}:
            failures += 1
            print(f"{line}  !! {detail}")
        else:
            print(line)

    if bootstrapped:
        print("\nPaste these sha256 values back into manifest.yaml to lock integrity:")
        for doc_id, digest in bootstrapped:
            print(f"  {doc_id}: {digest}")

    if failures:
        print(f"\n{failures} entr(ies) failed integrity/fetch — see !! lines above.")
        return 1
    print("\nFetch complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
