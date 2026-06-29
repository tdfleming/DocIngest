# Phase 17: Document Graph Status - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

**In scope:**
- Surface per-document graph build metadata in the frontend: `graph_status`, `entity_count`, `relationship_count`, `graph_built_at`, and failure info — all already present on `DocumentResponse` since Phase 14.
- **New route `/documents/:id`** hosting a `DocumentDetailPage` with:
  - A graph build section (status, entity count, relationship count, last-built timestamp, error display when failed)
  - Existing conversion metadata (status, error/error_type/error_stage, chunk_count, file_size_bytes, version, created/updated)
- **Document list table** gains a single new combined "Graph" column (badge + compact `E / R` counts, timestamp in tooltip) inserted after the existing Status column.
- **Source cell in list** becomes a link to `/documents/:id`.
- **Live updates:**
  - List: auto-poll while any visible row has `graph_status == "building"`, stop polling when idle.
  - Detail: auto-poll while the doc is in a transitional state (`graph_status == "building"` OR `doc.status ∈ {pending, converting, chunking}`).
- **Graph-enabled detection** via a new tiny backend endpoint `GET /v1/config` returning `{graph_rag_enabled: bool}`, fetched once at app init and stashed in a React context. When `graph_rag_enabled == false`, the list Graph column and the detail page graph section are hidden.
- **Retry action on detail page:** a "Rebuild graph" button that calls a new backend endpoint `POST /v1/documents/{id}/graph/rebuild` (enqueues the `build_graph` ARQ job for that doc, same pattern as existing ingestion/conversion reprocess).
- **Failed state display:** list badge is red with a warning icon and a short-error tooltip; detail page shows a distinct error panel with full message + `error_type` + `error_stage` + last-attempt timestamp, and the rebuild button.
- **Frontend TS type updates:** extend `DocumentResponse` in `frontend/src/api/types.ts` with the already-present-on-backend fields (`graph_status`, `entity_count`, `relationship_count`, `graph_built_at`, plus `error_type`/`error_stage` if still missing).
- **Tests:** unit tests for the new `GraphBadge` logic, integration tests for `DocumentDetailPage` happy/failed paths, and a pytest test for the new `/v1/config` + `POST /v1/documents/{id}/graph/rebuild` endpoints.
- Closes REQ-IDs **DOC-GRAPH-01, DOC-GRAPH-02, DOC-GRAPH-03, DOC-GRAPH-04**.

**Out of scope (explicitly NOT this phase):**
- Entity explorer page (/entities) — Phase 18.
- Community browser — Phase 19.
- Graph-aware search — Phase 20.
- Interactive/visual graph rendering (node-link, force-directed) — deferred to v1.2+.
- Consolidating/replacing the existing `MarkdownPreviewModal` — the modal stays; detail page is purely additive. Modal-vs-page cleanup is a future tech-debt task.
- Exposing any tenant/admin flag to toggle `graph_rag_enabled` at runtime — requires server restart today, explicitly deferred in REQUIREMENTS.md.
- Sort by graph columns in the list — Claude's discretion (can be added if trivial with existing `sort` query param pattern, else deferred).
- Inline graph rebuild from the list (row action) — rebuild is detail-page-only to keep the list compact.
- A separate feature-flags dashboard — `GET /v1/config` is intentionally minimal (one boolean).

</domain>

<decisions>
## Implementation Decisions

