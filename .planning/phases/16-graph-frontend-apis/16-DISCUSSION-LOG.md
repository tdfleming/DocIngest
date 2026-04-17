# Phase 16: Graph Frontend APIs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `16-CONTEXT.md` — this log preserves alternatives considered.

**Session:** 2026-04-17
**Participants:** User (visionary), Claude (builder)

---

## Scout findings presented up-front

Claude summarized existing helpers before discussion:

| Capability | Helper exists? | Location |
|---|---|---|
| Entity list paginated + type filter | ✅ `list_entities` | `graph_store.py:274` |
| Entity by ID | ✅ `get_entity_by_id` (needs tenant-scope wrap) | `graph_store.py:161` |
| Entity name search | ❌ — extend existing helper | — |
| Community list (all levels, paginated) | ❌ — new helper needed | — |
| Community by ID | ❌ — new helper needed | — |
| Community list at specific level | ✅ `get_communities_by_level` (non-paginated) | `graph_store.py:341` |
| Community embedding search | ✅ `search_communities_by_embedding` | `graph_store.py:350` |
| Query embedding | ✅ `embed_query` via `run_in_executor` | `services/embedding.py` + `routes/search.py:50` |

→ 4 new routes + 2 new helpers + extension to `list_entities`.

---

## Gray area selection

**Options:** (1) Endpoint surface, (2) Name search mechanics, (3) Community list shape, (4) Graph search shape.

**User selection:** ALL FOUR.

---

## Area 1 — Endpoint surface shape

### Q1.1: Route layout

**Options:**
- 4 new routes under `/v1/graph/` (Recommended)
- Extend `/v1/search` with `include_communities` flag
- Full split — `/v1/entities` + `/v1/communities` at top-level

**User selection:** **4 new routes under `/v1/graph/`** → D-01, D-02, D-04.

### Q1.2: List response shape

**Options:**
- Match `/documents` shape (Recommended)
- Generic `{items, total, page, per_page}`
- Cursor-based

**User selection:** **Match /documents shape** → D-05, D-06.

---

## Area 2 — Entity name search mechanics

### Q2.1: Query mechanism

**Options:**
- Case-insensitive `$regex` substring (Recommended)
- MongoDB text index (`$text`)
- Prefix-only (starts-with)

**User selection:** **Case-insensitive `$regex` substring** → D-07 with `re.escape` guard.

### Q2.2: Combine type filter + name search

**Options:**
- Both optional, AND'd (Recommended)
- Search-only mode (ignore type)

**User selection:** **Both optional, AND'd** → D-09.

### Q2.3: Backend min-length guard

**Options:**
- No backend guard (Recommended)
- Require q >= 2 chars

**User selection:** **No backend guard** → D-08.

---

## Area 3 — Community list shape + hierarchy

### Q3.1: Response shape

**Options:**
- Flat paginated + client-side hierarchy (Recommended)
- Nested tree
- Two endpoints (roots + children)

**User selection:** **Flat paginated + client-side hierarchy** → D-14, D-17.

### Q3.2: Default sort + filter

**Options:**
- Sort `(level asc, title asc)`; level filter (Recommended)
- Sort by entity_count desc
- Sort by updated_at desc

**User selection:** **Sort `(level asc, title asc)`; optional level filter** → D-15.

### Q3.3: Detail response contents

**Options:**
- Full community + expanded member_entities (Recommended)
- Just entity_ids (client fetches)
- Include summary_embedding

**User selection:** **Full community + expanded member_entities** → D-18, D-21. Explicitly exclude embedding → D-20.

---

## Area 4 — Graph search endpoint + response

### Q4.1: HTTP method + shape

**Options:**
- POST /v1/graph/search (Recommended)
- GET /v1/graph/search?q=...
- Extend POST /v1/search with flag

**User selection:** **POST /v1/graph/search** → D-22 (mirrors /v1/search pattern).

### Q4.2: Per-match fields

**Options:**
- id, title, summary, level, score, entity_ids (Recommended)
- Above + expanded member_entities
- Minimal: id, title, summary, score

**User selection:** **id, title, summary, level, score, entity_ids** → D-23.

### Q4.3: Default limit + cap

**Options:**
- default 5, max 20 (Recommended)
- default 10, max 50
- No cap

**User selection:** **default 5, max 20** → D-22 `Field(default=5, ge=1, le=20)`.

### Q4.4: Final — create context?

**User selection:** **Write context** — enough decisions captured.

---

## Summary of locked decisions

| # | Decision |
|---|----------|
| D-01..04 | 5 routes under `/v1/graph/`; POST for search; GET for reads; gate all on `graph_rag_enabled`; don't touch `/v1/search` |
| D-05..06 | List response shape matches `DocumentListResponse`; `page=1, per_page=50 (max 200)` |
| D-07..10 | Case-insensitive `re.escape`'d `$regex` substring; no min-length guard; AND with optional type filter; no new index |
| D-11..13 | Entity detail includes all fields except `embedding`; tenant-scope check at route; no neighbor expansion in v1.1 |
| D-14..17 | Flat paginated community list; sort `(level asc, title asc)`; optional `level` filter; lean list items (no embedding/entity_ids) |
| D-18..21 | Community detail batch-fetches member entities; tenant-scoped helper; no embedding in detail; consistent `EntityResponse` typing |
| D-22..26 | `POST /v1/graph/search` with `query + limit (5, max 20)`; returns `{results, query_tokens, search_time_ms}`; embed via `run_in_executor`; no reranker; empty results on no-communities |
| D-27..29 | Response models inline in `graph.py`; explicit str/isoformat conversion; 3 mapper helpers |
| D-30..31 | `Tenant` dep on all routes; structured logging with `graph_<resource>_<action>` event names |
| D-32..34 | New `tests/test_graph_api.py`; 12+ tests covering 5 endpoints × (success/403/scope/pagination/filter); no igraph skip marker |

## Deferred ideas captured

- Entity mutations (merge/delete/rename) — out of scope.
- Graph traversal endpoints — `get_entity_neighbors` exists but unused in v1.1.
- Text index on `entities.name` — defer unless measured slow.
- SSE for rebuild progress, GraphML export, hybrid search — all future.

---

*Audit trail only. Decisions captured in 16-CONTEXT.md.*
