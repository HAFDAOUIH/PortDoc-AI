"""Qdrant: collection schema, indexing, and the hybrid (dense+sparse) query.

The collection holds TWO named vectors per chunk:
  - "dense"   (1024-d, cosine)         -> semantic search
  - "lexical" (sparse, bge-m3 weights) -> exact-word/code search

Hybrid query = run both branches, then fuse with RRF (Reciprocal Rank Fusion).
Payload indexes on doc_type/authority/year/lang/clearance make metadata filtering
(and the RBAC clearance filter, §6.5) cheap and exact.

CLI:
  uv run python -m portdoc.index.store index
  uv run python -m portdoc.index.store search "règles marchandises dangereuses" [clearance]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    Range,
    SparseVectorParams,
    VectorParams,
)

from portdoc.config import get_settings
from portdoc.index.embed import (
    embed_passages_dense,
    embed_query_dense,
    embed_sparse_passages,
    embed_sparse_query,
)

DENSE = "dense"
LEXICAL = "lexical"
_INDEXED_FIELDS = {
    "doc_type": PayloadSchemaType.KEYWORD,
    "authority": PayloadSchemaType.KEYWORD,
    "lang": PayloadSchemaType.KEYWORD,
    "year": PayloadSchemaType.INTEGER,
    "clearance": PayloadSchemaType.INTEGER,
}


def get_client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)


def create_collection(client: QdrantClient) -> None:
    s = get_settings()
    if client.collection_exists(s.collection):
        client.delete_collection(s.collection)
    client.create_collection(
        s.collection,
        vectors_config={DENSE: VectorParams(size=s.dense_dim, distance=Distance.COSINE)},
        sparse_vectors_config={LEXICAL: SparseVectorParams()},
    )
    for field, schema in _INDEXED_FIELDS.items():
        client.create_payload_index(s.collection, field_name=field, field_schema=schema)


def build_filter(
    user_clearance: int | None = None,
    doc_type: str | None = None,
    authority: str | None = None,
    year: int | None = None,
) -> Filter | None:
    """Compose a Qdrant payload filter. clearance uses <= (you see your level and below)."""
    must = []
    if user_clearance is not None:
        must.append(FieldCondition(key="clearance", range=Range(lte=user_clearance)))
    if doc_type is not None:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if authority is not None:
        must.append(FieldCondition(key="authority", match=MatchValue(value=authority)))
    if year is not None:
        must.append(FieldCondition(key="year", match=MatchValue(value=year)))
    return Filter(must=must) if must else None


def _load_chunks() -> list[dict]:
    path = get_settings().corpus_dir / "chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def build_index() -> int:
    s = get_settings()
    client = get_client()
    chunks = _load_chunks()
    print(f"Indexing {len(chunks)} chunks into '{s.collection}' ...")
    create_collection(client)

    n = 0
    for start in range(0, len(chunks), s.embed_batch_size):
        batch = chunks[start : start + s.embed_batch_size]
        texts = [c["text"] for c in batch]                 # embed the contextual text
        dense = embed_passages_dense(texts)
        sparse = embed_sparse_passages(texts)
        points = [
            PointStruct(
                id=start + i,
                vector={DENSE: dense[i], LEXICAL: sparse[i]},
                payload=batch[i],                          # full chunk metadata + raw_text
            )
            for i in range(len(batch))
        ]
        client.upsert(s.collection, points)
        n += len(points)
        print(f"  {n}/{len(chunks)}", end="\r", flush=True)
    print(f"\nIndexed {n} chunks.")
    return n


def hybrid_search(
    client: QdrantClient,
    query: str,
    limit: int | None = None,
    user_clearance: int | None = None,
    **filters,
):
    """Dense + sparse prefetch, fused with RRF. Filters apply to BOTH branches."""
    s = get_settings()
    flt = build_filter(user_clearance=user_clearance, **filters)
    res = client.query_points(
        s.collection,
        prefetch=[
            Prefetch(query=embed_query_dense(query), using=DENSE, limit=s.prefetch_limit, filter=flt),
            Prefetch(query=embed_sparse_query(query), using=LEXICAL, limit=s.prefetch_limit, filter=flt),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit or s.retrieve_limit,
        with_payload=True,
    )
    return res.points


def search_mode(client: QdrantClient, query: str, mode: str, limit: int,
                user_clearance: int | None = None, **filters):
    """Single-mode retrieval for the eval sweep: mode in {dense, sparse, hybrid}."""
    s = get_settings()
    flt = build_filter(user_clearance=user_clearance, **filters)
    if mode == "dense":
        return client.query_points(s.collection, query=embed_query_dense(query), using=DENSE,
                                   limit=limit, query_filter=flt, with_payload=True).points
    if mode == "sparse":
        return client.query_points(s.collection, query=embed_sparse_query(query), using=LEXICAL,
                                   limit=limit, query_filter=flt, with_payload=True).points
    if mode == "hybrid":
        return client.query_points(
            s.collection,
            prefetch=[
                Prefetch(query=embed_query_dense(query), using=DENSE, limit=s.prefetch_limit, filter=flt),
                Prefetch(query=embed_sparse_query(query), using=LEXICAL, limit=s.prefetch_limit, filter=flt),
            ],
            query=FusionQuery(fusion=Fusion.RRF), limit=limit, with_payload=True,
        ).points
    raise ValueError(mode)


def _cli_search(query: str, clearance: int | None) -> None:
    points = hybrid_search(get_client(), query, limit=5, user_clearance=clearance)
    print(f"\nQuery: {query}   (clearance={clearance})\n" + "-" * 70)
    for i, p in enumerate(points, 1):
        pl = p.payload
        head = " > ".join(pl["heading_path"]) or "(no heading)"
        print(f"[{i}] score={p.score:.4f}  {pl['doc_id']} p.{pl['page_start']}  clr={pl['clearance']}")
        print(f"    {pl['authority']} {pl['doc_type']} {pl['year']} | {head}")
        print(f"    {pl['raw_text'][:160].strip()}...\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("clearance", nargs="?", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "index":
        build_index()
    elif args.cmd == "search":
        _cli_search(args.query, args.clearance)
    return 0


if __name__ == "__main__":
    sys.exit(main())
