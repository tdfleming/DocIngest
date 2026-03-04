from arq.connections import ArqRedis, create_pool, RedisSettings

from docingest.config import settings

_pool: ArqRedis | None = None


def get_redis_settings() -> RedisSettings:
    # Parse redis://host:port from URL
    url = settings.redis_url.replace("redis://", "")
    host, _, port = url.partition(":")
    return RedisSettings(host=host or "redis", port=int(port) if port else 6379)


async def get_redis_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(get_redis_settings())
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
