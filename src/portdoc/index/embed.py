"""Dense + sparse encoders — CPU profile via FastEmbed (ONNX).

Why ONNX/FastEmbed and not the SOTA torch stack: Qwen3-Embedding + bge-m3 are both
~600M-param fp32 transformers that run ~9 s/chunk on this CPU (≈5 h to index). ONNX
inference is ~10× faster here, so we right-size to the hardware:

  DENSE  : intfloat/multilingual-e5-large (1024-d, multilingual). It is ASYMMETRIC —
           queries are prefixed "query: " and passages "passage: " (e5's trained
           convention). Same idea as instruction-aware embedding, kept explicit here.
  SPARSE : BM25 (French stemming) — exact-word/code matching. Documents use BM25
           term weighting; queries use idf-only weighting (FastEmbed's query_embed).

The SOTA stack (Qwen3-Embedding + bge-m3 learned-sparse) is the GPU/data-center
profile — same hybrid retrieval, swapped models where they're fast.

Models load lazily and once.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client.models import SparseVector

from portdoc.config import get_settings


@lru_cache(maxsize=1)
def _dense():
    from fastembed import TextEmbedding

    return TextEmbedding(get_settings().onnx_dense_model)


@lru_cache(maxsize=1)
def _sparse():
    from fastembed import SparseTextEmbedding

    s = get_settings()
    return SparseTextEmbedding(s.onnx_sparse_model, language=s.sparse_language)


def embed_passages_dense(texts: list[str]) -> list[list[float]]:
    """e5 passages get the 'passage: ' prefix (the document half of the asymmetry)."""
    prefixed = [f"passage: {t}" for t in texts]
    return [v.tolist() for v in _dense().embed(prefixed)]


def embed_query_dense(text: str) -> list[float]:
    """e5 queries get the 'query: ' prefix (the query half of the asymmetry)."""
    return next(iter(_dense().embed([f"query: {text}"]))).tolist()


def _to_sparse(emb) -> SparseVector:
    """FastEmbed SparseEmbedding (.indices/.values numpy arrays) -> Qdrant SparseVector."""
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def embed_sparse_passages(texts: list[str]) -> list[SparseVector]:
    """BM25 document weighting (term frequency saturation + idf)."""
    return [_to_sparse(e) for e in _sparse().embed(texts)]


def embed_sparse_query(text: str) -> SparseVector:
    """BM25 query weighting (idf-only — no tf saturation on the query side)."""
    return _to_sparse(next(iter(_sparse().query_embed([text]))))
