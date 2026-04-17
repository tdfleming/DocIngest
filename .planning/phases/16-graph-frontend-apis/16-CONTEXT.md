# Phase 16: Graph Frontend APIs - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

**In scope:**
- Add **4 new REST endpoints** under the existing `/v1/graph/` router (`src/docingest/api/routes/graph.py`):
  1. `GET /v1/graph/entities` — paginated entity list with optional `entity_type` filter + optional `q` name-substring search (ENT-05)
  2. `GET /v1/graph/entities/{entity_id}` — entity detail including linked `doc_ids` and neighbor preview (ENT-05)
  3. `GET /v1/graph/communities` — paginated community list with optional `level` filter (COMM-UI-05)
  4. `GET /v1/graph/communities/{community_id}` — community detail with member entities expanded (COMM-UI-05)
  5. `POST /v1/graph/search` — embed query text, rank communities by cosine similarity to `summary_embedding`, return top-k (SEARCH-G-03)
- Add **2 new helpers** to `src/docingest/db/graph_store.py`:
  - Enhanced `list_entities` with `q` parameter for name substring search (extend existing helper, not replace)
  - `list_communities(db, tenant_id, level, page, per_page) -> tuple[list[dict], int]` — paginated, level-filterable
  - `get_community_by_id(db, community_id, tenant_id) -> dict | None`
- Add **Pydantic response models** in `graph.py` (or a sibling schemas module) mirroring `DocumentResponse` + `DocumentListResponse` conventions.
- Wire gating: every new route starts with `if not settings.graph_rag_enabled: raise HTTPException(403, "Graph RAG is not enabled")` — matches existing pattern at `graph.py:27`.
- Tests: `tests/test_graph_api.py` covering success/gated-off/tenant-scoping/pagination/filter combinations.
- Closes REQ-IDs **ENT-05, COMM-UI-05, SEARCH-G-03**.

**Out of scope (explicitly NOT this phase):**
- Frontend consumption — phases 17-20 handle React components, hooks, pages. No `frontend/src/` changes.
- Mutation endpoints (create/update/delete entities or communities). Entity graph is worker-owned; mutations are not a v1.1 feature.
- Graph traversal endpoints (k-hop neighborhood, path-finding). `get_entity_neighbors` exists but isn't needed for v1.1 UI.
- Extending `POST /v1/search` with community fields — explicitly rejected in discussion. Graph search is a separate endpoint so `/v1/search` stays unchanged.
- Admin tenant-cross-tenant APIs. Tenant isolation is preserved via `Tenant` dependency.
- New MongoDB indexes on `entities.name` for text search — regex suffices for v1.1 scale; add later only if measurements demand it.
- Rate-limit overrides for graph routes — inherits tenant default from `Tenant` dependency.
- OpenAPI `examples:` blocks. Router-level `tags=["graph"]` already in place; endpoints pick up schema automatically.
- Server-Sent Events / streaming responses. All endpoints are plain JSON.

</domain>

<decisions>
## Implementation Decisions

### Route layout (locked)
- **D-01:** All 5 endpoints live under `/v1/graph/` on the existing `router` in `src/docingest/api/routes/graph.py`. Do NOT create a new router file; extend the existing one.
- **D-02:** Method convention: `GET` for reads (entities list/detail, communities list/detail); `POST` for `/v1/graph/search` (mirrors `/v1/search` + allows future query extensions without URL changes).
- **D-03:** Every new route starts with the same gating block as the existing `rebuild_communities` (raise 403 when `settings.graph_rag_enabled` is false).
- **D-04:** Do NOT extend `POST /v1/search` with an `include_communities` flag — graph search is a distinct endpoint. `search.py` stays untouched.

### List response shape (locked)
- **D-05:** Match the `DocumentListResponse` shape from `src/docingest/api/routes/documents.py:98-102`:
  ```python
  class EntityListResponse(BaseModel):
      entities: list[EntityResponse]
      total: int
      page: int
      per_page: int

  class CommunityListResponse(BaseModel):
      communities: list[CommunitySummary]
      total: int
      page: int
      per_page: int
  ```
- **D-06:** Query params: `page: int = 1` (Query, ge=1), `per_page: int = 50` (Query, ge=1, le=200). Match `list_entities` helper defaults.

