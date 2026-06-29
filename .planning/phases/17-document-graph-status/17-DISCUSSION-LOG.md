# Phase 17: Document Graph Status - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 17-document-graph-status
**Areas discussed:** Detail surface, Graph-disabled detection, List columns + badges, Polling + failed state

---

## Gray-area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Detail surface | No document detail page today. Where does the 'graph build section' live? | ✓ |
| Graph-disabled detection | How does the UI know GRAPH_RAG_ENABLED=false on backend? | ✓ |
| List columns + badges | 8 existing columns + 3 new = 11. Layout + badge mapping. | ✓ |
| Polling and failed state | Auto-poll while building? Error display? Retry in scope? | ✓ |

**User's choice:** All four areas.

---

## Detail Surface

### Q1: Where should the document detail view live?

| Option | Description | Selected |
|--------|-------------|----------|
| New route /documents/:id | Standalone DocumentDetailPage; shareable URL. Adds a router entry. | ✓ |
| Extend MarkdownPreviewModal | Add a 'Graph' tab to the existing modal. No routing changes. | |
| Expandable row | Click row to expand inline. Smallest scope, most clutter. | |

**User's choice:** New route /documents/:id
**Notes:** Recommended option; avoids modal cramping, enables shareable URLs.

### Q2: What info does the detail surface show beyond the graph section?

| Option | Description | Selected |
|--------|-------------|----------|
| Graph build section only | Minimal — just DOC-GRAPH-03 fields. | |
| Plus existing conversion metadata | Also status, errors, chunks, size, version, timestamps. | ✓ |
| Plus markdown preview | Integrate existing modal content into the page. | |

**User's choice:** Plus existing conversion metadata
**Notes:** Users landing on the detail page via link need conversion context too; markdown preview stays in the modal.

### Q3: How do users reach the detail surface from the list?

| Option | Description | Selected |
|--------|-------------|----------|
| Click source_ref | Link the 'Source' cell to /documents/:id. | ✓ |
| New 'View details' icon in Actions | Add an info icon in the actions column. | |
| Both | Link + icon for max discoverability. | |

**User's choice:** Click source_ref

### Q4: Does THIS phase include MarkdownPreviewModal consolidation?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep modal, add new detail page | Additive; modal continues to work. | ✓ |
| Replace modal with detail page | Clean long-term architecture; more churn now. | |
| N/A | If Q1 was 'Extend modal'. | |

**User's choice:** Keep modal, add new detail page
**Notes:** Consolidation is a deferred tech-debt task.

---

## Graph-Disabled Detection

### Q1: How should the frontend detect graph-enabled?

