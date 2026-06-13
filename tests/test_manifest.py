"""Manifest schema, clearance derivation, and integrity rules — pure functions."""

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from portdoc.ingestion.manifest import (
    Clearance,
    Manifest,
    ManifestEntry,
    load_manifest,
)


def _entry(**over) -> ManifestEntry:
    base = dict(
        id="x",
        url="https://example.org/x.pdf",
        doc_type="report",
        authority="ANP",
        year=2024,
        lang="fr",
    )
    base.update(over)
    return ManifestEntry(**base)


# --- clearance derivation ---------------------------------------------------

@pytest.mark.parametrize(
    "doc_type,expected",
    [
        ("report", Clearance.PUBLIC),
        ("regulation", Clearance.PUBLIC),
        ("circular", Clearance.INTERNAL),
        ("procedure", Clearance.INTERNAL),
    ],
)
def test_clearance_defaults_from_doc_type(doc_type, expected):
    assert _entry(doc_type=doc_type).effective_clearance == expected


def test_explicit_clearance_overrides_default():
    # A security procedure marked restricted must win over the type default.
    e = _entry(doc_type="procedure", clearance=2)
    assert e.effective_clearance == Clearance.RESTRICTED


def test_override_can_lower_clearance_too():
    e = _entry(doc_type="circular", clearance=0)
    assert e.effective_clearance == Clearance.PUBLIC


# --- bootstrap flag ---------------------------------------------------------

def test_is_bootstrapped_tracks_hash_presence():
    assert _entry(sha256=None).is_bootstrapped is False
    assert _entry(sha256="abc123").is_bootstrapped is True


def test_raw_path_uses_id_as_stem(tmp_path: Path):
    assert _entry(id="adii-2024").raw_path(tmp_path) == tmp_path / "adii-2024.pdf"


# --- schema validation ------------------------------------------------------

def test_bad_doc_type_rejected():
    with pytest.raises(ValidationError):
        _entry(doc_type="memo")


def test_bad_lang_rejected():
    with pytest.raises(ValidationError):
        _entry(lang="ar")  # Arabic is explicitly scoped out (FR/EN only)


def test_implausible_year_rejected():
    with pytest.raises(ValidationError):
        _entry(year=1800)


# --- manifest loader --------------------------------------------------------

def test_load_manifest_roundtrip(tmp_path: Path):
    p = tmp_path / "manifest.yaml"
    p.write_text(
        textwrap.dedent(
            """
            docs:
              - id: a
                url: https://example.org/a.pdf
                doc_type: report
                authority: TangerMed
                year: 2024
                lang: fr
              - id: b
                url: https://example.org/b.pdf
                doc_type: procedure
                authority: TangerMed
                year: 2023
                lang: fr
                clearance: 2
            """
        ),
        encoding="utf-8",
    )
    m = load_manifest(p)
    assert isinstance(m, Manifest)
    assert len(m) == 2
    assert m.docs[0].effective_clearance == Clearance.PUBLIC
    assert m.docs[1].effective_clearance == Clearance.RESTRICTED


def test_duplicate_ids_rejected(tmp_path: Path):
    p = tmp_path / "manifest.yaml"
    p.write_text(
        textwrap.dedent(
            """
            docs:
              - {id: dup, url: "https://e.org/1.pdf", doc_type: report, authority: A, year: 2024, lang: fr}
              - {id: dup, url: "https://e.org/2.pdf", doc_type: report, authority: A, year: 2024, lang: fr}
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(p)
