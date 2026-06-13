"""Corpus manifest: the typed, reproducible description of every source doc.

Why this exists (and isn't just a folder of PDFs):
  - reproducibility — anyone can rebuild the exact corpus from URLs + hashes,
  - integrity — sha256 catches a silently-changed or truncated download,
  - metadata at the source — doc_type/authority/year/lang/clearance are decided
    once, here, and flow through chunking -> Qdrant payload -> retrieval filters.

The `clearance` value is what powers the RBAC retrieval filter (§6.5). We derive
a sensible default from `doc_type`, but any entry can override it explicitly —
that's how a security/safety *procedure* gets marked restricted (2) while a
public annual *report* stays at 0.
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl

DocType = Literal["regulation", "report", "procedure", "circular"]
Lang = Literal["fr", "en"]


class Clearance(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    RESTRICTED = 2


# Default clearance by document type. Reports and published regulations are
# public; circulars are internal-administrative; procedures default to internal
# but a security/safety procedure should override to RESTRICTED in the manifest.
_DEFAULT_CLEARANCE: dict[str, Clearance] = {
    "report": Clearance.PUBLIC,
    "regulation": Clearance.PUBLIC,
    "circular": Clearance.INTERNAL,
    "procedure": Clearance.INTERNAL,
}


class ManifestEntry(BaseModel):
    id: str = Field(..., description="Stable slug; also the raw filename stem.")
    # url is optional: several official Moroccan sources block automated download,
    # so those docs ship locally in corpus/raw/ and are verified by sha256 alone.
    # When a url IS present, fetch can re-download a missing file from it.
    url: HttpUrl | None = None
    sha256: str | None = Field(
        default=None,
        description="Hex digest of the source bytes. Leave null to bootstrap on first fetch.",
    )
    doc_type: DocType
    authority: str = Field(..., description="Issuing body, e.g. ADII, ANP, TangerMed, CIRES.")
    year: int = Field(..., ge=1990, le=2100)
    lang: Lang
    scanned: bool = False
    # Optional explicit override; if None we derive from doc_type.
    clearance: Clearance | None = None

    @property
    def effective_clearance(self) -> Clearance:
        if self.clearance is not None:
            return self.clearance
        return _DEFAULT_CLEARANCE[self.doc_type]

    @property
    def is_bootstrapped(self) -> bool:
        """True once we have a real hash to verify against."""
        return bool(self.sha256)

    @property
    def is_fetchable(self) -> bool:
        """True if we can (re)download this doc; False = local-only, must ship in raw/."""
        return self.url is not None

    def raw_path(self, raw_dir: Path) -> Path:
        return raw_dir / f"{self.id}.pdf"


class Manifest(BaseModel):
    docs: list[ManifestEntry]

    def __len__(self) -> int:
        return len(self.docs)

    def __iter__(self):  # type: ignore[override]
        return iter(self.docs)


def load_manifest(path: Path) -> Manifest:
    """Parse + validate the YAML manifest. Raises on duplicate ids or bad schema."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    docs = raw.get("docs", [])
    manifest = Manifest(docs=docs)

    ids = [d.id for d in manifest.docs]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate manifest ids: {sorted(dupes)}")
    return manifest
