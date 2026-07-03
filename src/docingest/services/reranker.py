from __future__ import annotations

import asyncio
import math
import threading
from typing import TYPE_CHECKING

import structlog

from docingest.config import settings

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    from docingest.api.routes.search import SearchResult

log = structlog.get_logger()

_model: TextCrossEncoder | None = None
_model_lock = threading.Lock()


def _get_model() -> TextCrossEncoder:
    """Lazy-init the FastEmbed cross-encoder (downloads ~80MB on first use).

    Thread-safe: uses double-checked locking so that concurrent
    ``run_in_executor`` calls don't race during initialization. Mirrors the
    lazy-singleton pattern in ``services/embedding.py``.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # Imported lazily so the ~80MB model class isn't touched at import time.
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                log.info("loading cross-encoder model", model=settings.reranker_model)
                _model = TextCrossEncoder(model_name=settings.reranker_model)
                log.info("cross-encoder model loaded", model=settings.reranker_model)
    return _model


def _compute_scores(query: str, documents: list[str]) -> list[float]:
    """Score each (query, document) pair with the cross-encoder. Blocking/CPU-bound.

    Serialized via ``_model_lock`` so concurrent ``run_in_executor`` calls don't
    hit the ONNX model simultaneously (same convention as ``embedding.py``).
    """
    model = _get_model()
    with _model_lock:
        return list(model.rerank(query, documents))


def _sigmoid(x: float) -> float:
    """Map an unbounded cross-encoder logit to a 0..1 relevance probability."""
    return 1.0 / (1.0 + math.exp(-x))


async def rerank(
    query: str,
    results: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    """Rerank candidate search results with a local cross-encoder.

    The cross-encoder jointly scores the query against each chunk's text, which
    is far more accurate than the bi-encoder (vector) score used for retrieval.
    Results are reordered by relevance and each ``score`` is replaced with the
    sigmoid-normalized cross-encoder score (0..1).

    Blocking ONNX inference is offloaded to the default executor. If the model is
    unavailable (e.g. offline / download failure), reranking degrades gracefully
    to the original vector ordering rather than failing the search request.
    """
    if not results:
        return results

    documents = [r.chunk_text for r in results]
    loop = asyncio.get_running_loop()
    try:
        scores = await loop.run_in_executor(None, _compute_scores, query, documents)
    except Exception as exc:  # noqa: BLE001 - reranking is best-effort; never fail search
        log.warning(
            "reranker unavailable, falling back to vector order",
            error=str(exc),
            model=settings.reranker_model,
        )
        return results[:top_k]

    scored = list(zip(scores, results, strict=True))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    reranked: list[SearchResult] = []
    for raw_score, result in scored[:top_k]:
        result.score = round(_sigmoid(raw_score), 4)
        reranked.append(result)

    log.info(
        "reranked results",
        input_count=len(results),
        output_count=len(reranked),
        model=settings.reranker_model,
    )
    return reranked
