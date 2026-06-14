# PortDoc AI — Sovereign RAG over Port Security Documents

A **fully self-hosted** retrieval-augmented assistant over port security & operational
documents, with **role-based access control enforced at retrieval**. Built as the kind of
internal assistant **CIRES Technologies** (Tanger Med's security / data-sovereignty
subsidiary) would deploy for port staff: every employee queries the same knowledge base,
but **sees only what their clearance permits**, every answer is **cited**, and **no data
ever leaves the host**.

```
Ask a question  →  access-controlled hybrid retrieval  →  reranked top-k  →  cited French
answer (or an honest refusal)  —  100% local: embeddings, reranker, and LLM all on-prem.
```

---

## Highlights

- **🔒 Row-level RBAC at the data layer** — each chunk carries a clearance level; a Qdrant
  payload filter excludes restricted chunks *before* fusion/rerank, so they never enter the
  LLM context. Same question, two roles, different answers. **Measured leakage: 0%.**
- **🔎 Hybrid retrieval** — dense (multilingual-e5-large, ONNX) + sparse (BM25-french),
  fused with Reciprocal Rank Fusion, then a cross-encoder reranker (bge-reranker-base).
- **🧾 Machine-checkable grounding** — every factual sentence must cite `[n]`; a parser
  validates citations and *strips invented ones*. An exact `<NO_ANSWER/>` sentinel makes
  refusal detectable and measurable.
- **🖼️ OCR pipeline** — scanned/born-digital routing (verified, not trusted from metadata)
  + a French OCR bake-off (`results/ocr_bakeoff.md`): Tesseract retained 99% of accents vs
  EasyOCR / RapidOCR.
