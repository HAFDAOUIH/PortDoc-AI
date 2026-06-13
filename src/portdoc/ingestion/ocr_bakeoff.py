"""OCR bake-off: which engine reads the French scan best?

There is no published FR OCR head-to-head, so we make our own evidence. Crucially,
our scan was rendered from the *digital* pages 13-16 of the Casablanca regulation —
so we have the EXACT correct text as ground truth and can compute real accuracy
(character similarity, word error rate, accent retention), not eyeballed guesses.

Engines compared (all swapped via Docling's `ocr_options`, one line each):
  - Tesseract fra+eng  (our pick)
  - EasyOCR            (Docling's default — the one we expect to lose on French)
  - RapidOCR           (lightweight ONNX alternative)

Output: results/ocr_bakeoff.md

Run:  uv run python -m portdoc.ingestion.ocr_bakeoff
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pypdfium2 as pdfium

from portdoc.config import get_settings

SOURCE_DOC = "anp-reglement-casablanca-fr.pdf"   # digital source of the scan
SCAN_DOC = "circulaire-securite-md-scan-fr.pdf"  # the image-only version
SOURCE_PAGES = (12, 13, 14, 15)                  # 0-indexed -> pages 13-16
ACCENTS = "éèêëàâäçùûüôîïŒœ"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def ground_truth(raw: Path) -> str:
    pdf = pdfium.PdfDocument(str(raw / SOURCE_DOC))
    try:
        parts = []
        for i in SOURCE_PAGES:
            page = pdf[i]
            tp = page.get_textpage()
            parts.append(tp.get_text_range())
            tp.close()
            page.close()
        return "\n".join(parts)
    finally:
        pdf.close()


def char_similarity(ref: str, hyp: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, ref, hyp).ratio()


def _edit_distance(r: list[str], h: list[str]) -> int:
    prev = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        cur = [i] + [0] * len(h)
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(h)]


def word_error_rate(ref: str, hyp: str) -> float:
    r, h = ref.split(), hyp.split()
    if not r:
        return 0.0
    return _edit_distance(r, h) / len(r)


def accent_count(s: str) -> int:
    return sum(s.count(c) for c in ACCENTS)


def _converter(engine: str):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        RapidOcrOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Table structure off: isolate OCR quality and keep the bake-off fast.
    opts = PdfPipelineOptions(do_ocr=True, do_table_structure=False)
    if engine == "tesseract":
        opts.ocr_options = TesseractCliOcrOptions(lang=["fra", "eng"], force_full_page_ocr=True)
    elif engine == "easyocr":
        opts.ocr_options = EasyOcrOptions(lang=["fr", "en"], force_full_page_ocr=True)
    elif engine == "rapidocr":
        opts.ocr_options = RapidOcrOptions(force_full_page_ocr=True)
    else:
        raise ValueError(engine)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def run_engine(engine: str, scan_path: Path) -> tuple[str, float]:
    t0 = time.perf_counter()
    result = _converter(engine).convert(str(scan_path))
    text = result.document.export_to_markdown()
    return text, time.perf_counter() - t0


def main() -> int:
    settings = get_settings()
    settings.ensure_dirs()
    raw = settings.raw_dir
    scan = raw / SCAN_DOC

    gt = ground_truth(raw)
    gt_n = _norm(gt)
    gt_accents = accent_count(gt)
    print(f"Ground truth: {len(gt.split())} words, {gt_accents} accented chars\n")

    rows = []
    samples = {}
    for engine in ("tesseract", "easyocr", "rapidocr"):
        print(f"running {engine} ...", flush=True)
        try:
            text, secs = run_engine(engine, scan)
        except Exception as exc:  # noqa: BLE001
            print(f"  {engine} FAILED: {exc!r}")
            rows.append((engine, None, None, None, None, repr(exc)[:60]))
            continue
        hyp_n = _norm(text)
        sim = char_similarity(gt_n, hyp_n)
        wer = word_error_rate(gt_n, hyp_n)
        acc = accent_count(text)
        rows.append((engine, sim, wer, acc, secs, ""))
        samples[engine] = text
        print(f"  sim={sim:.1%}  WER={wer:.1%}  accents={acc}/{gt_accents}  {secs:.0f}s")

    # winner = best char similarity
    ok = [r for r in rows if r[1] is not None]
    winner = max(ok, key=lambda r: r[1])[0] if ok else "n/a"

    out = settings.results_dir / "ocr_bakeoff.md"
    lines = [
        "# OCR Bake-off — French scanned circular\n",
        f"Scored against ground truth ({gt_accents} accented chars, "
        f"{len(gt.split())} words) recovered from the digital source pages of the "
        "Casablanca regulation. Run on CPU.\n",
        "| Engine | Char similarity ↑ | Word error rate ↓ | Accents retained | Time |",
        "|---|---|---|---|---|",
    ]
    for eng, sim, wer, acc, secs, err in rows:
        if sim is None:
            lines.append(f"| {eng} | FAILED | — | — | — |")
        else:
            mark = " **(winner)**" if eng == winner else ""
            lines.append(
                f"| {eng}{mark} | {sim:.1%} | {wer:.1%} | {acc}/{gt_accents} "
                f"({acc / gt_accents:.0%}) | {secs:.0f}s |"
            )
    lines += [
        "",
        f"**Verdict: {winner}.** Higher char-similarity and accent retention is what "
        "matters for downstream French retrieval — a mangled `matières`→`matieres` "
        "silently breaks sparse search.",
        "",
        "## First 240 chars per engine (eyeball the accents)",
        "",
        "**Ground truth:**",
        "```",
        gt_n[:240],
        "```",
    ]
    for eng in ("tesseract", "easyocr", "rapidocr"):
        if eng in samples:
            lines += [f"**{eng}:**", "```", _norm(samples[eng])[:240], "```"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}  (winner: {winner})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
