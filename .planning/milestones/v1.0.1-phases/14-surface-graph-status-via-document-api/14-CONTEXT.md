# Phase 14: Surface Graph Status via Document API - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

**In scope:**
- Declare `graph_built_at: datetime | None = None` on the `Document` model in `src/docingest/models/document.py` (alongside the existing `graph_status`, `entity_count`, `relationship_count`).
- Extend `DocumentResponse` in `src/docingest/api/routes/documents.py` with 4 new fields: `graph_status`, `entity_count`, `relationship_count`, `graph_built_at`.
- Extend `_doc_to_response` mapper in the same file to populate the 4 fields from the MongoDB document dict.
- Add pytest coverage: assertions that `GET /v1/documents/{id}` and `GET /v1/documents` return the 4 new fields in both `graph_rag_enabled=true` and `graph_rag_enabled=false` cases.
- Close REQ-IDs **GRAPH-WORKER-01** and **GRAPH-WORKER-04**.

**Out of scope (explicitly NOT this phase):**
- Upload, reprocess, delete, batch, or URL-ingest route response shapes — those return operational status dicts (`{"id": ..., "status": "pending"}`), not DocumentResponse. Do not modify them.
- Frontend code under `frontend/src/` — there is currently no consumer for these fields. Future phases or the UI team can wire up a "Graph" badge/column separately.
- Community count (`community_count`) — not named in phase 14 REQ-IDs; belongs in a future community-surface phase if ever needed.
- Derived fields (e.g., a synthesized `graph_error` combining `error_type`+`error_stage`) — explicitly rejected in discussion.
- Pydantic `exclude_none` / conditional field omission — explicitly rejected in D-05.
- Backfill migration for pre-existing documents missing these fields — Pydantic defaults handle this automatically (graph_status=None, counts=0, graph_built_at=None).
- Removing the duplicate `ensure_graph_indexes` call (INT-01) — that's Phase 15.
- The asyncio deprecation fix in entity_extraction.py (EE-08) — that's Phase 15.

</domain>

<decisions>
## Implementation Decisions

### Fields to expose (locked)
- **D-01:** Expose **4 fields** on DocumentResponse: `graph_status`, `entity_count`, `relationship_count`, `graph_built_at`. Not 3. Including `graph_built_at` is consistent with what the worker writes and enables UI timestamp UX.
- **D-02:** Types:
  - `graph_status: str | None = None` — matches Document model, values are `None` / `"building"` / `"complete"` / `"failed"`.
  - `entity_count: int = 0` — matches Document model.
  - `relationship_count: int = 0` — matches Document model.
  - `graph_built_at: str | None = None` — serialized as ISO 8601 string (same pattern as `created_at`, `updated_at` which use `.isoformat()`).

### Defaults for non-graph-built docs (locked)
- **D-03:** When the graph worker has not run for a document (new upload, or `graph_rag_enabled=false`), response values are: `graph_status=None`, `entity_count=0`, `relationship_count=0`, `graph_built_at=None`. Clients use `graph_status is None` to detect "not yet built" vs. `graph_status="complete", entity_count=0` to detect "built but zero entities".
- **D-04:** No `"pending"` placeholder status — the `None`/`"complete"` distinction is enough. Do not synthesize derived statuses in `_doc_to_response`.

### Gating behavior (locked)
- **D-05:** **Always expose** the 4 fields unconditionally on DocumentResponse, with defaults as per D-03. Do NOT conditionally omit based on `settings.graph_rag_enabled`. Same response shape regardless of gate state.
- **D-06:** Rationale: Simpler API contract; matches "unused feature returns defaults" pattern common in v1.0 APIs; no FastAPI `model_dump(exclude=...)` or dual-response-class branching. The REQUIREMENTS.md wording "returns these fields when graph_rag_enabled" is interpreted as "these are the values of interest when gate is on" rather than "conditional field existence".

### Response shape scope (locked)
- **D-07:** Only `DocumentResponse` and `_doc_to_response` change. That covers BOTH `GET /v1/documents/{id}` (line 319) and `GET /v1/documents` (list, line 338) — both funnel through the same mapper.
- **D-08:** Do NOT modify operational routes (upload, reprocess, delete, batch-URL, URL-ingest) — they return raw dicts with `{"id", "status", ...}` and that contract stays unchanged.

