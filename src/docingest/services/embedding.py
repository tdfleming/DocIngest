import structlog
from fastembed import TextEmbedding

from docingest.config import settings

log = structlog.get_logger()

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    """Lazy-init the FastEmbed model (downloads ~30MB on first use)."""
    global _model
    if _model is None:
        log.info("loading fastembed model", model=settings.fastembed_model)
        _model = TextEmbedding(model_name=settings.fastembed_model)
        log.info("fastembed model loaded", model=settings.fastembed_model)
    return _model


def count_tokens(text: str) -> int:
    """Approximate token count. ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via FastEmbed.

    Handles batching internally based on configured batch size.
    """
    model = _get_model()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), settings.embedding_batch_size):
        batch = texts[i : i + settings.embedding_batch_size]
        embeddings = list(model.embed(batch))
        all_embeddings.extend([e.tolist() for e in embeddings])

    log.info("embedded texts", count=len(texts))
    return all_embeddings


def embed_query(query: str) -> tuple[list[float], int]:
    """Embed a single query string. Returns (vector, token_count).

    Uses FastEmbed's query_embed which prepends the appropriate prefix
    for asymmetric models like bge-small-en-v1.5.
    """
    model = _get_model()
    embeddings = list(model.query_embed(query))
    vector = embeddings[0].tolist()
    return vector, count_tokens(query)
