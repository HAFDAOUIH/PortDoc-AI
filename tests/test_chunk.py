"""Chunk metadata, contextual-header injection, and the Chunk schema."""

from pathlib import Path

import pytest

from portdoc.ingestion.chunk import Chunk, doc_title, is_meaningful, make_contextual_text
from portdoc.ingestion.manifest import ManifestEntry

RAW = Path(__file__).resolve().parents[1] / "data" / "corpus" / "raw"


def _entry(**over) -> ManifestEntry:
    base = dict(id="x", doc_type="report", authority="ANP", year=2024, lang="fr")
    base.update(over)
    return ManifestEntry(**base)


# --- contextual header injection (pure) -------------------------------------

def test_contextual_text_prepends_title_and_headings():
    out = make_contextual_text("ANP report 2024", ["Chapitre 2", "Sûreté"], "Le port...")
    assert out.startswith("ANP report 2024 > Chapitre 2 > Sûreté")
    assert out.endswith("Le port...")
    # the raw body is preserved verbatim after the prefix
    assert "Le port..." in out


def test_contextual_text_without_headings_still_has_title():
    out = make_contextual_text("ANP report 2024", [], "body")
    assert out == "ANP report 2024\n\nbody"


def test_doc_title_format():
    assert doc_title(_entry(authority="TangerMed", doc_type="procedure", year=2023)) == (
        "TangerMed procedure 2023"
    )


# --- Chunk schema -----------------------------------------------------------

def _mk(raw, is_table=False) -> Chunk:
    return Chunk(
        chunk_id="d:0", doc_id="d", text=raw, raw_text=raw, heading_path=[],
        page_start=1, page_end=1, doc_type="report", authority="A", year=2024,
        lang="fr", clearance=0, is_table=is_table, from_ocr=False,
    )


def test_meaningful_filter_drops_page_numbers_and_fragments():
    assert is_meaningful(_mk("17\n18")) is False          # bare page numbers
    assert is_meaningful(_mk("46")) is False
    assert is_meaningful(_mk("L'armateur doit communiquer 48 heures avant l'arrivée")) is True


def test_meaningful_filter_always_keeps_tables():
    # a short table cell still belongs to a table -> keep it
    assert is_meaningful(_mk("EXERCICE", is_table=True)) is True


def test_chunk_roundtrips_and_separates_embedded_vs_cited_text():
    c = Chunk(
        chunk_id="doc:0", doc_id="doc", text="TITLE > H\n\nbody", raw_text="body",
        heading_path=["H"], page_start=1, page_end=1, doc_type="procedure",
        authority="ANP", year=2024, lang="fr", clearance=2, is_table=False, from_ocr=True,
    )
    # embedded text carries the header; cited text stays clean
    assert c.text.startswith("TITLE")
    assert c.raw_text == "body"
    assert Chunk.model_validate_json(c.model_dump_json()) == c


# --- integration on a real doc (skipped if corpus absent; loads docling) ----

@pytest.mark.skipif(not RAW.exists(), reason="corpus not present")
@pytest.mark.slow
def test_real_doc_chunks_carry_metadata():
    from portdoc.ingestion.chunk import chunk_document
    from portdoc.ingestion.parse import parse_to_document

    entry = _entry(id="tmsa-comfin-t4-2024-fr", authority="TangerMed", year=2024)
    document, used_ocr = parse_to_document(RAW / "tmsa-comfin-t4-2024-fr.pdf")
    chunks = chunk_document(document, entry, used_ocr)

    assert len(chunks) >= 1
    c = chunks[0]
    assert c.chunk_id == "tmsa-comfin-t4-2024-fr:0"
    assert c.clearance == 0          # report -> public
    assert c.from_ocr is False       # this is a born-digital doc
    assert c.page_start >= 1
    assert c.text.startswith("TangerMed report 2024")  # contextual prefix present
