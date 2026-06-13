"""Pure logic for indexing/retrieval: payload filters + sparse-vector conversion."""

from qdrant_client.models import Filter

from portdoc.index.store import build_filter


def _keys(flt: Filter) -> list[str]:
    return [c.key for c in flt.must]


def test_no_filter_when_nothing_requested():
    assert build_filter() is None


def test_clearance_filter_uses_lte_range():
    flt = build_filter(user_clearance=1)
    assert "clearance" in _keys(flt)
    cond = next(c for c in flt.must if c.key == "clearance")
    # caller at clearance 1 may see levels 0 and 1, not 2
    assert cond.range.lte == 1
    assert cond.range.gte is None


def test_metadata_filters_compose():
    flt = build_filter(doc_type="procedure", authority="ANP", year=2012)
    assert set(_keys(flt)) == {"doc_type", "authority", "year"}


def test_clearance_and_metadata_combine():
    flt = build_filter(user_clearance=2, doc_type="circular")
    assert set(_keys(flt)) == {"clearance", "doc_type"}


def test_sparse_conversion_shape():
    # _to_sparse maps a FastEmbed SparseEmbedding (.indices/.values arrays) -> SparseVector
    from types import SimpleNamespace

    import numpy as np
    import pytest

    from portdoc.index.embed import _to_sparse

    sv = _to_sparse(SimpleNamespace(indices=np.array([5, 17]), values=np.array([0.8, 0.2])))
    assert sv.indices == [5, 17]
    assert sv.values == pytest.approx([0.8, 0.2])