### Entity name search (locked)
- **D-07:** Case-insensitive regex substring: query selector becomes `{"name": {"$regex": escaped_q, "$options": "i"}}` when `q` is non-empty. Must call `re.escape()` server-side to defuse regex metachars in user input.
- **D-08:** Empty `q` → no name filter applied (treated as absent). No min-length guard on the backend; frontend is responsible for debouncing keystrokes.
- **D-09:** Type filter (`entity_type`) and search (`q`) are **optional, AND-combined** when both present. Extend `list_entities(db, tenant_id, entity_type, q, page, per_page)` in `graph_store.py` to accept the new `q` parameter (default `None`).
- **D-10:** No new index on `entities.name` — tenant entity counts are small (<10k typical). Revisit if P95 query time exceeds 100ms in prod.

### Entity detail (locked)
- **D-11:** `GET /v1/graph/entities/{entity_id}` response includes all `Entity` model fields (id, tenant_id, name, entity_type, mention_count, doc_ids, chunk_ids, created_at, updated_at) but explicitly omits `embedding` (expensive to serialize, unused by frontend).
- **D-12:** **Tenant scope enforcement:** the endpoint does a secondary check `doc["tenant_id"] == tenant["tenant_id"]` on the returned entity; returns 404 if mismatch. Prevents tenant-id leakage via ObjectId guessing. Returns 404 (not 403) for unknown/other-tenant IDs so we don't leak existence.
- **D-13:** No neighbor expansion in v1.1. `doc_ids` is enough; frontend links to `/documents/{id}` directly. The `get_entity_neighbors` helper stays unused this phase.

### Community list (locked)
- **D-14:** Flat paginated list (**not** nested tree). Response items include `parent_community_id` and `child_community_ids` so the frontend can build the tree client-side.
- **D-15:** Default sort: `(level ASC, title ASC)`. Optional query param `level: int | None` filters to a single resolution level.
- **D-16:** New helper `list_communities(db, tenant_id, level, page, per_page) -> (list[dict], int)` follows the shape of `list_entities`. Mirror the code pattern exactly.
- **D-17:** List items use a lean shape — `CommunitySummary`: id, level, title, summary (truncated? no — full summary is fine, extractive summaries are short by design), entity_count (derived via `len(entity_ids)`), parent_community_id, child_community_ids, created_at, updated_at. Do NOT include `summary_embedding` or `entity_ids` array in list items (payload bloat).

### Community detail (locked)
- **D-18:** `GET /v1/graph/communities/{community_id}` returns the full community + expanded `member_entities: list[EntityResponse]` (batch-fetched via `get_entity_by_id` over `entity_ids`). Saves N+1 fetches from frontend.
- **D-19:** New helper `get_community_by_id(db, community_id, tenant_id) -> dict | None` with tenant-scope enforcement on the returned document (same 404 pattern as D-12).
- **D-20:** Do NOT include `summary_embedding` in detail response. Frontend has no use for it.
- **D-21:** Member entities in detail response use the same `EntityResponse` model as the list endpoint (consistent typing for the frontend).

### Graph search endpoint (locked)
- **D-22:** `POST /v1/graph/search` with request body `{query: str, limit: int = Field(default=5, ge=1, le=20)}`.
- **D-23:** Response shape (separate from SearchResponse for `/v1/search` to keep namespaces clean):
  ```python
  class CommunityMatch(BaseModel):
      id: str
      title: str
      summary: str
      level: int
      score: float
      entity_ids: list[str]

  class GraphSearchResponse(BaseModel):
      results: list[CommunityMatch]
      query_tokens: int
      search_time_ms: int
  ```
- **D-24:** Implementation: embed `request.query` via `embed_query` with `run_in_executor` (copy the pattern from `search.py:49-50`); pass the resulting vector into `search_communities_by_embedding`. Measure elapsed time with `time.monotonic()` (same pattern as `search.py`).
- **D-25:** No reranker, no filters. Communities are already tenant-scoped in the DB call. Zero additional post-processing beyond the cosine rank.
- **D-26:** Return empty `results: []` when the tenant has no communities with embeddings. `search_communities_by_embedding` already returns `[]` in that case — just surface it.

### Pydantic response models (locked)
- **D-27:** Define response models inline at the top of `graph.py` (not a separate schemas module) — sibling pattern to `documents.py` which also defines its response models inline. Keep the file under ~200 lines; split only if it bloats.
- **D-28:** Field conversions:
  - `_id: ObjectId` → `id: str` via explicit `str(doc["_id"])` (same pattern as `_doc_to_response`)
  - `datetime` fields → ISO strings via `.isoformat()` (same pattern as phase 14)
- **D-29:** Do NOT add mapper helper functions like `_entity_to_response` unless the same shape is used in 2+ places. For this phase, 1 entity mapper + 1 community-summary mapper + 1 community-detail mapper is right.

