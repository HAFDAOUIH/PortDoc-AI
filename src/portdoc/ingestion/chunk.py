"""Chunking: slice a DoclingDocument into searchable pieces with carried metadata.

Design choices (and why):
  - HybridChunker with the EMBEDDER's tokenizer (Qwen3-Embedding). Chunk size is
    measured in the same tokens the embedder will see, so a "512-token" chunk
    really fits the model — using a different tokenizer silently mis-sizes chunks.
  - Contextual header injection: the embedded `text` is prefixed with
    "{doc_title} > {heading_path}". A bare paragraph ("...48 heures avant
    l'arrivée...") is ambiguous; with its heading path it's anchored. This is the
    cheap, high-ROI version of contextual retrieval.
  - Two text fields per chunk: `text` (header-prefixed) is what we EMBED;
    `raw_text` (clean) is what the LLM QUOTES/cites. Don't make the model cite a
    heading breadcrumb we glued on.
  - Every chunk carries `clearance` from its document -> this is what the RBAC
    retrieval filter (§6.5) will enforce later.
  - `from_ocr` is carried so eval can slice quality by OCR provenance, and the UI
    can flag answers sourced from scanned docs.

Run:  uv run python -m portdoc.ingestion.chunk
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

from portdoc.config import get_settings
from portdoc.ingestion.manifest import ManifestEntry, load_manifest
from portdoc.ingestion.parse import parse_to_document


class Chunk(BaseModel):
    chunk_id: str          # f"{doc_id}:{seq}"
    doc_id: str
    text: str              # header-prefixed — this is what gets EMBEDDED
    raw_text: str          # clean — this is what the LLM cites/quotes
    heading_path: list[str]
    page_start: int
    page_end: int
    doc_type: str
    authority: str
    year: int
    lang: str
    clearance: int
    is_table: bool
    from_ocr: bool


def doc_title(entry: ManifestEntry) -> str:
    """Short human title used as the contextual prefix root."""
    return f"{entry.authority} {entry.doc_type} {entry.year}"


def make_contextual_text(title: str, headings: list[str], raw: str) -> str:
    """Prepend the document title + heading path to a chunk's text for embedding."""
    prefix = " > ".join([title, *headings])
    return f"{prefix}\n\n{raw}" if prefix else raw


def is_meaningful(chunk: "Chunk") -> bool:
    """Reject retrieval-noise chunks (bare page numbers, fragments). Tables always kept."""
    return chunk.is_table or len(chunk.raw_text.strip()) >= get_settings().min_chunk_chars


# The chunker is expensive to build (loads a tokenizer), so build it once.
_chunker = None


def _get_chunker():
    global _chunker
    if _chunker is not None:
        return _chunker

    from docling.chunking import HybridChunker

    settings = get_settings()
    try:
        # Match the embedder's tokenizer so chunk sizes reflect what it will see.
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer

        tok = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(settings.dense_model),
            max_tokens=settings.chunk_max_tokens,
        )
        _chunker = HybridChunker(tokenizer=tok, merge_peers=True)
    except Exception as exc:  # noqa: BLE001 — never let a tokenizer download block ingest
        print(f"[chunk] embedder tokenizer unavailable ({exc!r}); using default tokenizer")
        _chunker = HybridChunker(merge_peers=True)
    return _chunker


def _pages_of(doc_items) -> tuple[int, int]:
    pages = [p.page_no for it in doc_items for p in (it.prov or [])]
    return (min(pages), max(pages)) if pages else (0, 0)


def _has_table(doc_items) -> bool:
    from docling_core.types.doc.document import DocItemLabel

    return any(getattr(it, "label", None) == DocItemLabel.TABLE for it in doc_items)


def chunk_document(document, entry: ManifestEntry, used_ocr: bool) -> list[Chunk]:
    """Chunk one parsed DoclingDocument into Chunk records carrying full metadata."""
    chunker = _get_chunker()
    title = doc_title(entry)
    chunks: list[Chunk] = []
    for seq, ch in enumerate(chunker.chunk(dl_doc=document)):
        headings = list(ch.meta.headings or [])
        page_start, page_end = _pages_of(ch.meta.doc_items)
        chunks.append(
            Chunk(
                chunk_id=f"{entry.id}:{seq}",
                doc_id=entry.id,
                text=make_contextual_text(title, headings, ch.text),
                raw_text=ch.text,
                heading_path=headings,
                page_start=page_start,
                page_end=page_end,
                doc_type=entry.doc_type,
                authority=entry.authority,
                year=entry.year,
                lang=entry.lang,
                clearance=int(entry.effective_clearance),
                is_table=_has_table(ch.meta.doc_items),
                from_ocr=used_ocr,
            )
        )
    return chunks


def chunk_corpus() -> list[Chunk]:
    """Parse + chunk every manifest doc; write chunks.jsonl; return all chunks."""
    settings = get_settings()
    settings.ensure_dirs()
    manifest = load_manifest(settings.manifest_path)
    out_path = settings.corpus_dir / "chunks.jsonl"

    all_chunks: list[Chunk] = []
    with out_path.open("w", encoding="utf-8") as f:
        for entry in manifest:
            pdf = entry.raw_path(settings.raw_dir)
            document, used_ocr = parse_to_document(pdf)
            chunks = [c for c in chunk_document(document, entry, used_ocr) if is_meaningful(c)]
            for c in chunks:
                f.write(c.model_dump_json() + "\n")
            all_chunks.extend(chunks)
            print(
                f"  {entry.id:<32} {len(chunks):>3} chunks  "
                f"clr={int(entry.effective_clearance)}  ocr={used_ocr}"
            )
    return all_chunks


def _print_stats(chunks: list[Chunk]) -> None:
    n = len(chunks)
    tables = sum(c.is_table for c in chunks)
    ocr = sum(c.from_ocr for c in chunks)
    by_clr = {0: 0, 1: 0, 2: 0}
    for c in chunks:
        by_clr[c.clearance] += 1
    print(f"\nTotal: {n} chunks | tables: {tables} | from OCR: {ocr}")
    print(f"By clearance: public(0)={by_clr[0]}  internal(1)={by_clr[1]}  restricted(2)={by_clr[2]}")


def main() -> int:
    print("Chunking corpus...\n")
    chunks = chunk_corpus()
    _print_stats(chunks)
    print(f"\nWrote {get_settings().corpus_dir / 'chunks.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
