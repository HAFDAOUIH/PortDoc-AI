"""Retrieval metrics verified against hand-computed values (the reviewer-trust signal)."""

import math

import pytest

from portdoc.eval.retrieval_metrics import (
    aggregate,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)

R = ["a", "b", "c", "d", "e"]  # ranked retrieved list


# --- recall@k ---------------------------------------------------------------

def test_recall_full_hit():
    assert recall_at_k(R, {"a", "c"}, k=5) == 1.0  # both gold in top-5


def test_recall_partial_within_k():
    # gold {c, z}: c is in top-3, z never -> 1/2
    assert recall_at_k(R, {"c", "z"}, k=3) == 0.5


def test_recall_misses_below_k():
    # gold {d}: d is at rank 4, k=3 -> 0
    assert recall_at_k(R, {"d"}, k=3) == 0.0


def test_recall_empty_gold_is_zero():
    assert recall_at_k(R, set(), k=5) == 0.0


# --- MRR --------------------------------------------------------------------

def test_rr_first_position():
    assert reciprocal_rank(R, {"a"}) == 1.0


def test_rr_third_position():
    assert reciprocal_rank(R, {"c"}) == pytest.approx(1 / 3)


def test_rr_no_hit():
    assert reciprocal_rank(R, {"z"}) == 0.0


# --- nDCG@k (hand-computed) -------------------------------------------------

def test_ndcg_single_gold_at_rank2():
    # gold {b}: DCG = 1/log2(3); IDCG = 1/log2(2)=1 -> ndcg = 1/log2(3)
    assert ndcg_at_k(R, {"b"}, k=5) == pytest.approx(1 / math.log2(3))


def test_ndcg_perfect_when_gold_on_top():
    # gold {a,b} both at the top two ranks -> ideal ordering -> 1.0
    assert ndcg_at_k(R, {"a", "b"}, k=5) == pytest.approx(1.0)


# --- aggregate --------------------------------------------------------------

def test_aggregate_means():
    rows = [
        {"retrieved": ["a", "b"], "gold": {"a"}},   # recall@5=1, rr=1
        {"retrieved": ["x", "a"], "gold": {"a"}},   # recall@5=1, rr=0.5
    ]
    agg = aggregate(rows, ks=(5,))
    assert agg["recall@5"] == 1.0
    assert agg["mrr"] == pytest.approx(0.75)