### Detail surface (locked)
- **D-01:** Create a new route `/documents/:id` via `react-router-dom` v6 — add a `DocumentDetailPage` component at `frontend/src/pages/DocumentDetailPage.tsx`.
- **D-02:** Entry point from the list: make the `source_ref` cell in `DocumentRow.tsx` a `react-router-dom` `Link` to `/documents/${doc.id}`. Do NOT add an extra icon in the Actions column (keep row compact).
- **D-03:** Detail page scope: graph build section + existing conversion metadata (status, error, error_type, error_stage, chunk_count, file_size_bytes, version, created_at, updated_at). Skip markdown preview on the detail page for this phase — the `MarkdownPreviewModal` continues to be reachable from the list row's "View Markdown" icon.
- **D-04:** `MarkdownPreviewModal` is left unchanged. Consolidating the modal into the detail page is a deferred cleanup (noted in `<deferred>`).
- **D-05:** Detail page uses `useDocument(docId)` — a new TanStack Query hook calling existing `GET /v1/documents/{id}` (already implemented on backend). Add it to `frontend/src/hooks/useDocuments.ts` or a new `frontend/src/hooks/useDocument.ts` (planner's call).

### Graph-enabled detection (locked)
- **D-06:** Add a new backend endpoint: `GET /v1/config` returning `{"graph_rag_enabled": settings.graph_rag_enabled}`. Unauthenticated (public) — exposes no secrets. Lives in a new route module `src/docingest/api/routes/config.py` mounted under `/v1` in `api/app.py`.
- **D-07:** Response shape stays minimal for v1.1 — exactly one field: `graph_rag_enabled: bool`. Versioning/other flags are deferred.
- **D-08:** Frontend: fetch once via TanStack Query with `staleTime: Infinity` — `useQuery({ queryKey: ["config"], queryFn: getConfig, staleTime: Infinity })`. Consumed via a thin custom hook `useAppConfig()` that returns `{graphRagEnabled}`. No React context wrapper needed — TanStack Query acts as the cache.
- **D-09:** When `graphRagEnabled === false` → hide in list: the entire new `Graph` column (both `<Th>` and the `<Td>`). Hide in detail: the entire graph build section and the Rebuild button.
- **D-10:** No fallback banner on the detail page when graph is disabled — silent hide (users don't need to know graph is a feature if their deployment doesn't have it).

### List table layout (locked)
- **D-11:** One combined `Graph` column in `DocumentTable.tsx`. Content: `<GraphBadge status={doc.graph_status} /> <Text fontSize="xs">{doc.entity_count}E / {doc.relationship_count}R</Text>`.
- **D-12:** Column order becomes: `Source | Type | Status | Graph | Size | Chunks | Version | Created | Actions` (9 columns total). `Graph` inserted after existing `Status`.
- **D-13:** Badge color+label mapping (in a new `frontend/src/components/documents/GraphBadge.tsx`):
  - `null` → label `"pending"`, Chakra `colorScheme="gray"`, variant `"subtle"`
  - `"building"` → label `"building"`, Chakra `colorScheme="blue"`
  - `"complete"` → label `"built"`, Chakra `colorScheme="green"`
  - `"failed"` → label `"failed"`, Chakra `colorScheme="red"` + a small `FiAlertCircle` (react-icons/fi) icon beside the badge text
- **D-14:** `graph_built_at` timestamp is NOT a dedicated column; it appears in a Chakra `Tooltip` wrapping the list badge: `"Built: 2h ago"` (relative) — use existing patterns from the ingestion row (`new Date(...).toLocaleString()` if no relative-time helper exists, else prefer relative). If `null`, no timestamp in tooltip.
- **D-15:** Counts in the list are shown as plain integers (`12E / 34R`); no locale thousands separator for v1.1. Formatting nicety is Claude's Discretion if it turns out to matter (e.g., add `toLocaleString()` if counts commonly exceed 9999).
- **D-16:** Column is not sortable this phase. Leave default sort behavior on `created_at` as-is. Sort by graph status / counts is a deferred idea.

### Detail page graph section (locked)
- **D-17:** New component `frontend/src/components/documents/GraphBuildSection.tsx`. Layout: Chakra `Card` with header "Graph Build" and body grid (2 columns) showing:
  - Status (reuse `<GraphBadge />` at `size="md"`)
  - Entities (`entity_count`)
  - Relationships (`relationship_count`)
  - Last built (`graph_built_at` → full ISO + relative; `—` if null)
- **D-18:** When `graph_status === "failed"`: render an additional Chakra `Alert status="error"` immediately below the grid, containing the error summary: `error` field (or a generic "Graph build failed" fallback), `error_type`, and `error_stage`. Include the attempt timestamp from `graph_built_at` even for failures.
- **D-19:** A "Rebuild graph" `Button` sits in the Card footer. Disabled while:
  - `graph_status === "building"` (already in progress)
  - The rebuild mutation is in-flight
  - `doc.status !== "complete"` (chunks must exist before graph can be built)
  Button click fires `POST /v1/documents/{id}/graph/rebuild`, shows a Chakra toast on success (`"Graph rebuild started"`) and on error. `useMutation` + `queryClient.invalidateQueries({queryKey: ["document", docId]})` on success.
- **D-20:** The graph section (heading, body, error alert, rebuild button) renders only when `useAppConfig().graphRagEnabled === true`.

### Backend rebuild endpoint (locked, in scope)
- **D-21:** New endpoint: `POST /v1/documents/{document_id}/graph/rebuild` in `src/docingest/api/routes/documents.py`. Uses the existing `Tenant` dependency for auth + rate limit.
- **D-22:** Gating: same `if not settings.graph_rag_enabled: raise HTTPException(403, "Graph RAG is not enabled")` pattern used elsewhere.
- **D-23:** Precondition checks:
  - Document exists + belongs to tenant (return 404 if not)
  - `doc["status"] == "complete"` (return 409 Conflict `"Document not ready for graph build"` otherwise)
  - `doc["graph_status"] != "building"` (return 409 Conflict `"Graph build already in progress"` otherwise, to avoid duplicate jobs)
- **D-24:** Action: enqueue the existing `build_graph` ARQ job via the Redis pool onto queue `arq:queue:graph`, passing `doc_id`, `tenant_id`, `trace_id`. Before enqueueing, set the doc's `graph_status` to `"building"` and clear prior `graph_error`-ish fields in MongoDB — mirroring what the worker itself does at start-up, but setting it here avoids a UI flash of "failed" while the worker starts.
- **D-25:** Response shape: `{"id": document_id, "graph_status": "building"}` (status code 202 Accepted).
- **D-26:** Structured logging: `log.info("document_graph_rebuild_requested", doc_id=..., tenant_id=..., trace_id=...)`.
- **D-27:** New tests in an existing or new pytest file (planner's call — `tests/test_documents_graph_rebuild.py` preferred): 200/404/409/403 coverage plus a test that verifies a job is enqueued on queue `arq:queue:graph`.

### Config endpoint (locked, in scope)
- **D-28:** New file `src/docingest/api/routes/config.py` with a single route `GET /v1/config` returning `AppConfigResponse(graph_rag_enabled=settings.graph_rag_enabled)`. No auth (public). Mount in `src/docingest/api/app.py` next to other `/v1/*` routers with `tags=["config"]`.
- **D-29:** New Pydantic model inline in the same file: `class AppConfigResponse(BaseModel): graph_rag_enabled: bool`.
- **D-30:** New pytest in `tests/test_config_endpoint.py` covering: endpoint returns 200, response matches `{"graph_rag_enabled": <flag value>}`, works without an API key.

### Polling (locked)
- **D-31:** List polling: modify `useDocuments` so that `refetchInterval` returns `3000` when any returned document has `graph_status === "building"`, else `false`. TanStack Query supports this pattern via a function form of `refetchInterval`.
- **D-32:** Detail polling: `useDocument(id)` uses `refetchInterval` function form, polling every `3000` ms while `doc.graph_status === "building"` OR `doc.status ∈ {"pending", "converting", "chunking"}`, else `false`.
- **D-33:** Do NOT reduce or change the global `refetchOnWindowFocus: false` default — polling is additive.

### Frontend type updates (locked)
- **D-34:** Update `frontend/src/api/types.ts` — extend `DocumentResponse` interface with: `graph_status: "building" | "complete" | "failed" | null;  entity_count: number;  relationship_count: number;  graph_built_at: string | null;  error_type: string | null;  error_stage: string | null;`. Add a discriminated `GraphStatus` type alias for the four values.
- **D-35:** Add `AppConfig` type: `export interface AppConfig { graph_rag_enabled: boolean; }`.
- **D-36:** Add `RebuildGraphResponse` type: `export interface RebuildGraphResponse { id: string; graph_status: "building"; }`.

### API client additions (locked)
- **D-37:** Add to `frontend/src/api/documents.ts`: `export const getDocument = (id: string) => client.get<DocumentResponse>(`/v1/documents/${id}`).then(r => r.data)` and `export const rebuildGraph = (id: string) => client.post<RebuildGraphResponse>(`/v1/documents/${id}/graph/rebuild`).then(r => r.data)`.
- **D-38:** New module `frontend/src/api/config.ts`: `export const getConfig = () => client.get<AppConfig>("/v1/config").then(r => r.data)`.

### Routing (locked)
- **D-39:** `frontend/src/App.tsx` (or wherever routes are declared) gains `<Route path="/documents/:id" element={<DocumentDetailPage />} />`. Lazy-loading is Claude's Discretion; the rest of the app does not lazy-load so inline import is fine.

### Testing (locked)
- **D-40:** Backend pytest coverage (MUST pass):
  - `tests/test_config_endpoint.py` — new, ≥ 2 cases.
  - `tests/test_documents_graph_rebuild.py` (or existing file) — new, ≥ 5 cases (200 Accepted, 404 missing, 404 cross-tenant, 409 not-ready, 409 already-building, 403 gated-off).
- **D-41:** Frontend tests: `GraphBadge` unit tests for each of the 4 status states, and a `DocumentDetailPage` integration test that mocks `getDocument` + `rebuildGraph` and verifies the rebuild button disables-while-building (Vitest + @testing-library/react, whichever is already installed). If neither is installed, the test scaffolding itself can be deferred — but at minimum `npm run build` MUST pass (TypeScript strict check).
- **D-42:** A manual smoke test step is listed in the plan's `must_haves`: with a real running stack, toggle `GRAPH_RAG_ENABLED` and verify list/detail hide graph UI; with the flag on, rebuild a doc and watch the badge transition `failed/pending → building → built` via auto-polling.

### Claude's Discretion
- Exact relative-time helper (build one vs. `date-fns` install) — if `date-fns` or similar not already in `package.json`, a tiny inline helper is fine.
- Exact structure of `DocumentDetailPage` (single file vs. split into section components beyond `GraphBuildSection.tsx`).
- Whether to add a breadcrumb on the detail page (`Documents > {source_ref}`).
- Whether to show the raw `doc.id` anywhere on the detail page (useful for debugging; not required).
- Loading skeleton vs. spinner on the detail page (existing pattern uses Spinner; stick with it unless a skeleton is trivially small).
- Whether list-column sort-by-graph-status is added this phase. If trivial with existing `sort` query param wiring, go for it; otherwise defer.
- Whether `useDocuments` refactor bumps to a separate hook or adds an overload. Keep it minimal.
- Exact copy for error Alert body text (but `error_type` and `error_stage` must be included).
- Toast wording beyond "Graph rebuild started" / "Graph rebuild failed".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §DOC-GRAPH-01..04 (lines 27-30) — the 4 REQ-IDs this phase closes.
- `.planning/REQUIREMENTS.md` §"Out of Scope (v1.1)" (lines 62-70) — admin toggle for `GRAPH_RAG_ENABLED` is deferred; do not add UI to flip it.
- `.planning/ROADMAP.md` §Phase 17 (lines 79-89) — phase goal + success criteria.

### Source of truth — files to edit (backend)
- `src/docingest/api/routes/documents.py` — add `POST /v1/documents/{id}/graph/rebuild`. Current Pydantic `DocumentResponse` already has the graph fields from Phase 14 (line 81-99).
- `src/docingest/api/routes/config.py` — NEW file for `GET /v1/config`.
- `src/docingest/api/app.py` — mount the new config router.

### Source of truth — files to edit (frontend)
- `frontend/src/api/types.ts` — extend `DocumentResponse`, add `AppConfig`, add `GraphStatus`, add `RebuildGraphResponse`.
- `frontend/src/api/documents.ts` — add `getDocument(id)` and `rebuildGraph(id)`.
- `frontend/src/api/config.ts` — NEW file with `getConfig()`.
- `frontend/src/components/documents/DocumentTable.tsx` — add/guard the Graph column (8 → 9 columns), inserted after Status.
- `frontend/src/components/documents/DocumentRow.tsx` — render the new Graph cell, make source_ref a Link, hide cell when config says disabled.
- `frontend/src/components/documents/GraphBadge.tsx` — NEW component for the 4-state badge + optional alert icon for `failed`.
- `frontend/src/components/documents/GraphBuildSection.tsx` — NEW component for the detail page graph card + rebuild action.
- `frontend/src/pages/DocumentDetailPage.tsx` — NEW page at `/documents/:id`.
- `frontend/src/hooks/useDocuments.ts` — extend with `refetchInterval` polling; add or split out `useDocument(id)` with similar polling.
- `frontend/src/hooks/useAppConfig.ts` — NEW hook wrapping `useQuery({queryKey:["config"], queryFn: getConfig, staleTime: Infinity})`.
- `frontend/src/App.tsx` (or equivalent router file) — add `/documents/:id` route.

### Source of truth — files to READ but NOT modify
- `src/docingest/models/document.py` lines 40-64 — ground truth for `Document` model incl. graph fields (graph_status, entity_count, relationship_count, graph_built_at).
- `src/docingest/workers/graph_builder.py` — understand what "building"/"complete"/"failed" transitions look like; the rebuild endpoint enqueues the same `build_graph` job this worker consumes.
- `src/docingest/db/redis.py` — `get_redis_pool()` + `enqueue_job` pattern for the rebuild endpoint.
- `src/docingest/api/routes/documents.py` lines 112-141 (`_enqueue_conversion`, `_doc_to_response`) — reference patterns for enqueue helpers and dict→response mapping.
- `frontend/src/components/documents/StatusBadge.tsx` — existing badge component; `GraphBadge` mirrors its shape.
- `frontend/src/components/documents/DocumentRow.tsx` (current state) — reference for cell conventions (`Td`, `Tooltip`, `IconButton`, `className="text-xs"`).

### Reference patterns
- Reprocess pattern in `DocumentTable.tsx` (`useMutation` + `onSuccess` toast + `queryClient.invalidateQueries`) is the blueprint for the rebuild mutation.
- Existing API-key gating pattern via `useApiKey` → `isSet` check (see `DocumentsPage.tsx`) — apply the same gate on the detail page.
- Existing Tanstack Query `useDocuments` hook is the blueprint for `useDocument(id)`.

### Prior phase context
- `.planning/phases/16-graph-frontend-apis/16-CONTEXT.md` — sibling phase, establishes Pydantic v2 response conventions, gating block, `Tenant` dependency, and response-model-inline-in-route-file convention.
- `.planning/phases/14-surface-graph-status-via-document-api/` (no context file, but `src/docingest/api/routes/documents.py` lines 81-141 are the output) — Phase 14 added the graph fields; this phase consumes them.

### Project conventions
- `CLAUDE.md` — structlog not print; async throughout; Pydantic v2 populate_by_name; settings.graph_rag_enabled gating; Edit/Write tools only (no sed/awk/heredoc on Windows); pytest asyncio_mode="auto"; Chakra UI v2 + Emotion; TanStack Query v5; React Router v6; Vite strict TS --noEmit on build.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StatusBadge.tsx` — Chakra `Badge colorScheme variant="subtle"` pattern. `GraphBadge` is a near-clone with a different status→color map and an optional icon.
- `useDocuments` TanStack Query hook — extend with refetchInterval; add sibling `useDocument(id)`.
- `MarkdownPreviewModal` — remains untouched.
- Reprocess mutation pattern in `DocumentTable.tsx` — copy for the rebuild mutation on the detail page.
- Existing Redis pool + ARQ `enqueue_job` flow (`documents.py::_enqueue_conversion`) — copy for rebuild enqueue.
- `Tenant` dependency + rate limiter — inherited for the new rebuild endpoint.
- `settings.graph_rag_enabled` — already wired in `config.py`; referenced in `workers/graph_builder.py` and `api/routes/graph.py`.

### Established Patterns
- **Backend:** FastAPI routers under `/v1/`, tag-grouped, gated via `settings.graph_rag_enabled`. Pydantic v2 with `populate_by_name=True`. ISO-string datetime in responses.
- **Frontend:** Chakra UI compact `Table size="sm"`. TanStack Query v5 with `refetchOnWindowFocus: false` globally. Mutations use `useMutation` + `queryClient.invalidateQueries` + toast.
- **Routing:** React Router v6 single-file route table (check current wiring in App.tsx / main.tsx); add `/documents/:id` alongside existing `/documents`.
- **Auth on frontend:** `useApiKey` context gates all data pages — reuse on detail page.

### Integration Points
- `src/docingest/api/app.py` — add `config` router alongside existing mounts under `/v1`.
- `src/docingest/api/routes/documents.py` — add new rebuild route in the existing `documents` router (prefix `/documents`).
- `frontend/src/App.tsx` (or router file) — add `/documents/:id` route.
- `frontend/src/api/types.ts` — extend existing `DocumentResponse`; add new types.
- `frontend/src/components/documents/DocumentTable.tsx` + `DocumentRow.tsx` — modify for new column and source-ref link.

### Non-Integration (don't touch)
- `src/docingest/workers/graph_builder.py` — worker stays unchanged; rebuild endpoint simply enqueues the existing `build_graph` job.
- `src/docingest/services/community_detection.py` — unrelated to per-document graph status.
- `src/docingest/api/routes/search.py` — untouched.
- `src/docingest/api/routes/graph.py` — phase 16 owns this; phase 17 does not modify.
- Existing conversion / chunking pipeline behavior — unchanged.

</code_context>

<specifics>
## Specific Ideas

### Proposed GraphBadge shape (planner may polish)

```tsx
// frontend/src/components/documents/GraphBadge.tsx
import { Badge, HStack, Icon } from "@chakra-ui/react";
import { FiAlertCircle } from "react-icons/fi";

export type GraphStatus = "building" | "complete" | "failed" | null;

const MAP: Record<string, { label: string; colorScheme: string }> = {
  "null": { label: "pending", colorScheme: "gray" },
  building: { label: "building", colorScheme: "blue" },
  complete: { label: "built", colorScheme: "green" },
  failed: { label: "failed", colorScheme: "red" },
};

export default function GraphBadge({ status }: { status: GraphStatus }) {
  const key = status === null ? "null" : status;
  const { label, colorScheme } = MAP[key];
  return (
    <HStack spacing={1}>
      <Badge colorScheme={colorScheme} variant="subtle">{label}</Badge>
      {status === "failed" && <Icon as={FiAlertCircle} color="red.500" boxSize={3} />}
    </HStack>
  );
}
```

### Proposed rebuild endpoint shape

```python
# src/docingest/api/routes/documents.py (addition)

class RebuildGraphResponse(BaseModel):
    id: str
    graph_status: str  # always "building" when 202

@router.post("/{document_id}/graph/rebuild", status_code=202)
async def rebuild_document_graph(
    document_id: str,
    tenant: Tenant,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> RebuildGraphResponse:
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")

    doc = await get_document_by_id(db, document_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["status"] != "complete":
        raise HTTPException(status_code=409, detail="Document not ready for graph build")
    if doc.get("graph_status") == "building":
        raise HTTPException(status_code=409, detail="Graph build already in progress")

    # Flip to 'building' before enqueue — prevents duplicate-click double jobs.
    await db.documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"graph_status": "building", "updated_at": datetime.now(UTC)}},
    )

    pool = await get_redis_pool()
    trace_id = str(uuid4())
    await pool.enqueue_job(
        "build_graph",
        doc_id=document_id,
        tenant_id=tenant["tenant_id"],
        trace_id=trace_id,
        _queue_name="arq:queue:graph",
    )
    log.info("document_graph_rebuild_requested",
             doc_id=document_id, tenant_id=tenant["tenant_id"], trace_id=trace_id)
    return RebuildGraphResponse(id=document_id, graph_status="building")
```

### Proposed config endpoint shape

```python
# src/docingest/api/routes/config.py (new file)
from fastapi import APIRouter
from pydantic import BaseModel
from docingest.config import settings

router = APIRouter(tags=["config"])

class AppConfigResponse(BaseModel):
    graph_rag_enabled: bool

@router.get("/config")
async def get_app_config() -> AppConfigResponse:
    return AppConfigResponse(graph_rag_enabled=settings.graph_rag_enabled)
```

Mount in `api/app.py`: `app.include_router(config.router, prefix="/v1")`.

### TanStack Query polling pattern

```tsx
// useDocuments.ts (extension)
export function useDocuments(params: DocumentListParams) {
  return useQuery({
    queryKey: ["documents", params],
    queryFn: () => listDocuments(params),
    refetchInterval: (data) =>
      data?.documents?.some(d => d.graph_status === "building") ? 3000 : false,
  });
}

// useDocument.ts (new)
export function useDocument(id: string | undefined) {
  return useQuery({
    enabled: !!id,
    queryKey: ["document", id],
    queryFn: () => getDocument(id!),
    refetchInterval: (data) => {
      if (!data) return false;
      const transitional =
        data.graph_status === "building" ||
        ["pending", "converting", "chunking"].includes(data.status);
      return transitional ? 3000 : false;
    },
  });
}
```

### Grep-able acceptance criteria for PLAN.md DoD
- `grep -n "def rebuild_document_graph" src/docingest/api/routes/documents.py` returns 1 match.
- `test -f src/docingest/api/routes/config.py` passes.
- `grep -n "class AppConfigResponse" src/docingest/api/routes/config.py` returns 1 match.
- `grep -n "config.router" src/docingest/api/app.py` returns ≥ 1 match.
- `test -f frontend/src/components/documents/GraphBadge.tsx` passes.
- `test -f frontend/src/components/documents/GraphBuildSection.tsx` passes.
- `test -f frontend/src/pages/DocumentDetailPage.tsx` passes.
- `test -f frontend/src/hooks/useAppConfig.ts` passes.
- `test -f frontend/src/api/config.ts` passes.
- `grep -n "graph_status\|entity_count\|relationship_count\|graph_built_at" frontend/src/api/types.ts` returns ≥ 4 matches.
- `grep -n "/documents/:id\|documents/:id" frontend/src/App.tsx` returns ≥ 1 match (path exists — may be in a routes array).
- `pytest tests/test_config_endpoint.py tests/test_documents_graph_rebuild.py` exits 0.
- `ruff check src/` passes.
- `cd frontend && npm run build` exits 0 (TypeScript strict check + Vite build).
- Full existing pytest suite stays green (no regressions).

### Windows/shell note
All frontend+backend edits via `Edit` / `Write` tools (no sed/awk/heredoc). API hot-reloads under `uvicorn --reload` in Docker. Vite HMR picks up frontend changes without restart.

</specifics>

<deferred>
## Deferred Ideas

### Future phases within v1.1
- **Phase 18 (Entity Explorer)** — the `/entities` list page; uses Phase 16 endpoints.
- **Phase 19 (Community Browser)** — `/communities` page.
- **Phase 20 (Graph-Aware Search)** — extends `/search` page.

### Post-v1.1
- Consolidate `MarkdownPreviewModal` into `DocumentDetailPage` as a tab. Explicit cleanup task — modal + detail page coexist in v1.1.
- Interactive graph visualization (force-directed node-link). Out-of-scope per REQUIREMENTS.md.
- Runtime toggle for `GRAPH_RAG_ENABLED` (admin UI). Explicitly out-of-scope per REQUIREMENTS.md.
- Sort list by graph status / entity count / relationship count — if the existing `sort` wiring isn't trivial to extend, defer.
- Relative-time library (`date-fns` or similar) for consistent tooltips across the app.
- Row-level "Rebuild graph" action in the list. Currently only on the detail page to keep the list compact.
- Retry policy for failed graph builds with exponential backoff from the UI. Worker already retries; a manual rebuild is the escape hatch for v1.1.
- Feature-flag dashboard / expanded `/v1/config` with version + build info. Keep minimal for v1.1.
- Accessibility enhancements beyond color+text+icon on the badge (e.g., status-announce via aria-live) — not explicit v1.1 requirement but worth auditing post-ship.

### Rejected / locked out of this phase
- Replacing `MarkdownPreviewModal` this phase — rejected (D-04).
- Dedicated `graph_built_at` column in list — rejected (timestamp goes into tooltip, D-14).
- Three separate columns for graph status + entities + relationships — rejected in favor of one combined cell (D-11).
- Inline error panel on every failed row in list — rejected in favor of icon+tooltip in list, full panel in detail (D-18).
- Sort-by-graph-status this phase — deferred unless trivially cheap.
- Banner on detail page when graph disabled — rejected (silent hide, D-10).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 17-document-graph-status*
*Context gathered: 2026-04-17*
