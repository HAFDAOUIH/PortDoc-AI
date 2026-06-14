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
from contextlib import asynccontextmanager

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # warm the ONNX encoders + cross-encoder reranker so the first real request isn't a cold start
    from portdoc.index.embed import embed_query_dense, embed_sparse_query
    from portdoc.retrieval.rerank import rerank_scores

    embed_query_dense("warmup")
    embed_sparse_query("warmup")
    rerank_scores("warmup", ["warmup"])  # rerank is ON in the live path — warm it too
    yield


app = FastAPI(title="PortDoc AI — Sovereign RAG", lifespan=lifespan)
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


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve_ep(req: RetrieveRequest) -> RetrieveResponse:
    t0 = time.perf_counter()
    # rerank ON: serve the best-ranked sources (modern-RAG standard; +14pp context precision, measured).
    chunks = retrieve(req.query, user_clearance=req.user_clearance, rerank=True)
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
        # rerank ON: cross-encoder reranking is the modern-RAG standard and lifts context
        # precision +14pp (measured); the ~150ms cost is negligible vs ~14s generation.
        chunks = retrieve(query, user_clearance=clearance, rerank=True)
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

        yield json.dumps({"type": "step", "stage": "generating", "label": f"Generating locally ({get_settings().llm_model})…"}) + "\n"
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


@app.get("/documents")
def documents_ep() -> list[dict]:
    """Aggregate the chunk corpus into a per-document view for the Knowledge-base UI.

    Reads `corpus_dir / chunks.jsonl` (one chunk dict per line), groups by doc_id,
    and reports the document identity + a passage count. `from_ocr` is true if ANY
    chunk of the document came from OCR (i.e. the source was scanned). Returns []
    if the corpus file is absent.
    """
    path = get_settings().corpus_dir / "chunks.jsonl"
    if not path.exists():
        return []

    docs: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc_id = c.get("doc_id")
            if not doc_id:
                continue
            d = docs.get(doc_id)
            if d is None:
                d = docs[doc_id] = {
                    "doc_id": doc_id,
                    "authority": c.get("authority", ""),
                    "doc_type": c.get("doc_type", ""),
                    "year": c.get("year", 0),
                    "lang": c.get("lang", ""),
                    "clearance": c.get("clearance", 0),
                    "from_ocr": False,
                    "n_chunks": 0,
                }
            d["n_chunks"] += 1
            if c.get("from_ocr"):
                d["from_ocr"] = True

    return sorted(docs.values(), key=lambda d: (d["clearance"], d["authority"]))


@app.get("/eval")
def eval_ep() -> dict:
    s = get_settings()

    def _read(name: str):
        p = s.results_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    return {
        "sweep": _read("sweep.json"),
        "leakage": _read("leakage.json"),
        "generation": _read("generation.json"),
    }
