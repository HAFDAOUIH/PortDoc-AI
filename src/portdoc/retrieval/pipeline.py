"""The retrieval pipeline: hybrid search -> RBAC filter -> rerank -> top-k.

This is the single entry point generation (Slice 6) and eval (Slice 7) call.

RBAC (§6.5) — the CIRES security feature: the caller passes `user_clearance`, and
the clearance filter is applied INSIDE both prefetch branches (in store.hybrid_search),
so restricted chunks are excluded *before* fusion and rerank — they never enter the
candidate set, let alone the LLM context. This is real row-level access control, not
a prompt instruction.

CLI:
  uv run python -m portdoc.retrieval.pipeline retrieve "ma question" [clearance]
  uv run python -m portdoc.retrieval.pipeline rbac "ma question"   # clearance 0 vs 2 diff
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from portdoc.config import get_settings
from portdoc.index.store import get_client, hybrid_search


@dataclass
class ScoredChunk:
    score: float
    payload: dict

    @property
    def cite_text(self) -> str:
        return self.payload["raw_text"]


def retrieve(
    query: str,
    user_clearance: int | None = None,
    top_k: int | None = None,
    rerank: bool | None = None,
    client=None,
    **filters,
) -> list[ScoredChunk]:
    s = get_settings()
    top_k = top_k or s.rerank_top_k
    use_rerank = s.reranker_enabled if rerank is None else rerank
    client = client or get_client()

    candidates = hybrid_search(
        client, query, limit=s.retrieve_limit, user_clearance=user_clearance, **filters
    )
    if not candidates:
        return []

    if use_rerank:
        from portdoc.retrieval.rerank import rerank_scores

        # rerank on the RAW passage (the header prefix dilutes the cross-encoder — measured)
        scores = rerank_scores(query, [c.payload["raw_text"] for c in candidates])
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        return [ScoredChunk(scores[i], candidates[i].payload) for i in order[:top_k]]

    return [ScoredChunk(float(c.score), c.payload) for c in candidates[:top_k]]


def _print(chunks: list[ScoredChunk]) -> None:
    for i, c in enumerate(chunks, 1):
        pl = c.payload
        print(f"  [{i}] score={c.score:.3f}  {pl['doc_id']} p.{pl['page_start']}  clr={pl['clearance']}")
        print(f"      {pl['raw_text'][:120].strip()}")


def _demo_rbac(query: str) -> None:
    """Same question, two clearances -> different answers. The CIRES demo."""
    client = get_client()
    print(f"\nQuestion: {query}\n" + "=" * 72)
    for clr in (0, 2):
        chunks = retrieve(query, user_clearance=clr, client=client)
        levels = sorted({c.payload["clearance"] for c in chunks})
        restricted = [c for c in chunks if c.payload["clearance"] == 2]
        print(f"\n--- user_clearance = {clr} --- (clearance levels returned: {levels})")
        _print(chunks)
        if clr == 0:
            print(f"  >> restricted (clr=2) chunks leaked to clearance 0: {len(restricted)}  (must be 0)")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("retrieve")
    rp.add_argument("query")
    rp.add_argument("clearance", nargs="?", type=int, default=None)
    dp = sub.add_parser("rbac")
    dp.add_argument("query")
    args = ap.parse_args()

    if args.cmd == "retrieve":
        _print(retrieve(args.query, user_clearance=args.clearance))
    elif args.cmd == "rbac":
        _demo_rbac(args.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
