#!/usr/bin/env bash
# One-command setup for PortDoc AI. Brings the system up from a fresh clone.
#
# Assumes: Python 3.12, Docker, and (optionally) a GPU are available.
# Installs uv + Ollama if missing, starts Qdrant, pulls the model, builds the index.
# After this, run:  make api   (one terminal)   and   make ui   (another).
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${PORTDOC_LLM_MODEL:-mistral:7b}"

echo "==> 1/5 Python env (uv)"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev

echo "==> 2/5 Qdrant (vector DB)"
if ! curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
  docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
fi

echo "==> 3/5 Ollama (local LLM — uses GPU automatically if present)"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
ollama pull "$MODEL"

echo "==> 4/5 Building the vector index from committed chunks"
make index

echo "==> 5/5 Done."
echo
echo "Now run, in two terminals:"
echo "    make api      # FastAPI  -> http://localhost:8000"
echo "    make ui       # Next.js  -> http://localhost:3000"