### Gating + tenant scope (locked)
- **D-30:** All 5 new routes use the `Tenant` dependency (not `CurrentUser`). Matches `rebuild_communities` at `graph.py:19` and the entire `/v1/documents/*` surface.
- **D-31:** Log every new route with `log.info("graph_entities_list", tenant_id=..., page=..., per_page=..., ...)` using structured kwargs. Event-name convention: `graph_<resource>_<action>` (e.g., `graph_communities_detail`, `graph_search_started`, `graph_search_complete`).

### Testing (locked)
- **D-32:** New test file: `tests/test_graph_api.py`. Follow patterns from `tests/test_documents_graph_cleanup.py` and `tests/test_documents_graph_response.py` (real MongoDB fixtures + `httpx.AsyncClient`).
- **D-33:** Coverage targets (each endpoint):
  - Gating: 403 when `settings.graph_rag_enabled=false`
  - Tenant scoping: cross-tenant ID returns 404, never leaks data
  - Pagination: page=1, page=2, empty page beyond total returns empty list + correct total
  - Filter correctness: `entity_type=PERSON` excludes other types; `level=1` excludes other levels
  - Search correctness: `q=joh` returns names containing "joh" case-insensitively; regex metachars in `q` don't crash (`re.escape` test)
  - Graph search: query with known-relevant community returns that community ranked high; empty-tenant returns `[]`
- **D-34:** Do NOT gate tests with `needs_graph` / `igraph` skip markers — these endpoints don't import igraph directly. They depend only on MongoDB fixtures + FastAPI TestClient.

### Claude's Discretion
- Whether to import `re` at module top or lazy-import inside the handler (either is fine; module-top is more conventional).
- Exact field order on response models (cosmetic).
- Whether to factor the common gating/404 block into a tiny helper or inline it in each endpoint (inline is fine for 5 endpoints).
- Choice of `_doc_to_response`-style helper naming: `_entity_to_response` / `_community_summary_to_response` / `_community_detail_to_response` — names are planner/executor's call.
- Whether to add a docstring example for `POST /v1/graph/search` (nice-to-have).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §ENT-05 (line 40) — entity endpoints
- `.planning/REQUIREMENTS.md` §COMM-UI-05 (line 50) — community endpoints
- `.planning/REQUIREMENTS.md` §SEARCH-G-03 (line 58) — graph search endpoint

### Source of truth — files to edit
- `src/docingest/api/routes/graph.py` — extend the existing router (today has only `POST /communities/rebuild`). Add Pydantic models + 5 new routes.
- `src/docingest/db/graph_store.py` — extend `list_entities` with `q` parameter (line 274); add new helpers `list_communities` and `get_community_by_id`.
- `tests/test_graph_api.py` — new test file.

### Source of truth — files to READ but NOT modify
- `src/docingest/api/routes/documents.py` lines 81-135 — reference for `DocumentResponse` + `DocumentListResponse` + `_doc_to_response` patterns (mirror these for entities + communities).
- `src/docingest/api/routes/search.py` lines 17-43 + 45-90 — reference for POST-with-body pattern, `run_in_executor` embed, elapsed timing.
- `src/docingest/models/graph.py` — `Entity`, `Relationship`, `Community`, `EntityType` model shapes.
- `src/docingest/db/graph_store.py` lines 161-294 — existing helpers (`get_entity_by_id`, `list_entities`, `get_communities_by_level`, `search_communities_by_embedding`).
- `src/docingest/services/embedding.py::embed_query` — sync function, must run in executor.
- `src/docingest/api/auth.py` — `Tenant` dependency.
- `src/docingest/config.py` — `settings.graph_rag_enabled`.

### Reference patterns
- Phase 13 pattern for gating: see `src/docingest/api/routes/documents.py:354-363` for `if settings.graph_rag_enabled:` guard with try/except/log (phase 13 lenient mode is not relevant here — we want strict 403 gating like `graph.py:27`).
- Phase 14 pattern for mapping dict → response model: see `src/docingest/api/routes/documents.py::_doc_to_response` (lines 119-135).

### Roadmap & planning
- `.planning/ROADMAP.md` §Phase 16 — goal and success criteria.
- `.planning/phases/14-surface-graph-status-via-document-api/14-CONTEXT.md` — reference for sibling phase conventions (Pydantic v2, `.isoformat()` pattern).