### Model declaration (locked)
- **D-09:** Add `graph_built_at: datetime | None = None` to the `Document` model in `src/docingest/models/document.py` right after `relationship_count` (line 57). This gives the field a formal type contract instead of relying on `extra_fields` dict leakage from `graph_builder.py:254`.
- **D-10:** Do NOT modify the graph-worker write path — it already writes `graph_built_at` via `extra_fields`. The Document model declaration is cosmetic/type-safety; the MongoDB layer is already correct.
- **D-11:** In `_doc_to_response`, convert `graph_built_at` to ISO string with `.isoformat()` only when not None — mirror the pattern used for `created_at`/`updated_at`:
  ```python
  graph_built_at=doc["graph_built_at"].isoformat() if doc.get("graph_built_at") else None,
  ```

### Claude's Discretion
- Exact test file name (`tests/test_documents_graph_response.py` or fold into `tests/test_documents_graph_cleanup.py` — planner's call).
- Whether to add an OpenAPI docstring on DocumentResponse explaining "graph_status is None until worker runs" (nice-to-have, low cost).
- Order of the 4 new fields within DocumentResponse (suggest: after `chunk_count`, before `version` — groups with other computed progress fields).
- Whether to add 4 corresponding fields to `Document` model if any are missing (already verified: only `graph_built_at` is missing).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (PRD source)
- `.planning/v1.0-MILESTONE-AUDIT.md` §INT-02 (lines ~118-122 and ~272) — evidence: "DocumentResponse in documents.py:79-95 omits graph_status/entity_count/relationship_count; _doc_to_response strips them."

### Requirements
- `.planning/REQUIREMENTS.md` §GRAPH-WORKER-01 (line 179) — exposes `graph_status`, `entity_count`, `relationship_count`.
- `.planning/REQUIREMENTS.md` §GRAPH-WORKER-04 (line 206) — exposes `entity_count`, `relationship_count` (subset of GRAPH-WORKER-01; same root cause).

### Source of truth — files to edit
- `src/docingest/models/document.py` — add `graph_built_at: datetime | None = None` at line 57 (after `relationship_count`).
- `src/docingest/api/routes/documents.py` — extend `DocumentResponse` (line 81-95) and `_doc_to_response` (line 119-135).

### Source of truth — helpers used (do NOT modify)
- `src/docingest/workers/graph_builder.py` line 254 — writes `graph_built_at` via `extra_fields`. No change needed.
- `src/docingest/db/mongodb.py` — `get_document`/`list_documents` already return raw dicts; no transformation needed.

### Reference patterns (how existing fields flow)
- `src/docingest/api/routes/documents.py:133-134` — `.isoformat()` pattern for datetime fields (`created_at`, `updated_at`).
- `src/docingest/models/document.py:50` — Optional `str | None` pattern with default `None` (mirrored for graph_built_at).

### Roadmap & planning
- `.planning/ROADMAP.md` §Phase 14 (line 52-55) — phase goal and gap-closure target.
- `.planning/phases/13-wire-graph-data-lifecycle-cleanup/13-CONTEXT.md` — sibling gap-closure phase; same audit source, same conventions.

### Project conventions
- `CLAUDE.md` — Pydantic v2 with `populate_by_name=True`, StrEnum for enums, structlog, async throughout, Edit/Write tools only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_doc_to_response` already exists at `documents.py:119-135` — single site to extend; both detail (line 319) and list (line 338) endpoints funnel through it.
- Document model (`src/docingest/models/document.py`) already declares 3 of 4 graph fields with correct defaults.
- `.isoformat()` pattern at line 133-134 is the blueprint for `graph_built_at` serialization.
- Graph worker at `graph_builder.py:254` already writes `graph_built_at` — no write-path changes needed.

### Established Patterns
- Pydantic v2 with defaults: `field_name: Type | None = None` or `field_name: int = 0` — never `Optional[...]`.
- `datetime` fields stored as `datetime` in MongoDB, serialized as ISO string on response (pattern at `documents.py:133-134`).
- `.get()` on dicts when the field might be missing on legacy records (pattern at lines 127-131).

### Integration Points
- **Single edit point in routes:** `_doc_to_response` — updates propagate to 2 endpoints.
- **Single edit point in model:** `Document` class in `models/document.py` — adds one field.
- **Test surface:** `tests/test_documents_graph_*.py` (existing cleanup tests from phase 13) — can either extend or create a sibling file.

### Non-Integration (don't touch)
- Frontend: no consumer yet.
- ARQ workers: already write the fields.
- MongoDB helpers: already return full doc dicts.
- Qdrant: unrelated — graph fields live in MongoDB only.

</code_context>

<specifics>
## Specific Ideas

### Shape of the new DocumentResponse (approximate)
```python
class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    source_type: str
    source_ref: str
    content_type: str
    status: str
    error: str | None = None
    error_type: str | None = None
    error_stage: str | None = None
    file_size_bytes: int = 0
    chunk_count: int
    graph_status: str | None = None       # None | "building" | "complete" | "failed"
    entity_count: int = 0
    relationship_count: int = 0
    graph_built_at: str | None = None     # ISO 8601, None until worker completes
    version: int
    created_at: str
    updated_at: str
```

### Shape of updated _doc_to_response (approximate)
```python
def _doc_to_response(doc: dict) -> DocumentResponse:
    return DocumentResponse(
        # ... existing fields unchanged ...
        chunk_count=doc.get("chunk_count", 0),
        graph_status=doc.get("graph_status"),
        entity_count=doc.get("entity_count", 0),
        relationship_count=doc.get("relationship_count", 0),
        graph_built_at=doc["graph_built_at"].isoformat() if doc.get("graph_built_at") else None,
        version=doc.get("version", 1),
        # ... existing trailing fields unchanged ...
    )
```

### Document model addition (approximate)
```python
# At src/docingest/models/document.py line 57, after relationship_count:
graph_built_at: datetime | None = None
```

### Verification criteria (for PLAN.md DoD)
- `grep -n 'graph_status\|entity_count\|relationship_count\|graph_built_at' src/docingest/api/routes/documents.py` returns **at least 8 matches** in DocumentResponse class + `_doc_to_response` (4 each).
- `grep -n 'graph_built_at' src/docingest/models/document.py` returns 1 match.
- `git diff src/docingest/workers/graph_builder.py` shows NO changes.
- `git diff src/docingest/db/mongodb.py` shows NO changes.
- Integration test: upload doc → `GET /v1/documents/{id}` → response includes `graph_status: null, entity_count: 0, relationship_count: 0, graph_built_at: null`.
- Integration test: seed doc with MongoDB graph fields populated → response reflects them.
- Integration test: `GET /v1/documents` list response — first document dict includes all 4 graph fields with expected types.
- Integration test: same as above with `settings.graph_rag_enabled=false` — response shape unchanged (fields present with defaults).

### Windows/shell note
Use Edit/Write tools only (CLAUDE.md convention; Windows-compatible). The API has hot-reload via `uvicorn --reload` in the Docker dev stack, so post-commit verification is a simple reload trigger — no rebuild needed.

</specifics>

<deferred>
## Deferred Ideas

### Out of scope — belongs in Phase 15
- Removing duplicate `ensure_graph_indexes` call (INT-01).
- asyncio deprecation fix in entity_extraction.py (EE-08).
- Removing the worker safety net at `graph_builder.py:119-121` now that phase 13 wires cleanup synchronously — explicitly deferred in phase 13 CONTEXT.

### Out of scope — separate concerns
- Frontend consumption (React dashboard "Graph" column/badge) — separate milestone/phase.
- `community_count` exposure — not in phase 14 REQ-IDs; needs its own decision about whether per-doc community count is even meaningful (communities are tenant-level, not per-doc).
- `graph_error` derived field combining `error_type`/`error_stage` when `graph_status='failed'` — explicitly rejected in Q1.1.
- Pydantic `exclude_none` behavior — explicitly rejected in D-05/D-06.
- OpenAPI examples / response schema documentation — nice-to-have, not a blocker; planner may add short docstrings at discretion.

### Out of scope — backfill/migration
- Migration script for pre-existing documents missing graph fields — NOT NEEDED. Pydantic defaults and `doc.get(..., default)` in `_doc_to_response` handle missing dict keys automatically. Documents created before the graph-worker existed will simply report `graph_status=None, counts=0, graph_built_at=None`.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 14-surface-graph-status-via-document-api*
*Context gathered: 2026-04-16*
