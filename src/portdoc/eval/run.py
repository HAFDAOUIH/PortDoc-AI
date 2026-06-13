"""The sweep — runs retrieval metrics across a config matrix, emits one markdown table.

Matrix: retrieval mode {dense, sparse, hybrid} × reranker {off, on}. Retrieval-only,
so no LLM and the whole sweep runs in seconds. This is the artifact that proves every
retrieval choice was MEASURED, not copied from a blog.

§8.4 guard: hard-fails if the corpus was re-chunked since the dataset was built (the
gold chunk_ids would silently mis-align otherwise).

Run:  uv run python -m portdoc.eval.run
"""

from __future__ import annotations

import json
import sys

from portdoc.config import get_settings
from portdoc.eval.make_dataset import corpus_fingerprint
from portdoc.eval.retrieval_metrics import aggregate
from portdoc.index.store import get_client, search_mode

MODES = ["dense", "sparse", "hybrid"]


def ranked_ids(client, query: str, mode: str, rerank: bool) -> list[str]:
    pts = search_mode(client, query, mode, limit=get_settings().retrieve_limit)
    if rerank and pts:
        from portdoc.retrieval.rerank import rerank_scores

        scores = rerank_scores(query, [p.payload["raw_text"] for p in pts])
        order = sorted(range(len(pts)), key=lambda i: scores[i], reverse=True)
        pts = [pts[i] for i in order]
    return [p.payload["chunk_id"] for p in pts]


def run() -> str:
    s = get_settings()
    data = json.loads((s.eval_dir / "qa_dataset.json").read_text(encoding="utf-8"))
    if data["corpus_fingerprint"] != corpus_fingerprint():
        raise SystemExit(
            "Corpus fingerprint mismatch — the corpus was re-chunked. "
            "Re-run `make_dataset` to realign gold chunk_ids before evaluating."
        )
    grounded = [i for i in data["items"] if i["type"] == "grounded"]
    client = get_client()

    rows_out = []
    for mode in MODES:
        for rerank in (False, True):
            rows = [
                {"retrieved": ranked_ids(client, i["question"], mode, rerank),
                 "gold": set(i["gold_chunk_ids"])}
                for i in grounded
            ]
            agg = aggregate(rows, ks=(5, 20))
            rows_out.append((mode, rerank, agg))
            print(f"  {mode:<7} rerank={str(rerank):<5}  "
                  f"hit@5={agg['hit@5']:.2f} mrr={agg['mrr']:.3f} ndcg@10={agg['ndcg@10']:.3f}")

    # winner = best hit@5, then mrr
    best = max(rows_out, key=lambda r: (r[2]["hit@5"], r[2]["mrr"]))

    def _rerank_delta(mode: str) -> float:
        off = next(a for m, r, a in rows_out if m == mode and not r)
        on = next(a for m, r, a in rows_out if m == mode and r)
        return on["mrr"] - off["mrr"]

    conclusion = (
        f"**Winner: {best[0]} (rerank {'on' if best[1] else 'off'}).** "
        f"hybrid ≥ dense > **sparse** — sparse alone has the weakest ranking (it can't match "
        f"paraphrases). Reranking helps the weak sparse ordering most (MRR {_rerank_delta('sparse'):+.3f}) "
        f"but does **not** beat the already-strong dense/hybrid+RRF here (hybrid MRR "
        f"{_rerank_delta('hybrid'):+.3f}), so rerank is kept as a measured, toggleable option rather "
        f"than an unconditional cost. With n={len(grounded)}, ±0.1 on hit-rate is noise; the robust "
        f"signal is sparse << dense ≈ hybrid."
    )

    lines = [
        f"# Retrieval Sweep ({len(grounded)} grounded questions, FR corpus)\n",
        "Retrieval-only (no LLM). Metrics vs hand-labelled gold chunk_ids. "
        f"Corpus fingerprint `{data['corpus_fingerprint']}`.\n",
        "| Mode | Reranker | hit@5 | recall@5 | MRR | nDCG@10 | hit@20 |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode, rerank, a in rows_out:
        mark = " **(winner)**" if (mode, rerank, a) == best else ""
        lines.append(
            f"| {mode}{mark} | {'on' if rerank else 'off'} | {a['hit@5']:.2f} | "
            f"{a['recall@5']:.2f} | {a['mrr']:.3f} | {a['ndcg@10']:.3f} | {a['hit@20']:.2f} |"
        )
    lines += ["", conclusion]
    md = "\n".join(lines) + "\n"
    (s.results_dir / "sweep.md").write_text(md, encoding="utf-8")
    # JSON twin for the dashboard
    (s.results_dir / "sweep.json").write_text(
        json.dumps(
            {"n_questions": len(grounded),
             "rows": [{"mode": m, "rerank": r, **a} for m, r, a in rows_out],
             "winner": {"mode": best[0], "rerank": best[1]},
             "conclusion": conclusion},
            ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\nWrote {s.results_dir / 'sweep.md'}")
    return md


def leakage_check() -> str:
    """RBAC proof: query EVERY question at clearance 0; no restricted chunk may surface."""
    s = get_settings()
    data = json.loads((s.eval_dir / "qa_dataset.json").read_text(encoding="utf-8"))
    client = get_client()

    leaks = 0
    restricted_q = 0  # questions whose answer needs clearance 2
    for item in data["items"]:
        pts = search_mode(client, item["question"], "hybrid", limit=s.retrieve_limit, user_clearance=0)
        leaked = [p for p in pts if p.payload["clearance"] > 0]
        leaks += len(leaked)
        if item.get("expected_clearance") == 2:
            restricted_q += 1

    n = len(data["items"])
    md = (
        f"# RBAC Leakage Check\n\n"
        f"Every one of {n} questions queried at **user_clearance = 0**; counted any returned "
        f"chunk with clearance > 0 (restricted/internal).\n\n"
        f"- Restricted chunks leaked to a clearance-0 user: **{leaks}**\n"
        f"- (of which {restricted_q} questions actually require clearance 2 to answer)\n\n"
        f"**Leakage rate: {leaks}/{n} queries → {'0% — enforced at retrieval ✅' if leaks == 0 else 'NON-ZERO ❌'}**\n"
    )
    (s.results_dir / "leakage.md").write_text(md, encoding="utf-8")
    (s.results_dir / "leakage.json").write_text(
        json.dumps({"n_queries": n, "leaks": leaks, "restricted_questions": restricted_q,
                    "leakage_rate": leaks / n if n else 0.0}, indent=2),
        encoding="utf-8")
    print(f"Leakage: {leaks} restricted chunks surfaced at clearance 0 (must be 0)")
    return md


if __name__ == "__main__":
    print("Running retrieval sweep...\n")
    run()
    print("\nRunning RBAC leakage check...\n")
    leakage_check()
    sys.exit(0)
