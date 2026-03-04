# Plan 05-01 Summary: Per-API-Key Rate Limiting

## Result: COMPLETE

## What Changed

### New Files

**`src/docingest/services/rate_limiter.py`** (133 lines)
- Redis token bucket rate limiter using atomic Lua script
- `RateLimitResult` dataclass with `allowed`, `limit`, `remaining`, `reset` fields
- `check_rate_limit(key_hash, limit)` — consumes one token, returns rate limit status
- `init_rate_limiter()` / `close_rate_limiter()` — connection lifecycle
- Separate Redis connection from ARQ pool (avoids coupling with job queue)
- Fail-open: if Redis is unavailable, requests are allowed with a warning log
- Lua script stores Redis hash with `tokens` and `last_refill`, refills at `limit/60` tokens/sec, key TTL 120s

**`src/docingest/api/middleware.py`** (23 lines)
- `RateLimitHeaderMiddleware` (Starlette `BaseHTTPMiddleware`)
- Reads `request.state.rate_limit` (set by auth dependency)
- Adds `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers to response
- Skips headers for unauthenticated endpoints (health) via `getattr` with default `None`

### Modified Files

**`src/docingest/api/auth.py`**
- Added `resolve_tenant_with_rate_limit()` dependency that:
  1. Resolves tenant via MongoDB API key lookup
  2. Calls `check_rate_limit()` with key hash and tenant's rate limit
  3. Stores `RateLimitResult` in `request.state.rate_limit` for middleware
  4. Raises `HTTPException(429)` with `Retry-After` header if rate limit exceeded
- `Tenant` type alias now uses `resolve_tenant_with_rate_limit` (API endpoints get rate limiting)
- Original `resolve_tenant` preserved for internal/worker use (no rate limiting)

**`src/docingest/api/app.py`**
- Added `RateLimitHeaderMiddleware` via `app.add_middleware()`
- Added `init_rate_limiter()` call in lifespan startup
- Added `close_rate_limiter()` call in lifespan shutdown (before other cleanup)

## Verification

- [x] `python -m py_compile src/docingest/services/rate_limiter.py` — pass
- [x] `python -m py_compile src/docingest/api/auth.py` — pass
- [x] `python -m py_compile src/docingest/api/middleware.py` — pass
- [x] `python -m py_compile src/docingest/api/app.py` — pass
- [x] Rate limiter uses Lua script for atomicity (not separate GET/SET calls)
- [x] Rate limiter fails open when Redis unavailable
- [x] 429 response includes Retry-After header
- [x] Middleware adds X-RateLimit-* headers only on authenticated responses
- [x] Health endpoint has no auth or rate limiting

## Key Decisions

- Rate limiter uses its own `redis.asyncio.Redis` connection, not the ARQ pool from `db/redis.py`
- Token bucket initializes full (first request gets full limit)
- Fail-open design: Redis failures never block API requests
- `Tenant` dependency switched to rate-limited variant; `resolve_tenant` kept for workers
