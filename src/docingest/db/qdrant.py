from qdrant_client import AsyncQdrantClient
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


async def ensure_collection(client: AsyncQdrantClient, tenant_id: str) -> None:
    name = _collection_name(tenant_id)
    collections = await client.get_collections()
    if name not in [c.name for c in collections.collections]:
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


async def upsert_chunks(
    client: AsyncQdrantClient,
    tenant_id: str,
    points: list[PointStruct],
) -> None:
    await client.upsert(collection_name=_collection_name(tenant_id), points=points)


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
