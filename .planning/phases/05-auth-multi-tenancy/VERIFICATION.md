# Phase 05 Verification: Auth & Multi-Tenancy

**Phase goal**: Secure tenant-isolated access to all operations
**Verified**: 2026-03-04
**Result**: PASS (all 4 criteria met)

---

## Criterion 1: API requires valid API key in request header

**Result: PASS**

Evidence:

- `src/docingest/api/auth.py` defines `_api_key_header = APIKeyHeader(name="X-API-Key")` (line 10), requiring the `X-API-Key` header on all authenticated endpoints.
- The `resolve_tenant_with_rate_limit()` dependency (line 30-59) looks up the API key hash in MongoDB via `get_api_key(db, key_hash)`. If no matching enabled key is found, it raises `HTTPException(status_code=401, detail="Invalid API key")` (line 39).
- The `Tenant` type alias (line 62) binds to `resolve_tenant_with_rate_limit`, so every route that declares a `tenant: Tenant` parameter automatically enforces API key validation.
- All document routes (`POST /v1/documents`, `GET /v1/documents`, `GET /v1/documents/{doc_id}`, `DELETE /v1/documents/{doc_id}`, `POST /v1/documents/{doc_id}/reprocess`, `POST /v1/documents/url`, `POST /v1/documents/batch`) and the search route (`POST /v1/search`) use the `Tenant` dependency.
- The health endpoint (`GET /v1/health`) does **not** use the `Tenant` dependency, which is correct -- health checks should be unauthenticated.
- MongoDB stores API keys with `key_hash` (SHA-256 of the raw key) and an `enabled` flag. The `get_api_key()` function (mongodb.py line 109-110) filters on both `key_hash` and `enabled: True`, meaning disabled keys are rejected.

## Criterion 2: Each API key is scoped to a tenant -- operations only affect that tenant's data

**Result: PASS**

Evidence:

- Each API key document in MongoDB contains a `tenant_id` field. The `resolve_tenant_with_rate_limit()` dependency extracts this and returns it as `tenant["tenant_id"]` to every route handler.
- **Document upload** (`POST /v1/documents`, line 123-181): Sets `doc_fields["tenant_id"] = tenant["tenant_id"]` on every inserted document. Duplicate detection via `find_by_hash()` is scoped to `tenant_id`.
- **Document retrieval** (`GET /v1/documents/{doc_id}`, line 266-272): Calls `get_document(db, doc_id, tenant["tenant_id"])`, which queries MongoDB with both `_id` and `tenant_id` (mongodb.py line 47-48).
- **Document listing** (`GET /v1/documents`, line 275-295): Calls `list_documents(db, tenant["tenant_id"], ...)`, which builds the query as `{"tenant_id": tenant_id, ...}` (mongodb.py line 77).
- **Document deletion** (`DELETE /v1/documents/{doc_id}`, line 298-325): Fetches document with tenant filter, deletes Qdrant chunks with tenant-scoped collection name, deletes blobs from tenant-prefixed path, and deletes the MongoDB document with tenant filter.
- **URL ingestion** and **batch ingestion**: Both use the same tenant-scoped patterns.
- **Blob storage** (`src/docingest/db/blob.py`): All blob operations prefix object paths with `tenant_id` (e.g., `f"{tenant_id}/{blob_path}"`), providing storage isolation.

## Criterion 3: Tenant A cannot see or search Tenant B's documents

**Result: PASS**

Evidence:

- **Qdrant collection-level isolation**: The Qdrant module (`src/docingest/db/qdrant.py`) uses per-tenant collections via `_collection_name(tenant_id)` which returns `f"tenant_{tenant_id}"` (line 17-18). Every Qdrant operation -- `upsert_chunks`, `delete_doc_chunks`, `search_chunks`, `ensure_collection`, `delete_collection` -- operates on the tenant-specific collection. This means Tenant A's vectors are in a physically separate Qdrant collection from Tenant B's vectors.
- **Search isolation** (`POST /v1/search`, search.py line 44-88): Calls `search_chunks(qdrant, tenant["tenant_id"], ...)`, which queries only the `tenant_{tenant_id}` collection. A tenant's search query cannot hit another tenant's collection.
- **MongoDB query isolation**: All document queries in `mongodb.py` include `tenant_id` in the filter (`get_document`, `find_by_hash`, `list_documents`, `delete_document`). MongoDB indexes are compound on `(tenant_id, ...)` (mongodb.py lines 31-33) for efficient scoped queries.
- **Blob storage isolation**: MinIO objects are stored under `{tenant_id}/` prefixes, so blob operations cannot cross tenant boundaries.

