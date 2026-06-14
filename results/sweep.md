# Retrieval Sweep (10 grounded questions, FR corpus)

Retrieval-only (no LLM). Metrics vs hand-labelled gold chunk_ids. Corpus fingerprint `f6a1285066a3bceb`.

| Mode | Reranker | hit@5 | recall@5 | MRR | nDCG@10 | hit@20 |
|---|---|---|---|---|---|---|
| dense | off | 0.70 | 0.43 | 0.524 | 0.450 | 0.80 |
| dense | on | 0.70 | 0.38 | 0.491 | 0.393 | 0.80 |
| sparse | off | 0.50 | 0.24 | 0.329 | 0.304 | 0.70 |
| sparse | on | 0.60 | 0.33 | 0.561 | 0.429 | 0.70 |
| hybrid **(winner)** | off | 0.70 | 0.39 | 0.567 | 0.424 | 0.80 |
| hybrid | on | 0.70 | 0.38 | 0.508 | 0.426 | 0.80 |

**Winner: hybrid (rerank off).** hybrid ≥ dense > **sparse** — sparse alone has the weakest ranking (it can't match paraphrases). Reranking helps the weak sparse ordering most (MRR +0.232) but does **not** beat the already-strong dense/hybrid+RRF here (hybrid MRR -0.058), so rerank is kept as a measured, toggleable option rather than an unconditional cost. With n=10, ±0.1 on hit-rate is noise; the robust signal is sparse << dense ≈ hybrid.
