# Roadmap: DocIngest

**Current milestone:** v1.1 Graph Frontend
**Last updated:** 2026-04-17

---

## Milestones

- ✅ **v1.0 MVP** — Phases 1-7 (shipped 2026-03-04)
- ✅ **v1.0.1 Graph RAG Extension** — Phases 8-15 (shipped 2026-04-17)
- 🚧 **v1.1 Graph Frontend** — Phases 16-20

---

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-7) — SHIPPED 2026-03-04</summary>

- [x] Phase 01: Foundation & Infrastructure (1/1 plans)
- [x] Phase 02: Document Parsing (1/1 plans)
- [x] Phase 03: Chunking & Embedding (1/1 plans)
- [x] Phase 04: Search & Document Management (1/1 plans)
- [x] Phase 05: Auth & Multi-Tenancy (1/1 plans)
- [x] Phase 06: Reliability & Observability (2/2 plans)
- [x] Phase 07: Tech Debt Cleanup (1/1 plans)

Full detail: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.0.1 Graph RAG Extension (Phases 8-15) — SHIPPED 2026-04-17</summary>

**Build phases (feature):**
- [x] Phase 08: Graph Data Models (2/2 plans)
- [x] Phase 09: Entity Extraction (1/1 plans)
- [x] Phase 10: Graph Builder Worker (1/1 plans)
- [x] Phase 11: Community Detection (2/2 plans)

**Gap closure phases (audit-driven):**
- [x] Phase 12: Restore Graph RAG Traceability (4/4 plans) — REQUIREMENTS/PROJECT/MILESTONES/SUMMARY docs
- [x] Phase 13: Wire Graph Data Lifecycle Cleanup (1/1 plans) — closed FLOW-04/FLOW-06
- [x] Phase 14: Surface Graph Status via Document API (1/1 plans) — closed INT-02
- [x] Phase 15: Graph RAG Code Quality & Hardening (1/1 plans) — closed INT-01, EE-08, COMM-01..04

Full detail: [milestones/v1.0.1-ROADMAP.md](milestones/v1.0.1-ROADMAP.md)

</details>

### v1.1 Graph Frontend (Phases 16-20)

- [ ] **Phase 16: Graph Frontend APIs** - New backend endpoints for entity list/filter/search/detail, community list/detail, and graph-aware search
- [ ] **Phase 17: Document Graph Status** - Surface per-document graph build metadata (status badge, entity/relationship counts, last-built timestamp) in document list and detail views
- [ ] **Phase 18: Entity Explorer** - New /entities page with paginated table, type filter, name search, and entity detail panel
- [ ] **Phase 19: Community Browser** - New /communities page with hierarchical view, community detail panel, and rebuild action
- [ ] **Phase 20: Graph-Aware Search** - Extend search page with community context toggle that surfaces top matching communities above chunk results

---

## Phase Details

### Phase 16: Graph Frontend APIs
**Goal**: Backend exposes the query endpoints the frontend graph UI needs — entity list/filter/search/detail, community list/detail, and community-aware search — so frontend phases 17-20 can be built against live APIs
**Depends on**: Phase 15 (graph data in MongoDB from v1.0.1)
**Requirements**: ENT-05, COMM-UI-05, SEARCH-G-03
**Success Criteria** (what must be TRUE):
  1. `GET /v1/graph/entities` returns a paginated list filterable by entity_type and searchable by name (substring)
  2. `GET /v1/graph/entities/{id}` returns entity detail including linked document IDs
  3. `GET /v1/graph/communities` returns a paginated list of communities with resolution_level, entity_count, and summary
  4. `GET /v1/graph/communities/{id}` returns community detail with full summary and member entity list
  5. `POST /v1/graph/search` returns top-k communities by embedding similarity to a query string
**Plans:** 1 plan
Plans:
- [ ] 16-01-PLAN.md — DB helpers + 5 route handlers + Pydantic models + 14+ tests
**UI hint**: no

### Phase 17: Document Graph Status
**Goal**: Users can see at a glance whether graph extraction has run for each document, including entity and relationship counts, without leaving the document list or detail page
**Depends on**: Nothing (backend graph_status field already in DocumentResponse since Phase 14)
**Requirements**: DOC-GRAPH-01, DOC-GRAPH-02, DOC-GRAPH-03, DOC-GRAPH-04
**Success Criteria** (what must be TRUE):
  1. Document list table shows a graph status badge (e.g., built / pending / failed) for each document row
  2. Document list table shows entity count and relationship count in compact columns beside the status badge
  3. Document detail page shows a graph build section with status, entity count, relationship count, and last-built timestamp (and error message if failed)
  4. When GRAPH_RAG_ENABLED is false on the backend (all documents have null graph_status), graph columns and sections are hidden — no broken UI
