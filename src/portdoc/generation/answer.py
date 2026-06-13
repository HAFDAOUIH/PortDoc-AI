"""Generation: retrieved chunks -> a cited, grounded answer (or an honest refusal).

generate() is the top of the QUERY pipeline: it formats the top-k chunks as numbered
sources, calls the LLM under the citation/refusal contract (prompts.py), then validates
the output with the citation parser (citations.py) and maps citations back to sources.

CLI:
  uv run python -m portdoc.generation.answer ask "ma question" [clearance]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from portdoc.config import get_settings
from portdoc.generation import llm, prompts
from portdoc.generation.citations import parse_answer
from portdoc.retrieval.pipeline import ScoredChunk, retrieve


@dataclass
class Source:
    n: int
    doc_id: str
    page_start: int
    authority: str
    doc_type: str
    year: int
    clearance: int
    raw_text: str


@dataclass
class Answer:
    text: str
    refused: bool
    sources: list[Source]          # the sources actually cited
    hallucinated: list[int]        # invented citation numbers (stripped + flagged)
    uncited_sentences: list[str]   # factual sentences lacking a citation
    raw: str


def _sources_block(chunks: list[ScoredChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        pl = c.payload
        meta = f"{pl['authority']} {pl['doc_type']} {pl['year']}, p.{pl['page_start']}"
        lines.append(f"[{i}] ({meta}) {pl['raw_text']}")
    return "\n\n".join(lines)


def _source_from_chunk(n: int, c: ScoredChunk) -> Source:
    pl = c.payload
    return Source(n, pl["doc_id"], pl["page_start"], pl["authority"], pl["doc_type"],
                  pl["year"], pl["clearance"], pl["raw_text"])


def generate(query: str, chunks: list[ScoredChunk]) -> Answer:
    if not chunks:
        return Answer("<NO_ANSWER/>", True, [], [], [], "<NO_ANSWER/>")

    messages = [
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.user_message(query, _sources_block(chunks))},
    ]
    s = get_settings()
    raw = llm.complete(messages, temperature=s.gen_temperature, max_tokens=s.gen_max_tokens)
    parsed = parse_answer(raw, len(chunks))
    sources = [_source_from_chunk(n, chunks[n - 1]) for n in parsed.citations]
    return Answer(parsed.text, parsed.refused, sources, parsed.hallucinated,
                  parsed.uncited_sentences, raw)


def answer_query(query: str, user_clearance: int | None = None) -> Answer:
    """End-to-end: retrieve (access-controlled) -> generate."""
    return generate(query, retrieve(query, user_clearance=user_clearance))


def _cli(query: str, clearance: int | None) -> None:
    a = answer_query(query, clearance)
    print(f"\nQ: {query}  (clearance={clearance})\n" + "=" * 72)
    if a.refused:
        print("REFUSED (<NO_ANSWER/>):", a.text)
    else:
        print(a.text)
    print("\nSources cited:")
    for s in a.sources:
        print(f"  [{s.n}] {s.doc_id} p.{s.page_start} (clr={s.clearance})")
    if a.hallucinated:
        print(f"\n⚠ hallucinated citations stripped: {a.hallucinated}")
    if a.uncited_sentences:
        print(f"⚠ uncited factual sentences: {len(a.uncited_sentences)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ask"])
    ap.add_argument("query")
    ap.add_argument("clearance", nargs="?", type=int, default=None)
    args = ap.parse_args()
    _cli(args.query, args.clearance)
    return 0


if __name__ == "__main__":
    sys.exit(main())