### Project conventions
- `CLAUDE.md` — structlog, async throughout, `settings.graph_rag_enabled` gating, Pydantic v2 with `populate_by_name`, `Edit`/`Write` tools only, pytest+asyncio_mode="auto".

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `list_entities(db, tenant_id, entity_type, page, per_page)` at `graph_store.py:274` — just add `q` parameter.
- `get_entity_by_id(db, entity_id)` at `graph_store.py:161` — add tenant-scope check at the call site (route handler).
- `get_communities_by_level(db, tenant_id, level)` at `graph_store.py:341` — keep existing; add a new paginated `list_communities` rather than changing this one.
- `search_communities_by_embedding(db, tenant_id, query_embedding, limit)` at `graph_store.py:350` — Python-side cosine; already correct.
- `embed_query(text) -> (vec, token_count)` from `services/embedding.py` — sync; wrap in `loop.run_in_executor` (pattern at `search.py:50`).
- `Tenant` + `APIKeyHeader` auth + rate limiting — inherited from `api/auth.py`.
- Existing graph router at `api/routes/graph.py` with `prefix="/graph"` and `tags=["graph"]`.

### Established Patterns
- Pydantic v2 with `populate_by_name=True`, `Field(alias="_id")` for id fields.
- `datetime` → ISO string via `.isoformat()` on response.
- Route gating at call site: `if not settings.graph_rag_enabled: raise HTTPException(status_code=403, detail="Graph RAG is not enabled")`.
- Tenant-scoped queries: every MongoDB selector includes `tenant_id`.
- POST search with Pydantic body + timing via `time.monotonic()` (search.py pattern).
- Pagination: `(page, per_page)` query params, `(items, total)` tuple from helper.
- Test patterns: `tests/test_documents_graph_cleanup.py` uses real MongoDB + FastAPI `httpx.AsyncClient`.

### Integration Points
- `api/app.py` already mounts the graph router under `/v1` — no router mounting changes.
- Frontend phases 18-20 will consume these endpoints via `frontend/src/api/` + TanStack Query hooks. Response shapes must match `DocumentListResponse` convention so existing patterns can be reused.
- No changes to existing routes (`/v1/documents`, `/v1/search`, `/v1/graph/communities/rebuild`).

### Non-Integration (don't touch)
- `src/docingest/workers/graph_builder.py` — writes, not reads.
- `src/docingest/db/mongodb.py` — no new indexes this phase.
- `src/docingest/services/community_detection.py` — write path only.
- Existing graph-status fields on `DocumentResponse` (phase 14) stay as-is.

</code_context>

<specifics>
## Specific Ideas

### Proposed shapes (planner may polish wording)

**Entity response:**
```python
class EntityResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    entity_type: str
    mention_count: int = 0
    doc_ids: list[str] = []
    chunk_ids: list[str] = []
    created_at: str
    updated_at: str
    # NOT included: embedding
```

**Entity list endpoint:**
```python
@router.get("/entities")
async def list_entities_route(
    tenant: Tenant,
    entity_type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> EntityListResponse:
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    docs, total = await list_entities(
        db, tenant["tenant_id"], entity_type=entity_type, q=q,
        page=page, per_page=per_page,
    )
    log.info("graph_entities_list", tenant_id=tenant["tenant_id"], page=page, count=len(docs), total=total)
    return EntityListResponse(
        entities=[_entity_to_response(d) for d in docs],
        total=total, page=page, per_page=per_page,
    )
```

**Community detail endpoint (with member entity expansion):**
```python
@router.get("/communities/{community_id}")
async def get_community_detail(
    tenant: Tenant,
    community_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> CommunityDetailResponse:
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    comm = await get_community_by_id(db, community_id, tenant["tenant_id"])
    if not comm:
        raise HTTPException(status_code=404, detail="Community not found")
    # Batch-fetch member entities
    member_docs = await asyncio.gather(*[
        get_entity_by_id(db, eid) for eid in comm["entity_ids"]
    ])
    members = [_entity_to_response(d) for d in member_docs if d]
    return CommunityDetailResponse(
        **_community_base_fields(comm),
        member_entities=members,
    )
```

**Graph search endpoint:**
```python
@router.post("/search")
async def graph_search(tenant: Tenant, request: GraphSearchRequest, db: ... = Depends(...)) -> GraphSearchResponse:
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    start = time.monotonic()
    loop = asyncio.get_running_loop()
    query_vector, token_count = await loop.run_in_executor(None, embed_query, request.query)
    matches = await search_communities_by_embedding(
        db, tenant["tenant_id"], query_vector, limit=request.limit,
    )
    # ranking score lives on the returned dict per existing helper
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return GraphSearchResponse(
        results=[_community_match(m) for m in matches],
        query_tokens=token_count, search_time_ms=elapsed_ms,
    )
```

### Helper signatures to add

