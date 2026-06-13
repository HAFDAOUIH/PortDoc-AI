"""Deterministic retrieval metrics — pure functions, unit-tested.

These are the numbers reviewers trust because they're not LLM-judged: given a ranked
list of retrieved chunk_ids and the set of gold (correct) chunk_ids, they compute
exactly. No model, no randomness.

  recall@k : did we retrieve the gold chunk(s) within the top k?  (coverage)
  MRR      : 1 / rank of the first relevant chunk.                (how high?)
  nDCG@k   : rank-weighted relevance, normalized 0..1.            (ordering quality)

All take `retrieved` as a rank-ordered list (best first) and `gold` as a set/iterable.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def recall_at_k(retrieved: Sequence[str], gold: Iterable[str], k: int) -> float:
    gold = set(gold)
    if not gold:
        return 0.0
    hits = sum(1 for cid in retrieved[:k] if cid in gold)
    return hits / len(gold)


def hit_rate_at_k(retrieved: Sequence[str], gold: Iterable[str], k: int) -> float:
    """1.0 if ANY gold chunk is in the top-k, else 0.0 (a.k.a. success@k).

    Robust when several chunks legitimately answer a question — we only need to
    surface one good one. The primary 'did retrieval work?' signal for RAG.
    """
    gold = set(gold)
    return 1.0 if any(cid in gold for cid in retrieved[:k]) else 0.0


def reciprocal_rank(retrieved: Sequence[str], gold: Iterable[str]) -> float:
    gold = set(gold)
    for rank, cid in enumerate(retrieved, start=1):
        if cid in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gold: Iterable[str], k: int) -> float:
    """Binary-relevance nDCG@k. DCG with log2(rank+1) discount, normalized by ideal."""
    gold = set(gold)
    if not gold:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, cid in enumerate(retrieved[:k], start=1)
        if cid in gold
    )
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def aggregate(rows: list[dict], ks: tuple[int, ...] = (5, 20)) -> dict[str, float]:
    """Mean metrics across a list of {retrieved, gold} query results."""
    if not rows:
        return {}
    out: dict[str, float] = {}
    for k in ks:
        out[f"hit@{k}"] = sum(hit_rate_at_k(r["retrieved"], r["gold"], k) for r in rows) / len(rows)
        out[f"recall@{k}"] = sum(recall_at_k(r["retrieved"], r["gold"], k) for r in rows) / len(rows)
    out["mrr"] = sum(reciprocal_rank(r["retrieved"], r["gold"]) for r in rows) / len(rows)
    out["ndcg@10"] = sum(ndcg_at_k(r["retrieved"], r["gold"], 10) for r in rows) / len(rows)
    return out
