.PHONY: install fetch test

install:  ## sync the env from the lockfile
	uv sync --extra dev

fetch:  ## download + integrity-check the corpus from the manifest
	uv run python -m portdoc.ingestion.fetch

test:  ## run fast unit tests
	uv run pytest -q

test-slow:  ## run heavy integration tests (load docling / real corpus)
	uv run pytest -q -m slow

chunk:  ## parse + chunk the whole corpus -> data/corpus/chunks.jsonl
	uv run python -m portdoc.ingestion.chunk

index:  ## embed all chunks (dense+sparse) and upsert into Qdrant
	uv run python -m portdoc.index.store index

search:  ## ad-hoc hybrid search: make search Q="your question"
	uv run python -m portdoc.index.store search "$(Q)"

dataset:  ## build the labelled eval dataset (gold chunk ids + fingerprint)
	uv run python -m portdoc.eval.make_dataset

sweep:  ## run the retrieval sweep -> results/sweep.md
	uv run python -m portdoc.eval.run

api:  ## run the FastAPI backend (port 8077)
	uv run uvicorn portdoc.api.main:app --port 8077

ui:  ## run the Next.js dashboard (port 3000; needs the API running)
	cd frontend && npm run dev