**Plans**: TBD
**UI hint**: yes

### Phase 18: Entity Explorer
**Goal**: Users can browse, filter, and search all entities extracted across their tenant, and drill into any entity to see which documents mention it
**Depends on**: Phase 16
**Requirements**: ENT-01, ENT-02, ENT-03, ENT-04
**Success Criteria** (what must be TRUE):
  1. Navigating to `/entities` shows a paginated table of entities with name, type, mention count, and document count columns
  2. User can filter the entity table by entity type using a dropdown that lists all EntityType enum values
  3. User can search entities by name (substring) using a text input; results update server-side as the user types
  4. Clicking an entity opens a detail view listing the documents that mention it, with each document name linking back to `/documents/{id}`
**Plans**: TBD
**UI hint**: yes

### Phase 19: Community Browser
**Goal**: Users can explore detected communities at multiple resolution levels, read their summaries, inspect member entities, and trigger a full tenant-wide community rebuild from the UI
**Depends on**: Phase 16
**Requirements**: COMM-UI-01, COMM-UI-02, COMM-UI-03, COMM-UI-04
**Success Criteria** (what must be TRUE):
  1. Navigating to `/communities` shows a paginated table of communities with title, resolution level, entity count, and a truncated summary preview
  2. User can expand a parent community row to reveal child communities at finer resolution levels (hierarchical nesting)
  3. Clicking a community opens a detail panel showing the full summary, resolution level, and a list of member entities with links to their entity detail
  4. A "Rebuild communities" button triggers `POST /v1/graph/communities/rebuild`; the UI shows a loading state during the request and a success toast with rebuild stats when complete; the last-rebuild timestamp is displayed
**Plans**: TBD
**UI hint**: yes

### Phase 20: Graph-Aware Search
**Goal**: Users can optionally augment their vector search results with community-level context, seeing which knowledge communities the query best matches before diving into individual chunk results
**Depends on**: Phase 16
**Requirements**: SEARCH-G-01, SEARCH-G-02
**Success Criteria** (what must be TRUE):
  1. The search page has a "Include community context" toggle; when enabled, submitting a query shows a community matches section above the chunk results
  2. Each community match in the results shows: title, truncated summary with an expand control to reveal the full text, resolution level, and linked member entities
  3. When the toggle is off, the search page behaves identically to its pre-v1.1 behavior with no regressions
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase                                      | Milestone | Plans | Status      | Completed  |
|--------------------------------------------|-----------|-------|-------------|------------|
| 01. Foundation & Infrastructure            | v1.0      | 1/1   | Complete    | 2026-03-03 |
| 02. Document Parsing                       | v1.0      | 1/1   | Complete    | 2026-03-03 |
| 03. Chunking & Embedding                   | v1.0      | 1/1   | Complete    | 2026-03-03 |
| 04. Search & Document Management           | v1.0      | 1/1   | Complete    | 2026-03-03 |
| 05. Auth & Multi-Tenancy                   | v1.0      | 1/1   | Complete    | 2026-03-04 |
| 06. Reliability & Observability            | v1.0      | 2/2   | Complete    | 2026-03-04 |
| 07. Tech Debt Cleanup                      | v1.0      | 1/1   | Complete    | 2026-03-04 |
| 08. Graph Data Models                      | v1.0.1    | 2/2   | Complete    | 2026-04-12 |
| 09. Entity Extraction                      | v1.0.1    | 1/1   | Complete    | 2026-04-12 |
| 10. Graph Builder Worker                   | v1.0.1    | 1/1   | Complete    | 2026-04-12 |
| 11. Community Detection                    | v1.0.1    | 2/2   | Complete    | 2026-04-12 |
| 12. Restore Graph RAG Traceability         | v1.0.1    | 4/4   | Complete    | 2026-04-16 |
| 13. Wire Graph Data Lifecycle Cleanup      | v1.0.1    | 1/1   | Complete    | 2026-04-16 |
| 14. Surface Graph Status via Document API  | v1.0.1    | 1/1   | Complete    | 2026-04-17 |
| 15. Graph RAG Code Quality & Hardening     | v1.0.1    | 1/1   | Complete    | 2026-04-17 |
| 16. Graph Frontend APIs                    | v1.1      | 0/1   | Planned     | -          |
| 17. Document Graph Status                  | v1.1      | 0/TBD | Not started | -          |
| 18. Entity Explorer                        | v1.1      | 0/TBD | Not started | -          |
| 19. Community Browser                      | v1.1      | 0/TBD | Not started | -          |
| 20. Graph-Aware Search                     | v1.1      | 0/TBD | Not started | -          |