```python
# graph_store.py (additions)

async def list_entities(  # EXTEND existing
    db, tenant_id, entity_type=None, q=None, page=1, per_page=50,
) -> tuple[list[dict], int]:
    query = {"tenant_id": tenant_id}
    if entity_type:
        query["entity_type"] = entity_type
    if q:
        query["name"] = {"$regex": re.escape(q), "$options": "i"}
    # ... rest unchanged

async def list_communities(
    db, tenant_id, level=None, page=1, per_page=50,
) -> tuple[list[dict], int]:
    query = {"tenant_id": tenant_id}
    if level is not None:
        query["level"] = level
    total = await db.communities.count_documents(query)
    cursor = (
        db.communities.find(query)
        .sort([("level", 1), ("title", 1)])
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    docs = await cursor.to_list(length=per_page)
    return docs, total

async def get_community_by_id(
    db, community_id, tenant_id,
) -> dict | None:
    doc = await db.communities.find_one(
        {"_id": ObjectId(community_id), "tenant_id": tenant_id}
    )
    return doc  # Tenant check baked into query
```

**Note on tenant scoping:** For entity detail, the planner's choice of secondary tenant check in the route vs. passing `tenant_id` through `get_entity_by_id` → let's align them. `get_community_by_id` includes `tenant_id` in the selector (cleaner). `get_entity_by_id` currently doesn't — either extend it to accept `tenant_id` (same pattern) or check at the call site. **Recommendation:** extend `get_entity_by_id` to accept `tenant_id` with a default `None` for back-compat with existing callers, and require it (pass it) from the route handler. Planner's call on whether this is clean.

### Grep-able acceptance criteria (for PLAN.md DoD)
- `grep -n "def list_entities_route\|def get_entity_detail\|def list_communities_route\|def get_community_detail\|def graph_search" src/docingest/api/routes/graph.py` returns **5 matches** (one per route).
- `grep -n "def list_communities\|def get_community_by_id" src/docingest/db/graph_store.py` returns **2 matches**.
- `grep -n "$regex" src/docingest/db/graph_store.py` returns **at least 1 match** (in `list_entities`).
- `grep -n "settings.graph_rag_enabled" src/docingest/api/routes/graph.py` returns **at least 6 matches** (5 new + existing `rebuild_communities`).
- `grep -n "EntityResponse\|EntityListResponse\|CommunitySummary\|CommunityDetailResponse\|CommunityMatch\|GraphSearchRequest\|GraphSearchResponse" src/docingest/api/routes/graph.py` returns **at least 7 matches** (each model defined once + used in responses).
- `tests/test_graph_api.py` exists with ≥ 12 test functions covering all 5 endpoints × (success, gated-off, tenant-scope, pagination, filter where applicable).
- `git diff src/docingest/api/routes/search.py` is empty.
- `git diff src/docingest/workers/graph_builder.py` is empty.
- `git diff src/docingest/db/mongodb.py` is empty (no new indexes this phase).
- `pytest tests/test_graph_api.py` exits 0.
- Full suite (`pytest tests/ --ignore=tests/test_entity_extraction.py`) stays green.
- `ruff check src/` passes.

### Windows/shell note
All edits via `Edit` / `Write` tools (no sed/awk/heredoc). API hot-reloads under `uvicorn --reload` in the Docker dev stack; restart `ingestion-api` container if autoreload doesn't pick up.

</specifics>

<deferred>
## Deferred Ideas

### Future phases within v1.1
- **Phases 17-20** consume these endpoints. 17 uses existing `DocumentResponse` fields (no dependency on phase 16). 18, 19, 20 depend on phase 16 landing first.

### Post-v1.1
- Entity mutation endpoints (merge, delete, rename) — requires UI design for dedup workflows.
- Graph traversal endpoints — `/v1/graph/entities/{id}/neighbors?hops=N` using the existing `get_entity_neighbors` helper. Not in v1.1 UI scope.
- Text index on `entities.name` for faster search at scale. Revisit if measured latency is a problem.
- Server-Sent Events for community rebuild progress. Useful if rebuild takes >30s; not worth building until we hit that.
- GraphML / CSV export of tenant graph. Out of scope for v1.1 per REQUIREMENTS.md.
- Community search via hybrid embedding + keyword match. Current `search_communities_by_embedding` is pure cosine; hybrid would need BM25 or similar.

### Out of scope — rejected/locked
- Extending `POST /v1/search` with `include_communities` flag (explicitly rejected in step 1 gray-area discussion).
- Nested tree response for community list (explicitly rejected in step 3 — D-14).
- Minimum query length guard for entity search (explicitly rejected in step 2 — D-08).
- Reranker on graph search (explicitly rejected in step 4 — D-25).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 16-graph-frontend-apis*
*Context gathered: 2026-04-17*
