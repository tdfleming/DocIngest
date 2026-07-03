"""Tests for docingest.services.reranker.

The cross-encoder model itself is not loaded — ``_compute_scores`` is monkeypatched
so tests are fast and offline-safe. We verify reordering, top_k truncation, score
normalization, and graceful degradation when the model is unavailable.
"""

from __future__ import annotations

import pytest

from docingest.api.routes.search import SearchResult
from docingest.services import reranker


def _make_result(chunk_text: str, score: float, chunk_index: int = 0) -> SearchResult:
    return SearchResult(
        chunk_text=chunk_text,
        score=score,
        doc_id="doc1",
        source_ref="ref",
        content_type="text/markdown",
        heading_chain=[],
        chunk_index=chunk_index,
    )


async def test_rerank_reorders_by_cross_encoder_score(monkeypatch):
    # Retrieval (vector) order: A, B, C. Cross-encoder disagrees: C is most relevant.
    results = [
        _make_result("A", 0.9, 0),
        _make_result("B", 0.8, 1),
        _make_result("C", 0.7, 2),
    ]
    scores_by_doc = {"A": -2.0, "B": 0.0, "C": 5.0}
    monkeypatch.setattr(
        reranker, "_compute_scores", lambda q, docs: [scores_by_doc[d] for d in docs]
    )

    out = await reranker.rerank("query", results, top_k=3)

    assert [r.chunk_text for r in out] == ["C", "B", "A"]


async def test_rerank_respects_top_k(monkeypatch):
    results = [_make_result(str(i), 0.5, i) for i in range(5)]
    monkeypatch.setattr(
        reranker,
        "_compute_scores",
        lambda q, docs: [float(len(docs) - i) for i in range(len(docs))],
    )

    out = await reranker.rerank("query", results, top_k=2)

    assert len(out) == 2


async def test_rerank_normalizes_scores_to_unit_interval(monkeypatch):
    results = [_make_result("A", 0.9, 0), _make_result("B", 0.8, 1)]
    monkeypatch.setattr(reranker, "_compute_scores", lambda q, docs: [8.0, -8.0])

    out = await reranker.rerank("query", results, top_k=2)

    for r in out:
        assert 0.0 <= r.score <= 1.0
    # sigmoid(8) ≈ 0.9997 for the top result; sigmoid(-8) ≈ 0.0003 for the tail.
    assert out[0].score > 0.99
    assert out[1].score < 0.01


async def test_rerank_empty_results_returns_empty(monkeypatch):
    def _boom(q, docs):
        raise AssertionError("should not be called for empty input")

    monkeypatch.setattr(reranker, "_compute_scores", _boom)

    assert await reranker.rerank("query", [], top_k=5) == []


async def test_rerank_falls_back_to_vector_order_on_model_failure(monkeypatch):
    results = [
        _make_result("A", 0.9, 0),
        _make_result("B", 0.8, 1),
        _make_result("C", 0.7, 2),
    ]

    def _fail(q, docs):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(reranker, "_compute_scores", _fail)

    out = await reranker.rerank("query", results, top_k=2)

    # Original vector order preserved, truncated to top_k, scores untouched.
    assert [r.chunk_text for r in out] == ["A", "B"]
    assert out[0].score == pytest.approx(0.9)


def test_sigmoid_monotonic_and_bounded():
    assert reranker._sigmoid(0.0) == pytest.approx(0.5)
    assert reranker._sigmoid(-10.0) < reranker._sigmoid(0.0) < reranker._sigmoid(10.0)
    # Bounded within [0, 1] even at extreme logits (large magnitudes saturate to 0.0/1.0).
    assert 0.0 <= reranker._sigmoid(-100.0) < reranker._sigmoid(100.0) <= 1.0
