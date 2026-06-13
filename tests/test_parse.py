"""Scanned-vs-digital routing logic, and OCR-bake-off metric correctness."""

from pathlib import Path

import pytest

from portdoc.ingestion import parse
from portdoc.ingestion.ocr_bakeoff import char_similarity, word_error_rate, accent_count

RAW = Path(__file__).resolve().parents[1] / "data" / "corpus" / "raw"


# --- routing decision (pure logic, mocked page counts) ----------------------

def test_needs_ocr_when_pages_have_little_text(monkeypatch):
    monkeypatch.setattr(parse, "page_char_counts", lambda p: [0, 2, 1, 0])
    assert parse.needs_ocr(Path("x.pdf"), threshold=50) is True


def test_no_ocr_for_text_rich_pages(monkeypatch):
    monkeypatch.setattr(parse, "page_char_counts", lambda p: [2400, 2600, 2500])
    assert parse.needs_ocr(Path("x.pdf"), threshold=50) is False


def test_median_resists_one_image_page(monkeypatch):
    # A single full-page figure in an otherwise digital report must not flip it.
    monkeypatch.setattr(parse, "page_char_counts", lambda p: [2400, 0, 2500, 2600])
    assert parse.needs_ocr(Path("x.pdf"), threshold=50) is False


def test_empty_pdf_routes_to_ocr(monkeypatch):
    monkeypatch.setattr(parse, "page_char_counts", lambda p: [])
    assert parse.needs_ocr(Path("x.pdf")) is True


# --- bake-off metrics (hand-checkable) --------------------------------------

def test_char_similarity_identical_is_one():
    assert char_similarity("matières dangereuses", "matières dangereuses") == 1.0


def test_word_error_rate_counts_one_substitution():
    # one of three words wrong -> WER = 1/3
    assert word_error_rate("a b c", "a x c") == pytest.approx(1 / 3)


def test_word_error_rate_perfect_is_zero():
    assert word_error_rate("port de casablanca", "port de casablanca") == 0.0


def test_accent_count():
    assert accent_count("matières à problèmes ç") == 4  # è, à, è, ç


# --- integration on the real corpus (skipped if files absent) ---------------

@pytest.mark.skipif(not RAW.exists(), reason="corpus not present")
def test_real_scan_routes_to_ocr():
    assert parse.needs_ocr(RAW / "circulaire-securite-md-scan-fr.pdf") is True


@pytest.mark.skipif(not RAW.exists(), reason="corpus not present")
def test_real_digital_doc_routes_to_text():
    assert parse.needs_ocr(RAW / "code-isps-fr.pdf") is False
