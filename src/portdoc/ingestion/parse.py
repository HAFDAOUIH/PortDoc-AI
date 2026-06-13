"""Parse PDFs into clean Markdown, routing scanned vs born-digital.

Routing rule (don't trust the manifest's `scanned` flag — verify the bytes):
a page with very little extractable text is a scan. We probe text per page with
pypdfium2 (fast, no model load) and take the MEDIAN char count so one odd page
(e.g. a full-page figure in an otherwise digital report) can't flip the verdict.

Reading:
  born-digital -> Docling, OCR off, table structure on
  scanned      -> Docling, OCR on (Tesseract fra+eng), full-page OCR

Tesseract is the chosen engine; the bake-off (ocr_bakeoff.py) is what justifies
that choice over Docling's EasyOCR default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pypdfium2 as pdfium

from portdoc.config import get_settings


def page_char_counts(pdf_path: Path) -> list[int]:
    """Extractable (already-digital) characters per page. ~0 everywhere => a scan."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        counts = []
        for page in pdf:
            textpage = page.get_textpage()
            counts.append(len(textpage.get_text_range().strip()))
            textpage.close()
            page.close()
        return counts
    finally:
        pdf.close()


def needs_ocr(pdf_path: Path, threshold: int | None = None) -> bool:
    """True if the PDF is (mostly) scanned and must go through OCR."""
    thr = threshold if threshold is not None else get_settings().scanned_char_threshold
    counts = page_char_counts(pdf_path)
    if not counts:
        return True
    return median(counts) < thr


@dataclass
class ParsedDoc:
    doc_id: str
    markdown: str
    num_pages: int
    used_ocr: bool


# Docling converters are expensive to build (they load layout models), so build
# each variant once and reuse it across documents.
_converters: dict[bool, object] = {}


def _get_converter(do_ocr: bool):
    if do_ocr in _converters:
        return _converters[do_ocr]

    # Imported lazily so the lightweight routing probe doesn't pay docling's import cost.
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions(do_ocr=do_ocr, do_table_structure=True)
    if do_ocr:
        # CLI backend uses the system `tesseract` binary -> no extra C dependency.
        opts.ocr_options = TesseractCliOcrOptions(
            lang=list(get_settings().ocr_langs), force_full_page_ocr=True
        )
    conv = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    _converters[do_ocr] = conv
    return conv


def parse_to_document(pdf_path: Path, force_ocr: bool | None = None):
    """Parse one PDF to a DoclingDocument (what the chunker needs). Returns (doc, used_ocr)."""
    use_ocr = needs_ocr(pdf_path) if force_ocr is None else force_ocr
    result = _get_converter(use_ocr).convert(str(pdf_path))
    return result.document, use_ocr


def parse_pdf(pdf_path: Path, doc_id: str, force_ocr: bool | None = None) -> ParsedDoc:
    """Parse one PDF to Markdown, auto-routing to OCR unless `force_ocr` overrides."""
    doc, use_ocr = parse_to_document(pdf_path, force_ocr)
    return ParsedDoc(
        doc_id=doc_id,
        markdown=doc.export_to_markdown(),
        num_pages=len(doc.pages),
        used_ocr=use_ocr,
    )
