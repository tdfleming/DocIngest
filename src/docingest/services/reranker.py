from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from docingest.api.routes.search import SearchResult

log = structlog.get_logger()


async def rerank(
    query: str,
    results: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    """Rerank search results using a cross-encoder model.

    Currently uses a simple keyword-overlap heuristic as a placeholder.
    Replace with a local cross-encoder (e.g., cross-encoder/ms-marco-MiniLM-L-6-v2).
    """
    # TODO: Integrate a real cross-encoder reranker.
    # Placeholder: boost results where query terms appear in chunk text.
    query_terms = set(query.lower().split())

    scored = []
    for result in results:
        chunk_lower = result.chunk_text.lower()
        overlap = sum(1 for term in query_terms if term in chunk_lower)
        # Blend vector score with keyword overlap
        combined = result.score * 0.7 + (overlap / max(len(query_terms), 1)) * 0.3
        scored.append((combined, result))

    scored.sort(key=lambda x: x[0], reverse=True)

    reranked = []
    for score, result in scored[:top_k]:
        result.score = round(score, 4)
        reranked.append(result)

    log.info("reranked results", input_count=len(results), output_count=len(reranked))
    return reranked
