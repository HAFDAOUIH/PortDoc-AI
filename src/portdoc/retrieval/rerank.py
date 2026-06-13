"""Reranking — the careful second read.

Hybrid search is fast but coarse: it scores query and chunk *independently* (two
vectors, a similarity). A cross-encoder reads the query and chunk *together* and
judges direct relevance — far more accurate, but too slow to run on the whole
corpus. So the pattern is: hybrid retrieves top-20 cheaply, the reranker rescores
those 20 and keeps the best 5.

CPU profile: BAAI/bge-reranker-base (MIT, multilingual, ONNX via FastEmbed).
GPU profile: Qwen/Qwen3-Reranker-0.6B (documented; too slow in fp32 on CPU).

Toggleable via config.reranker_enabled — it's both an eval-sweep axis and a CPU
latency lever.
"""

from __future__ import annotations

from functools import lru_cache

from portdoc.config import get_settings


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(get_settings().reranker_model_onnx)


def rerank_scores(query: str, documents: list[str]) -> list[float]:
    """Cross-encoder relevance score for each (query, document) pair. Higher = better."""
    return [float(s) for s in _reranker().rerank(query, documents)]
