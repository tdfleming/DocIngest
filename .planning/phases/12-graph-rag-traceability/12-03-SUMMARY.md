---
phase: 12
plan: 03
subsystem: planning-artifacts
tags: [documentation, milestones, traceability, gap-closure, graph-rag]
requirements-completed: []
one-liner: "Appended v1.0 Graph RAG Extension (2026-04-12) subsection to MILESTONES.md, recording phases 8-11 scope under the existing v1.0 milestone"
dependency-graph:
  requires:
    - ".planning/MILESTONES.md (existing v1.0 MVP block)"
    - ".planning/v1.0-MILESTONE-AUDIT.md (cross-reference target)"
  provides:
    - "MILESTONES.md v1.0 Graph RAG Extension narrative record"
  affects:
    - "Planning-artifact completeness (milestone history)"
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - ".planning/MILESTONES.md"
decisions:
  - "Graph RAG recorded as a ### subsection within the existing ## v1.0 MVP block (not a new top-level heading) per 12-CONTEXT.md lock"
  - "Insertion placed BEFORE the closing --- separator to scope the new subsection inside the v1.0 milestone block"
  - "Git range recorded as 85e5a0e (v1.0 ship) → 479736f (gap closure phases added) to bracket the Graph RAG work"
metrics:
  duration-minutes: 1
  tasks-completed: 1
  files-touched: 1
  completed: "2026-04-16"
---

# Phase 12 Plan 03: Update MILESTONES.md with v1.0 Graph RAG Extension Record — Summary

## What Shipped

Appended a new `### v1.0 Graph RAG Extension (2026-04-12)` subsection inside the existing `## v1.0 MVP (Shipped: 2026-03-04)` block in `.planning/MILESTONES.md`. The subsection records the Graph RAG extension work (phases 8-11) as a scoped-into-v1.0 delivery, documenting:

- **Delivered capabilities:** Knowledge-graph pipeline (spaCy NER + SVO relationships, MongoDB tenant-scoped graph store, on-demand Leiden community detection with TF-IDF summaries), all gated by `GRAPH_RAG_ENABLED`.
- **Scope:** Phases 8-11 (7 plans total), 25 requirements declared (GRAPH-01..07, EE-01..08, GRAPH-WORKER-01..05, COMM-01..05).
- **Status:** `⚠ Gap closure in flight (phases 12-15)` with cross-reference to `.planning/v1.0-MILESTONE-AUDIT.md`.
- **Stats:** New ARQ `graph-worker` service (queue `arq:queue:graph`), new services (`entity_extraction`, `community_detection`), new models (Entity, Relationship, Community), new dependencies (spaCy `en_core_web_lg`, python-igraph, leidenalg, scikit-learn).
- **Git range:** `85e5a0e` (v1.0 ship) → `479736f` (gap closure phases added).

The existing v1.0 MVP block (lines 1-25 pre-edit) was preserved verbatim. No new top-level milestone heading was created.

## How It Works

- MILESTONES.md now has two `###` subsections under the `## v1.0 MVP` heading (implicitly — the first v1.0 MVP content itself, then the new Graph RAG Extension).
- The `---` separator at the end of the v1.0 MVP block was retained to bound the full milestone record (original + extension) from any future milestones.
- The audit cross-reference (`v1.0-MILESTONE-AUDIT.md`) allows readers to navigate from the narrative record to the gap-closure detail document.

## Decisions Made

- **`###` subsection vs `##` sibling heading:** Chose `###` (subsection inside v1.0 MVP) over `##` (sibling top-level). Rationale: the audit recommendation scopes Graph RAG into v1.0 rather than creating a separate v1.1 milestone. 12-VALIDATION.md grep check pattern `### v1.0 Graph RAG Extension` enforced this choice.
- **Insertion point:** Placed the new block BETWEEN the v1.0 MVP `**What's next:**` line and the closing `---` separator, making Graph RAG Extension a contained subsection of the v1.0 milestone block rather than a sibling.
- **No top-level v1.1 heading:** Explicitly rejected per 12-CONTEXT.md `<deferred>` block. The acceptance criterion `! grep -qE '^## v1\.1'` enforces this.

## Verification

All 13 acceptance-criteria greps from the plan passed:

| # | Check | Result |
|---|-------|--------|
| 1 | `grep -q '### v1.0 Graph RAG Extension (2026-04-12)'` | PASS |
| 2 | `grep -qE 'Phases?:.*8.*11'` | PASS |
| 3 | `grep -q 'Knowledge-graph pipeline layered onto v1.0 MVP'` | PASS |
| 4 | `grep -q 'Requirements declared:\*\* 25'` | PASS |
| 5 | `grep -q 'Gap closure in flight (phases 12-15)'` | PASS |
| 6 | `grep -q '.planning/v1.0-MILESTONE-AUDIT.md'` | PASS |
| 7 | `grep -q 'arq:queue:graph'` | PASS |
| 8 | `grep -q 'en_core_web_lg'` | PASS |
| 9 | `grep -qE '85e5a0e.*479736f'` | PASS |
| 10 | `grep -q '## v1.0 MVP (Shipped: 2026-03-04)'` (existing heading preserved) | PASS |
| 11 | `grep -q 'Multi-tenant document ingestion engine with full async pipeline'` (v1.0 delivered preserved) | PASS |
| 12 | `! grep -qE '^## v1\.1'` (no new top-level heading) | PASS |
| 13 | `grep -q '6e60969'` (original v1.0 git range preserved) | PASS |

Additionally confirmed byte-level preservation of the v1.0 MVP block (lines 1-25 of the final file byte-match the pre-edit file's lines 1-25).

## Deviations from Plan

None — plan executed exactly as written. The corrected insertion plan in the `<action>` block (placing the new subsection BEFORE the `---` separator, not after) was followed precisely.

## Known Stubs

None. The edit added concrete narrative content; no placeholders, TODO markers, or empty values introduced.

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Append v1.0 Graph RAG Extension block to MILESTONES.md | `2ec49df` |

## Self-Check: PASSED

- File exists: `.planning/MILESTONES.md` (modified) — FOUND
- Commit exists: `2ec49df` — FOUND
- All 13 acceptance-criteria greps pass.
- SUMMARY.md frontmatter `requirements-completed: []` matches plan output spec (planning-artifact gap closure, no REQ-IDs claimed).
