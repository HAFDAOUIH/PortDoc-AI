"""Pydantic request/response models for the API (typed contract for the dashboard)."""

from __future__ import annotations

from pydantic import BaseModel


class SourceOut(BaseModel):
    n: int                 # citation index [n]
    chunk_id: str
    doc_id: str
    authority: str
    doc_type: str
    year: int
    page_start: int
    clearance: int
    is_table: bool
    from_ocr: bool
    score: float
    snippet: str           # raw_text (the citable passage)


class RetrieveRequest(BaseModel):
    query: str
    user_clearance: int = 2
    rerank: bool | None = None


class RetrieveResponse(BaseModel):
    sources: list[SourceOut]
    hidden_by_clearance: int   # how many restricted chunks were filtered out (RBAC visual)
    took_ms: int


class AskRequest(BaseModel):
    query: str
    user_clearance: int = 2


class AskResponse(BaseModel):
    answer: str
    refused: bool
    sources: list[SourceOut]            # only the cited ones
    hallucinated_citations: list[int]
    uncited_sentences: int
    took_ms: int


class Health(BaseModel):
    status: str = "ok"
    sovereign: bool = True              # everything runs locally
    llm_backend: str
    llm_model: str
    dense_model: str
    sparse_model: str
    reranker_model: str
    reranker_enabled: bool
    qdrant_points: int
