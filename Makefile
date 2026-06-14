.PHONY: install fetch test test-slow chunk index ingest search dataset sweep eval-gen api ui

install:  ## sync the Python env from the lockfile
	uv sync --extra dev

fetch:  ## download + integrity-check the corpus from the manifest (URL docs only)
	uv run python -m portdoc.ingestion.fetch

test:  ## run fast unit tests
	uv run pytest -q

test-slow:  ## run heavy integration tests (load docling / real corpus)
	uv run pytest -q -m slow

chunk:  ## parse + chunk the corpus -> data/corpus/chunks.jsonl (needs raw PDFs + OCR deps)
	uv run python -m portdoc.ingestion.chunk

index:  ## embed all chunks (dense+sparse) into Qdrant (works from committed chunks.jsonl)
	uv run python -m portdoc.index.store index

ingest: chunk index  ## full re-ingestion: parse + chunk + index (needs raw PDFs)

search:  ## ad-hoc hybrid search: make search Q="your question"
	uv run python -m portdoc.index.store search "$(Q)"

dataset:  ## build the labelled eval dataset (gold chunk ids + fingerprint)
	uv run python -m portdoc.eval.make_dataset

sweep:  ## run the retrieval sweep + RBAC leakage check -> results/
	uv run python -m portdoc.eval.run

eval-gen:  ## generation eval: refusal accuracy + faithfulness (LLM-judge) -> results/generation.*
	uv run python -m portdoc.eval.generation_eval

api:  ## run the FastAPI backend (port 8000)
	uv run uvicorn portdoc.api.main:app --port 8000

ui:  ## run the Next.js dashboard (port 3000; needs the API running)
	cd frontend && npm install && npm run dev
