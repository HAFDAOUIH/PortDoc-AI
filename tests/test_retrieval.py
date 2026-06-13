"""Retrieval pipeline logic: top-k selection, rerank reordering, RBAC plumbing."""

from types import SimpleNamespace

from portdoc.retrieval import pipeline
from portdoc.retrieval.pipeline import ScoredChunk, retrieve


def _cand(score, cid, clr=0):
    return SimpleNamespace(
        score=score,
        payload={"chunk_id": cid, "text": f"ctx {cid}", "raw_text": cid, "clearance": clr,
                 "doc_id": "d", "page_start": 1},
    )


def test_no_rerank_keeps_fusion_order_and_topk(monkeypatch):
    cands = [_cand(0.9, "a"), _cand(0.8, "b"), _cand(0.7, "c")]
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *a, **k: cands)
    out = retrieve("q", top_k=2, rerank=False, client="x")
    assert [c.payload["chunk_id"] for c in out] == ["a", "b"]


def test_rerank_reorders_by_cross_encoder_score(monkeypatch):
    cands = [_cand(0.9, "a"), _cand(0.8, "b"), _cand(0.7, "c")]
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *a, **k: cands)
    # cross-encoder disagrees with fusion: c is most relevant, then a
    import portdoc.retrieval.rerank as rr
    monkeypatch.setattr(rr, "rerank_scores", lambda q, docs: [0.2, 0.1, 0.95])
    out = retrieve("q", top_k=2, rerank=True, client="x")
    assert [c.payload["chunk_id"] for c in out] == ["c", "a"]


def test_empty_candidates_returns_empty(monkeypatch):
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *a, **k: [])
    assert retrieve("q", client="x") == []


def test_clearance_is_passed_through_to_hybrid_search(monkeypatch):
    captured = {}

    def fake(client, query, limit, user_clearance, **filters):
        captured["clr"] = user_clearance
        return []

    monkeypatch.setattr(pipeline, "hybrid_search", fake)
    retrieve("q", user_clearance=1, client="x")
    assert captured["clr"] == 1


def test_scoredchunk_cite_text_is_raw():
    c = ScoredChunk(0.5, {"raw_text": "clean line"})
    assert c.cite_text == "clean line"