- **📊 Committed evaluation** — unit-tested retrieval metrics, a config sweep, and the RBAC
  leakage check, all in `results/` (rendered live in the UI's *Trust & Evaluation* panel).
- **💬 Streaming enterprise UI** — Next.js console with a persona switcher (the RBAC demo),
  pipeline steps, citation-forward answers, and grounding chips.

---

## Architecture

```
INGEST (offline)
  PDF ─► route (scanned? OCR : born-digital) ─► Docling parse ─► HybridChunker
      ─► contextual headers ─► dense + sparse embed ─► Qdrant (named vectors + payload)

QUERY (online)
  question + persona ─► embed ─► Qdrant hybrid search ──[clearance filter, both branches]──►
      top-20 (access-controlled) ─► RRF fusion ─► cross-encoder rerank ─► top-5
      ─► local LLM: cited answer / <NO_ANSWER/>  ─► citation validation

  Next.js dashboard ──HTTP/NDJSON stream──► FastAPI (/health /retrieve /ask /chat/stream /eval)
```

---

## Quickstart

### Prerequisites
- **Python 3.12** + [`uv`](https://docs.astral.sh/uv/)
- **Docker** (for Qdrant) · **[Ollama](https://ollama.com)** (local LLM)
- **Node.js 18+** (for the UI)
- *Optional, only to re-ingest from source PDFs:* `tesseract-ocr tesseract-ocr-fra poppler-utils imagemagick`

> The processed `data/corpus/chunks.jsonl` is committed, so you can run the full system
> **without the raw PDFs** — just build the index from it (step 4). Re-ingestion from
> source PDFs is optional (see [Re-ingestion](#re-ingestion-optional)).

### Run it

```bash
# 1. Python env
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --extra dev

# 2. Vector DB
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# 3. Local LLM (Ollama uses the GPU automatically if present → ~2-5s/answer)
ollama pull mistral:7b

# 4. Build the index from the committed chunks
make index

# 5. Serve — two terminals
make api          # FastAPI  → http://localhost:8000
make ui           # Next.js  → http://localhost:3000
```

Open **http://localhost:3000**. Try: ask a security question as *Salma (Port Security,
clearance 2)*, then switch to *Nadia (Reception, clearance 0)* and ask the same thing —
watch the restricted sources disappear.

> **On a CPU-only machine** the local LLM is slow (~1–2 min/answer; it's prefill-bound on
> a 7B model). That's the sovereignty trade-off. On a GPU box (e.g. Lightning.ai) Ollama
> uses the GPU and answers in ~2–5 s — `make` steps are identical.

### Make targets
`make install · fetch · index · ingest · sweep · search Q="…" · api · ui · test`

---

## Evaluation

Deterministic retrieval metrics over a hand-labelled question set (`data/eval/qa_dataset.json`,
fingerprint-guarded against re-chunk drift). Full results in [`results/`](results/).

| Mode | Reranker | hit@5 | MRR | nDCG@10 |
|---|---|---|---|---|
| dense | off | 0.70 | 0.524 | 0.450 |
| sparse | off | 0.50 | 0.329 | 0.304 |
| **hybrid (winner)** | off | **0.70** | **0.566** | 0.424 |

**RBAC leakage: 0 / 19 queries (0%)** — no restricted chunk ever surfaced at clearance 0.

Reranking helped the weak sparse ordering most (+0.232 MRR) but did **not** beat the strong
hybrid+RRF baseline on this corpus, so it's kept as a measured, toggleable option. Regenerate
with `make sweep`.

---

## Tech stack & rationale

| Layer | Choice | Why |
|---|---|---|
| Parsing / OCR | Docling + **Tesseract `fra`** | best French accent retention (measured) |
| Chunking | Docling `HybridChunker`, 512-tok cap, contextual headers | structure-aware; embedder-matched tokenizer |
| Vector DB | **Qdrant** | lightest self-hostable DB with native sparse + server-side RRF fusion |
| Dense embed | `multilingual-e5-large` (ONNX/FastEmbed) | multilingual, ~10× faster than fp32 torch on CPU |
| Sparse embed | BM25-french | commercially-licensed multilingual lexical signal |
| Reranker | `bge-reranker-base` (MIT, multilingual) | jina-v2 multilingual rejected (CC-BY-NC) |
| LLM | Mistral 7B via Ollama (swappable via LiteLLM) | self-hosted; one-line swap to vLLM/cloud |
| API / UI | FastAPI + Next.js 14 (Tailwind, Recharts) | streaming console; API is the product |

All retrieval/generation runs locally — no hosted embedding or LLM API.

---

## Project structure

```
src/portdoc/
  ingestion/   fetch · parse (scan routing + OCR) · chunk
  index/       embed (dense+sparse) · store (Qdrant schema, hybrid search, RBAC filter)
  retrieval/   rerank · pipeline (retrieve = hybrid → RBAC → rerank → top-k)
  generation/  llm (LiteLLM) · prompts · citations (validating parser) · answer
  eval/        retrieval_metrics · make_dataset · run (sweep + leakage)
  api/         main (FastAPI) · schemas · personas
frontend/      Next.js streaming dashboard
data/          corpus/manifest.yaml · corpus/chunks.jsonl (committed) · eval/qa_dataset.json
results/       sweep · leakage · ocr_bakeoff
tests/         59 unit tests (metrics, citations, chunking, filters, …)
```

## Configuration

Defaults run fully local — no `.env` needed. Override any setting via `PORTDOC_*` env vars
(see `.env.example`), e.g. to swap the LLM backend:

```bash
PORTDOC_LLM_BACKEND=ollama        # ollama | vllm | openai
PORTDOC_LLM_MODEL=mistral:7b
```

## Re-ingestion (optional)

The repo ships `chunks.jsonl`, so this is only needed to rebuild from source PDFs:

```bash
# place the raw PDFs in data/corpus/raw/ (filenames matching manifest ids), then:
make ingest        # parse + OCR + chunk + index   (needs tesseract/poppler/imagemagick)
```

`scripts/make_scan.sh` regenerates the synthetic scanned circular used for the OCR pipeline.

---

## Limitations & roadmap

- **CPU latency** — 7B generation is slow on CPU; production runs on a GPU profile (vLLM /
  Ollama-on-GPU). Embeddings stay ONNX-CPU (one-time indexing cost).
- **Scoped out:** Arabic/Darija (FR/EN only). Documented, not built.
- **Roadmap:** Qwen3-Embedding + bge-m3 learned-sparse + Qwen3-Reranker on the GPU profile;
  LLM-judge faithfulness scoring; PaddleOCR-VL evaluation; Intel NPU/iGPU acceleration.

---

*Built incrementally with engineering rigor — unit-tested metrics, integrity-checked corpus,
honest evaluation (including negative findings), and reproducibility throughout.*
