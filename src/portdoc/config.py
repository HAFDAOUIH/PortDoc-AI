"""Single source of truth for configuration.

Everything that another module might want to tweak lives here, typed and
defaulted. No `os.environ[...]` scattered across the codebase, no magic
constants buried in functions. Override any field with a `PORTDOC_`-prefixed
env var (or a line in `.env`), e.g. `PORTDOC_LLM_BACKEND=ollama`.

Fields are grouped by the slice that first needs them so the file reads as a
map of the build, not a flat bag of settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (src/portdoc/config.py -> repo/).
_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PORTDOC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- paths (slice 1) -----------------------------------------------------
    data_dir: Path = _ROOT / "data"
    results_dir: Path = _ROOT / "results"

    @property
    def corpus_dir(self) -> Path:
        return self.data_dir / "corpus"

    @property
    def manifest_path(self) -> Path:
        return self.corpus_dir / "manifest.yaml"

    @property
    def raw_dir(self) -> Path:
        """Where fetched source PDFs land (gitignored)."""
        return self.corpus_dir / "raw"

    @property
    def eval_dir(self) -> Path:
        return self.data_dir / "eval"

    # --- ingestion / chunking (slices 2-3) -----------------------------------
    # A page with fewer than this many extractable chars is treated as scanned.
    scanned_char_threshold: int = 50
    ocr_langs: tuple[str, ...] = ("fra", "eng")
    chunk_max_tokens: int = 512
    # Drop degenerate chunks (bare page numbers, stray fragments) below this many
    # chars of clean text — they only add retrieval noise. Tables are always kept.
    min_chunk_chars: int = 30

    # --- embedding / retrieval (slices 4-5) ----------------------------------
    # CPU profile: ONNX models via FastEmbed — fast + fully local. The SOTA GPU stack
    # (Qwen3-Embedding + bge-m3) is documented but too slow in fp32 on CPU (~9s/chunk).
    onnx_dense_model: str = "intfloat/multilingual-e5-large"  # 1024-d, multilingual, query/passage prefixes
    onnx_sparse_model: str = "Qdrant/bm25"
    sparse_language: str = "french"
    # Kept as the chunker tokenizer + the documented GPU-profile dense model.
    dense_model: str = "Qwen/Qwen3-Embedding-0.6B"
    dense_dim: int = 1024            # e5-large and Qwen3-Embedding are both 1024-d
    sparse_model: str = "BAAI/bge-m3"
    # CPU reranker: bge-reranker-base (MIT, multilingual, ONNX). The jina v2 multilingual
    # reranker is stronger but CC-BY-NC (non-commercial) — license trap, rejected.
    reranker_model_onnx: str = "BAAI/bge-reranker-base"
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"  # documented GPU-profile reranker
    reranker_enabled: bool = True
    rerank_top_k: int = 5            # final chunks after rerank (from retrieve_limit candidates)
    embed_batch_size: int = 16
    qdrant_url: str = "http://localhost:6333"
    collection: str = "portdoc"
    # Retrieval fan-out: each branch fetches this many, fused down to `retrieve_limit`.
    prefetch_limit: int = 40
    retrieve_limit: int = 20

    # --- generation / llm (slice 6) ------------------------------------------
    # LiteLLM treats all three as OpenAI-compatible endpoints; only this string
    # plus the api_base/model id change between profiles.
    llm_backend: str = "ollama"  # one of: vllm | ollama | openai — local by default
    llm_model: str = "mistral-small:24b"  # self-hosted default (French-native, on-prem GPU profile)
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    gen_max_tokens: int = 512        # cap answer length — main CPU latency lever
    gen_temperature: float = 0.1

    # --- eval judge (slice 7) ------------------------------------------------
    # A SEPARATE, stronger model grades faithfulness. Offline measurement only —
    # it never serves a user — so a cloud judge over PUBLIC docs doesn't dent the
    # (fully local) product's sovereignty. Cloud path uses llm_api_key.
    judge_backend: str = "openai"   # openai | ollama | vllm
    judge_model: str = "gpt-4o"     # must out-rank the served model (gpt-4o >> mistral-small:24b)

    def ensure_dirs(self) -> None:
        """Create the directories we own. Cheap, idempotent, called by entrypoints."""
        for d in (self.data_dir, self.corpus_dir, self.raw_dir, self.eval_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so every module shares one Settings instance."""
    return Settings()
