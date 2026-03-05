import asyncio

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from docingest.config import settings

logger = structlog.get_logger()

_client: AsyncQdrantClient | None = None


def _collection_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


async def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


async def close_qdrant() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None
    _known_collections.clear()


_known_collections: set[str] = set()
_collection_lock = asyncio.Lock()


async def ensure_collection(client: AsyncQdrantClient, tenant_id: str) -> None:
    name = _collection_name(tenant_id)
    if name in _known_collections:
        return
    async with _collection_lock:
        # Re-check after acquiring lock
        if name in _known_collections:
            return
        collections = await client.get_collections()
        existing = {c.name for c in collections.collections}
        _known_collections.update(existing)
        if name not in existing:
            try:
                await client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimensions,
                        distance=Distance.COSINE,
                        on_disk=True,
                    ),
                    on_disk_payload=True,
                    optimizers_config={"indexing_threshold": 20000},
                )
            except UnexpectedResponse as exc:
                if exc.status_code == 409 or (
                    exc.content and b"already exists" in exc.content
                ):
                    logger.info(
                        "collection_already_exists",
                        collection=name,
                        msg="created by another replica; treating as success",
                    )
                else:
                    raise
            _known_collections.add(name)


async def upsert_chunks(
    client: AsyncQdrantClient,
    tenant_id: str,
    points: list[PointStruct],
    batch_size: int = 100,
) -> None:
    name = _collection_name(tenant_id)
    if len(points) <= batch_size:
        await client.upsert(collection_name=name, points=points)
    else:
        for i in range(0, len(points), batch_size):
            await client.upsert(collection_name=name, points=points[i : i + batch_size])


async def delete_doc_chunks(
    client: AsyncQdrantClient,
    tenant_id: str,
    doc_id: str,
) -> None:
    await client.delete(
        collection_name=_collection_name(tenant_id),
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )


async def search_chunks(
    client: AsyncQdrantClient,
    tenant_id: str,
    query_vector: list[float],
    limit: int = 10,
    filters: dict | None = None,
) -> list:
    qdrant_filter = None
    if filters:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        qdrant_filter = Filter(must=conditions)

    response = await client.query_points(
        collection_name=_collection_name(tenant_id),
        query=query_vector,
        limit=limit,
        query_filter=qdrant_filter,
        with_payload=True,
    )
    return response.points


async def delete_collection(client: AsyncQdrantClient, tenant_id: str) -> None:
    name = _collection_name(tenant_id)
    collections = await client.get_collections()
    if name in [c.name for c in collections.collections]:
        await client.delete_collection(name)
    _known_collections.discard(name)