| Option | Description | Selected |
|--------|-------------|----------|
| New /v1/config endpoint | Tiny backend endpoint; deterministic, cheap, future-proof. | ✓ |
| Probe /v1/graph/* for 403 | Pure-frontend detection via 403 response. | |
| Client-side heuristic (all rows null) | Ambiguous; false-hides when list happens to have no graph-built docs. | |
| Manual toggle in settings | User-controlled frontend toggle. | |

**User's choice:** New /v1/config endpoint
**Notes:** Adds a small backend endpoint to this phase despite roadmap saying "depends on nothing backend-wise". Captured as D-06.

### Q2: What does /v1/config return beyond graph_rag_enabled?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — only graph_rag_enabled | One boolean. | ✓ |
| Include version + feature flags | Broader 'app info' shape. | |
| N/A | If non-endpoint detection chosen. | |

**User's choice:** Minimal — only graph_rag_enabled

### Q3: When graph is disabled, what gets hidden?

| Option | Description | Selected |
|--------|-------------|----------|
| Hide list columns + detail section | Omit graph column from table; omit graph section from detail. | ✓ |
| Show columns with '—' values | Keep layout consistent; dash for all graph cells. | |
| Hide + show banner on detail | Plus a 'Graph extraction is not enabled' info banner. | |

**User's choice:** Hide list columns + detail section
**Notes:** Silent hide. Users don't need to know graph is a feature if it isn't enabled on their deployment.

### Q4: Where in the fetch lifecycle should we check graph-enabled?

| Option | Description | Selected |
|--------|-------------|----------|
| Once at app init, React context | Fetch on mount, stash in context. | ✓ |
| TanStack Query with infinite staleTime | useQuery with staleTime: Infinity. | |
| Fetch per-component | Each component calls the hook directly. | |

**User's choice:** Once at app init, React context
**Notes:** Captured in CONTEXT.md as TanStack Query with staleTime: Infinity + thin custom hook (D-08) — the effect is the same as a React context without the provider boilerplate.

---

## List Columns + Badges

### Q1: How should the three new graph fields fit in the list table?

| Option | Description | Selected |
|--------|-------------|----------|
| One combined 'Graph' cell | Badge + tiny E/R count; tooltip for timestamp. | ✓ |
| Two columns: badge + E/R counts | Badge in one cell, counts in another. | |
| Three separate columns | Most readable, widest. 11 cols total. | |

**User's choice:** One combined 'Graph' cell
**Notes:** Keeps table from blowing past 9 columns.

### Q2: Badge wording + Chakra colorScheme for graph_status?

| Option | Description | Selected |
|--------|-------------|----------|
| built / building / failed / pending | null → pending gray, building → blue, complete → built green, failed → red. | ✓ |
| done / building / failed / n/a | 'n/a' for null, 'done' for complete. | |
| Match existing StatusBadge naming | Literal 'complete' green, 'building' blue, 'failed' red, 'pending' yellow. | |

**User's choice:** built / building / failed / pending

### Q3: Where does the new graph column sit?

| Option | Description | Selected |
|--------|-------------|----------|
| After Status, before Size | Groups status-like columns. | ✓ |
| After Chunks, before Version | Groups pipeline-output columns. | |
| At the end, before Actions | Minimal reshuffling. | |

**User's choice:** After Status, before Size

### Q4: Where does graph_built_at timestamp render?

| Option | Description | Selected |
|--------|-------------|----------|
| Tooltip on the badge | Hover for relative time. | ✓ |
| Dedicated column next to Graph | Most visible, widest. | |
| Detail page only | Cleanest list, least info. | |

**User's choice:** Tooltip on the badge

---

## Polling and Failed State

### Q1: Auto-poll the list while graph_status='building'?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, poll while building | refetchInterval 3-5s when any row is building; stop when idle. | ✓ |
| No polling, manual refresh | Static until user refreshes. | |
| Poll only on detail page | List static; detail polls. | |

**User's choice:** Yes, poll while building

### Q2: When graph_status='failed', what error info and where?

| Option | Description | Selected |
|--------|-------------|----------|
| Icon tooltip in list, full in detail | Red badge + warn icon + short tooltip; full error on detail page. | ✓ |
| Badge only in list, detail on detail | Just the red badge; no tooltip. | |
| Inline error text in both | Max visibility; list gets cluttered. | |

**User's choice:** Icon tooltip in list, full in detail

### Q3: Is retry/rebuild of a failed graph build part of THIS phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Out of scope for Phase 17 | Read-only display; retry is later. | |
| Include a retry button in detail page | New POST endpoint + button. Adds mutation scope. | ✓ |
| Reuse existing reprocess action | Point users at the full pipeline reprocess icon. | |

**User's choice:** Include a retry button in detail page
**Notes:** Expands phase scope: adds backend `POST /v1/documents/{id}/graph/rebuild` endpoint, tests, and a rebuild mutation + button on the detail page. Captured as D-19..D-27.

### Q4: Does the detail page need live elements beyond graph status?

| Option | Description | Selected |
|--------|-------------|----------|
| No, static snapshot | Fetch once on navigate. | |
| Poll while any status is transitional | graph_status='building' OR status ∈ {pending, converting, chunking}. | ✓ |
| Manual refresh button | User-controlled refresh. | |

**User's choice:** Poll while any status is transitional
**Notes:** Covers both pipeline and graph-build transitions; polling stops when idle.

---

## Claude's Discretion

- Exact relative-time helper (inline vs. date-fns install).
- Exact structure of DocumentDetailPage (single file vs. split sections).
- Breadcrumb on detail page.
- Showing raw doc.id on detail page.
- Loading skeleton vs. Spinner.
- Whether list-column sort-by-graph-status is added this phase (if trivial).
- useDocuments refactor shape (overload vs. sibling hook).
- Exact Alert copy (must include error_type + error_stage).
- Toast wording.

## Deferred Ideas

- MarkdownPreviewModal → DocumentDetailPage consolidation.
- Interactive graph visualization (force-directed).
- Runtime `GRAPH_RAG_ENABLED` admin toggle.
- Sort by graph columns in the list.
- date-fns or similar library install.
- Row-level "Rebuild graph" action.
- Exponential backoff retry policy.
- Feature-flag dashboard.
- Accessibility enhancements beyond color+text+icon.
