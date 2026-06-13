"""LiteLLM wrapper — one interface, three backends, swapped by a single config value.

  ollama -> self-hosted local model (the sovereignty default + demo)
  vllm   -> the data-center GPU profile (OpenAI-compatible endpoint)
  openai -> a cloud API (fast dev, or the strong eval JUDGE)

All three are OpenAI-compatible, so LiteLLM treats them uniformly; only the model
string and api_base change. Generation uses temperature 0.1; judges/rewrite 0.0.
"""

from __future__ import annotations

import json

from portdoc.config import get_settings


def _model_and_kwargs() -> tuple[str, dict]:
    s = get_settings()
    if s.llm_backend == "ollama":
        return f"ollama_chat/{s.llm_model}", {"api_base": s.llm_api_base or "http://localhost:11434"}
    if s.llm_backend == "vllm":
        return f"openai/{s.llm_model}", {"api_base": s.llm_api_base, "api_key": s.llm_api_key or "EMPTY"}
    # cloud (openai/anthropic/mistral via litellm model id)
    kw = {"api_key": s.llm_api_key} if s.llm_api_key else {}
    if s.llm_api_base:
        kw["api_base"] = s.llm_api_base
    return s.llm_model, kw


def complete(messages: list[dict], temperature: float = 0.1, max_tokens: int = 1024) -> str:
    import litellm

    model, kw = _model_and_kwargs()
    resp = litellm.completion(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kw
    )
    return resp.choices[0].message.content or ""


def stream_complete(messages: list[dict], temperature: float = 0.1, max_tokens: int = 512):
    """Yield answer text deltas token-by-token (the ChatGPT-style streaming path)."""
    import litellm

    model, kw = _model_and_kwargs()
    stream = litellm.completion(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        stream=True, **kw,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def complete_json(messages: list[dict], temperature: float = 0.0, max_tokens: int = 1024) -> dict:
    """JSON-mode call for rewrite / judges. Falls back to best-effort brace extraction."""
    import litellm

    model, kw = _model_and_kwargs()
    resp = litellm.completion(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        response_format={"type": "json_object"}, **kw,
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start : end + 1]) if start != -1 else {}
