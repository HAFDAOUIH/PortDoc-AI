"""FastAPI backend — the product. The Next.js dashboard is a thin client over this.

Endpoints:
  GET  /health    — sovereignty/status badge data
  POST /retrieve  — FAST (no LLM): access-controlled sources. Powers the live clearance toggle.
  POST /ask       — full generation (slow on CPU): grounded, cited answer or refusal.
  GET  /eval      — committed sweep + leakage results for the dashboard.

Run:  uv run uvicorn portdoc.api.main:app --port 8000
"""

from __future__ import annotations

import json
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from portdoc.api.personas import PERSONAS, clearance_for
from portdoc.generation import llm, prompts
from portdoc.generation.citations import parse_answer

from portdoc.api.schemas import (
    AskRequest,
    AskResponse,
    Health,
    RetrieveRequest,
    RetrieveResponse,
    SourceOut,
)
from portdoc.config import get_settings
from portdoc.generation.answer import generate
from portdoc.index.store import get_client
from portdoc.retrieval.pipeline import ScoredChunk, retrieve

app = FastAPI(title="PortDoc AI — Sovereign RAG")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _source(n: int, c: ScoredChunk) -> SourceOut:
    pl = c.payload
    return SourceOut(
        n=n, chunk_id=pl["chunk_id"], doc_id=pl["doc_id"], authority=pl["authority"],
        doc_type=pl["doc_type"], year=pl["year"], page_start=pl["page_start"],
        clearance=pl["clearance"], is_table=pl["is_table"], from_ocr=pl["from_ocr"],
        score=round(c.score, 4), snippet=pl["raw_text"][:400],
    )


@app.get("/health", response_model=Health)
def health() -> Health:
    s = get_settings()
    try:
        points = get_client().count(s.collection).count
    except Exception:  # noqa: BLE001
        points = 0
    return Health(
        llm_backend=s.llm_backend, llm_model=s.llm_model, dense_model=s.onnx_dense_model,
        sparse_model=s.onnx_sparse_model, reranker_model=s.reranker_model_onnx,
        reranker_enabled=s.reranker_enabled, qdrant_points=points,
    )


@app.on_event("startup")
def _warmup() -> None:
    # warm the ONNX encoders so the first real request isn't a multi-second cold start
    from portdoc.index.embed import embed_query_dense, embed_sparse_query

    embed_query_dense("warmup")
    embed_sparse_query("warmup")


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve_ep(req: RetrieveRequest) -> RetrieveResponse:
    t0 = time.perf_counter()
    # rerank OFF here: the live clearance toggle is about ACCESS, not final ranking — keep it snappy.
    chunks = retrieve(req.query, user_clearance=req.user_clearance, rerank=False)
    # how many top results would a fully-cleared user see that this user cannot? (RBAC visual)
    full = retrieve(req.query, user_clearance=2, rerank=False)
    hidden = sum(1 for c in full if c.payload["clearance"] > req.user_clearance)
    return RetrieveResponse(
        sources=[_source(i, c) for i, c in enumerate(chunks, 1)],
        hidden_by_clearance=hidden,
        took_ms=int((time.perf_counter() - t0) * 1000),
    )


@app.post("/ask", response_model=AskResponse)
def ask_ep(req: AskRequest) -> AskResponse:
    t0 = time.perf_counter()
    chunks = retrieve(req.query, user_clearance=req.user_clearance)
    ans = generate(req.query, chunks)
    cited = [_source(s.n, chunks[s.n - 1]) for s in ans.sources]
    return AskResponse(
        answer=ans.text, refused=ans.refused, sources=cited,
        hallucinated_citations=ans.hallucinated, uncited_sentences=len(ans.uncited_sentences),
        took_ms=int((time.perf_counter() - t0) * 1000),
    )


@app.get("/personas")
def personas_ep() -> list[dict]:
    return PERSONAS


@app.post("/chat/stream")
def chat_stream(req: dict):
    """NDJSON stream: step → sources → token* → done. Powers the ChatGPT-style UI."""
    query = req.get("query", "")
    clearance = clearance_for(req.get("persona_id")) if req.get("persona_id") else req.get("user_clearance", 0)

    def gen():
        t0 = time.perf_counter()
        yield json.dumps({"type": "step", "stage": "retrieving", "label": "Searching the corpus…"}) + "\n"
        # rerank=False: the eval showed it doesn't beat hybrid+RRF on this corpus, and it
        # saves a cross-encoder pass — faster first token, same retrieval quality.
        chunks = retrieve(query, user_clearance=clearance, rerank=False)
        full = retrieve(query, user_clearance=2, rerank=False)
        hidden = sum(1 for c in full if c.payload["clearance"] > clearance)
        sources = [_source(i, c).model_dump() for i, c in enumerate(chunks, 1)]
        yield json.dumps({"type": "sources", "sources": sources, "hidden_by_clearance": hidden,
                          "retrieve_ms": int((time.perf_counter() - t0) * 1000)}) + "\n"

        if not chunks:
            yield json.dumps({"type": "token", "text": "Information non disponible dans le corpus accessible à votre habilitation."}) + "\n"
            yield json.dumps({"type": "done", "refused": True, "citations": [],
                              "hallucinated": [], "uncited": 0, "took_ms": int((time.perf_counter() - t0) * 1000)}) + "\n"
            return

        yield json.dumps({"type": "step", "stage": "generating", "label": "Generating locally (Mistral 7B)…"}) + "\n"
        messages = [
            {"role": "system", "content": prompts.SYSTEM},
            {"role": "user", "content": prompts.user_message(query, _sources_block(chunks))},
        ]
        acc = []
        for delta in llm.stream_complete(messages):
            acc.append(delta)
            yield json.dumps({"type": "token", "text": delta}) + "\n"

        parsed = parse_answer("".join(acc), len(chunks))
        yield json.dumps({"type": "done", "refused": parsed.refused, "citations": parsed.citations,
                          "hallucinated": parsed.hallucinated, "uncited": len(parsed.uncited_sentences),
                          "took_ms": int((time.perf_counter() - t0) * 1000)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


def _sources_block(chunks) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        pl = c.payload
        lines.append(f"[{i}] ({pl['authority']} {pl['doc_type']} {pl['year']}, p.{pl['page_start']}) {pl['raw_text']}")
    return "\n\n".join(lines)


@app.get("/eval")
def eval_ep() -> dict:
    s = get_settings()

    def _read(name: str):
        p = s.results_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    return {"sweep": _read("sweep.json"), "leakage": _read("leakage.json")}