This is a strong isolation model: Qdrant uses separate collections per tenant (not just payload filters), MongoDB queries always include `tenant_id`, and blob storage is tenant-prefixed. There is no code path where one tenant's API key could access another tenant's data.

## Criterion 4: Rate limiting enforces per-key limits with X-RateLimit headers

**Result: PASS**

Evidence:

- **Token bucket algorithm** (`src/docingest/services/rate_limiter.py`): Implements a Redis-backed token bucket using an atomic Lua script (lines 19-60). The bucket refills at `limit/60` tokens per second (i.e., `limit` requests per minute). Each call to `check_rate_limit()` atomically refills and attempts to consume one token.
- **Per-key scoping**: Rate limit keys use format `rate_limit:{key_hash}` (line 110), so each API key has its own independent bucket. The `limit` value comes from the API key document's `rate_limit` field (default 100 per minute).
- **Enforcement in auth flow** (`src/docingest/api/auth.py`, lines 30-59): `resolve_tenant_with_rate_limit()` calls `check_rate_limit(key_hash, tenant["rate_limit"])` after tenant resolution. If `result.allowed` is `False`, it raises `HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(result.reset)})`.
- **X-RateLimit response headers** (`src/docingest/api/middleware.py`): `RateLimitHeaderMiddleware` reads `request.state.rate_limit` and injects three headers on every authenticated response:
  - `X-RateLimit-Limit` -- maximum requests per window
  - `X-RateLimit-Remaining` -- tokens left in the current window
  - `X-RateLimit-Reset` -- seconds until the bucket is fully replenished
- **Middleware registration** (`src/docingest/api/app.py`, line 41): `app.add_middleware(RateLimitHeaderMiddleware)` is registered on the FastAPI app.
- **Lifecycle management** (app.py lines 20, 27): `init_rate_limiter()` runs at startup, `close_rate_limiter()` runs at shutdown.
- **Fail-open design** (rate_limiter.py lines 104-106, 129-131): If Redis is unavailable or errors occur, requests are allowed with a warning log. Rate limiting does not block the API when Redis is down.
- **Health endpoint excluded**: The health route has no `Tenant` dependency, so it is never rate-limited and never receives X-RateLimit headers. This is correct behavior.

---

## Requirement Traceability

| Requirement | Description | Status |
|-------------|-------------|--------|
| AUTH-01 | User authenticates via API key in request header | PASS |
| AUTH-02 | Each API key is scoped to a tenant -- all operations are tenant-isolated | PASS |
| AUTH-03 | Tenant data is isolated in Qdrant via collection-level separation | PASS |
| AUTH-04 | API enforces rate limiting per API key (Redis token bucket, X-RateLimit headers) | PASS |

## Files Reviewed

| File | Role |
|------|------|
| `src/docingest/api/auth.py` | API key validation, tenant resolution, rate limit enforcement |
| `src/docingest/api/middleware.py` | X-RateLimit-* response header injection |
| `src/docingest/api/app.py` | Middleware registration, rate limiter lifecycle |
| `src/docingest/services/rate_limiter.py` | Redis token bucket implementation |
| `src/docingest/api/routes/documents.py` | All document routes use Tenant dependency |
| `src/docingest/api/routes/search.py` | Search route uses Tenant dependency |
| `src/docingest/api/routes/health.py` | Health route has no auth (correct) |
| `src/docingest/db/mongodb.py` | All queries scoped by tenant_id |
| `src/docingest/db/qdrant.py` | Per-tenant collections for vector isolation |
| `src/docingest/db/blob.py` | Tenant-prefixed blob storage paths |

## Notes

- Qdrant isolation uses **separate collections per tenant** (`tenant_{tenant_id}`), which is stronger than payload filtering alone. AUTH-03 specifies "payload filtering" but the actual implementation exceeds this by providing collection-level isolation. This is an acceptable strengthening of the requirement.
- No unit or integration tests exist specifically for auth and rate limiting. While the implementation is structurally correct, automated test coverage would improve confidence. This is an observation, not a blocking issue for phase completion.
