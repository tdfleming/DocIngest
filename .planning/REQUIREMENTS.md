# Requirements: DocIngest

**Current milestone:** v1.1 Graph Frontend
**Last updated:** 2026-04-17

Prior milestone requirements (23 for v1.0 MVP, 25 for v1.0.1 Graph RAG Extension) are archived at:
- [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
- [milestones/v1.0.1-REQUIREMENTS.md](milestones/v1.0.1-REQUIREMENTS.md)

This file tracks the **v1.1 Graph Frontend** milestone only. v1.1 adds frontend UI to surface the v1.0.1 backend Graph RAG pipeline. All endpoints and data are already live — this milestone is purely additive React/TypeScript/Chakra work.

---

## Coverage

- **Total REQ-IDs:** 17
- **Satisfied:** 0 (milestone in progress)
- **Partial:** 0
- **Pending:** 17

---

## Document Graph Status (Category: DOC-GRAPH)

Surface the per-document graph build fields already returned by the v1.0.1 API.

- [ ] **DOC-GRAPH-01** — Document list shows graph status badge — Phase: 17 — Status: Pending
- [ ] **DOC-GRAPH-02** — Document list shows entity and relationship counts (compact) — Phase: 17 — Status: Pending
- [ ] **DOC-GRAPH-03** — Document detail page shows full graph build metadata (status, counts, last-built timestamp, error if any) — Phase: 17 — Status: Pending
- [ ] **DOC-GRAPH-04** — Graph UI is gated: hides graph columns/sections when the `graph_status` field is `null` for all documents (signals `GRAPH_RAG_ENABLED=false` on backend) — Phase: 17 — Status: Pending

## Entity Explorer (Category: ENT)

New page / view for browsing entities extracted across a tenant.

- [ ] **ENT-01** — Entity list page (`/entities`) with paginated table: name, entity_type, mention_count, doc_count — Phase: 18 — Status: Pending
- [ ] **ENT-02** — Filter entities by type (dropdown / multi-select using EntityType enum values) — Phase: 18 — Status: Pending
- [ ] **ENT-03** — Search entities by name (substring match, server-side) — Phase: 18 — Status: Pending
- [ ] **ENT-04** — Entity detail view shows linked documents (clickable back to `/documents/{id}`) — Phase: 18 — Status: Pending
- [ ] **ENT-05** — Backend API endpoints for list/filter/search/detail — new `/v1/graph/entities` endpoints backing the UI — Phase: 16 — Status: Pending

## Community Browser (Category: COMM-UI)

List, inspect, and rebuild communities from the frontend.

- [ ] **COMM-UI-01** — Community list page (`/communities`) with paginated table: title, resolution_level, size (entity_count), summary preview — Phase: 19 — Status: Pending
- [ ] **COMM-UI-02** — Hierarchical view — expand parent communities to show child communities at finer resolutions — Phase: 19 — Status: Pending
- [ ] **COMM-UI-03** — Community detail panel shows full summary, member entities (linked), resolution level — Phase: 19 — Status: Pending
- [ ] **COMM-UI-04** — Rebuild action — button triggers `POST /v1/graph/communities/rebuild` with loading state; shows toast on success with stats; shows last-rebuild timestamp — Phase: 19 — Status: Pending
- [ ] **COMM-UI-05** — Backend API endpoints for list/detail — new `/v1/graph/communities` GET endpoints backing the UI — Phase: 16 — Status: Pending

## Graph-Aware Search (Category: SEARCH-G)

Extend the existing search page to optionally surface community summaries alongside chunk matches.

- [ ] **SEARCH-G-01** — Toggle on search page: "Include community context" — when on, search results UI includes a top-matches-by-community section above chunk results — Phase: 20 — Status: Pending
- [ ] **SEARCH-G-02** — Each community match shows: title, summary (truncated with expand), resolution level, linked member entities — Phase: 20 — Status: Pending
- [ ] **SEARCH-G-03** — Backend endpoint: new `/v1/graph/search` (or extension of existing `/v1/search` with a `include_communities` flag) returning top-k communities by embedding similarity to query — Phase: 16 — Status: Pending

---

## Out of Scope (v1.1)

- **Interactive graph visualization** (force-directed node-link diagrams). Deferred to v1.2+ after we see how users actually use the tabular views.
- **High-polish animations / custom viz widgets.** MVP uses Chakra UI defaults; iterate later.
- **Admin toggle for `GRAPH_RAG_ENABLED`.** Requires server restart today; defer until runtime reload is designed.
- **Entity merging / manual deduplication UI.** Dedup happens at extraction time; manual override is a future concern.
- **Relationship graph browser as a separate page.** Relationships are surfaced via entity detail (linked docs, mention count); no dedicated page.
- **Graph export** (CSV, JSON, GraphML of tenant graph). Out-of-scope for v1.1; add later if requested.
- **Multi-tenant admin view across tenants.** Tenant-scoped isolation from v1.0 remains the model.

---

## Traceability

| REQ-ID | Phase | Status |
|---|---|---|
| DOC-GRAPH-01 | Phase 17 | Pending |
| DOC-GRAPH-02 | Phase 17 | Pending |
| DOC-GRAPH-03 | Phase 17 | Pending |
| DOC-GRAPH-04 | Phase 17 | Pending |
| ENT-01 | Phase 18 | Pending |
| ENT-02 | Phase 18 | Pending |
| ENT-03 | Phase 18 | Pending |
| ENT-04 | Phase 18 | Pending |
| ENT-05 | Phase 16 | Pending |
| COMM-UI-01 | Phase 19 | Pending |
| COMM-UI-02 | Phase 19 | Pending |
| COMM-UI-03 | Phase 19 | Pending |
| COMM-UI-04 | Phase 19 | Pending |
| COMM-UI-05 | Phase 16 | Pending |
| SEARCH-G-01 | Phase 20 | Pending |
| SEARCH-G-02 | Phase 20 | Pending |
| SEARCH-G-03 | Phase 16 | Pending |

---

*Requirements v1.1 — defined 2026-04-17*
