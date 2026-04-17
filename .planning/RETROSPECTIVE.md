# DocIngest — Retrospective

Living document of milestone retrospectives. New milestone sections are appended as they ship. Cross-milestone trends are tracked at the bottom.

---

## Milestone: v1.0.1 — Graph RAG Extension

**Shipped:** 2026-04-17
**Phases:** 8 (phases 8-15) | **Plans:** 12

### What Was Built

Layered a knowledge-graph pipeline onto the v1.0 MVP:

- **Graph data models** (phase 8) — Entity/Relationship/Community Pydantic v2 models, MongoDB graph store, tenant-scoped compound indexes.
- **Entity extraction** (phase 9) — spaCy NER + SVO relationship extraction with lazy-loaded `en_core_web_lg` singleton and fuzzy dedup.
- **Graph builder worker** (phase 10) — Dedicated ARQ worker with separate queue, chunks-from-Qdrant pipeline, status tracking through build stages.
- **Community detection** (phase 11) — Multi-resolution Leiden clustering, TF-IDF extractive summaries, FastEmbed embeddings, on-demand rebuild API.
- **Gap closure (phases 12-15)** — Traceability docs, synchronous route-level graph cleanup, API-surface exposure, and 5 code-quality refactors closing deprecated asyncio calls, fragile vertex-index invariant, missing collection guard, and duplicate index-creation call.

All functionality gated by `GRAPH_RAG_ENABLED`. MVP remains fully operable without graph features.

### What Worked

- **Feature flag discipline.** Every graph call site gated on `settings.graph_rag_enabled` — made phase 13/14 hardening possible without risking the MVP.
- **Reusing existing patterns.** The spaCy lazy-load singleton mirrored `embedding.py`; the graph cleanup pattern mirrored existing blob/Qdrant cleanup; Pydantic v2 models mirrored `document.py`. Zero invented conventions.
- **Audit-driven gap closure.** Running `/gsd:audit-milestone` after phases 8-11 surfaced clearly categorized gaps (FLOW-*, INT-*, COMM-* tech debt) that mapped cleanly to 4 follow-on phases. Each phase had a single, narrow goal.
- **Per-phase verification.** Phases 13/14/15 each produced a VERIFICATION.md with grep-able acceptance criteria + test runs. Made milestone completion unambiguous.
- **Tech-debt phase batching.** Phase 15 bundled 5 unrelated but similarly-scoped refactors into one plan with concrete edits. Kept context minimal, ran in ~4 minutes.
- **Skip-research for trivial phases.** Phases 13/14/15 all used `--skip-research` — context + requirements were enough to generate correct plans.

### What Was Inefficient

- **Graph RAG extension shipped without traceability.** Phases 8-11 landed without REQUIREMENTS.md entries, SUMMARY frontmatter, or milestone records. Phase 12 had to retroactively backfill 25 REQ-ID entries. Should have been done as part of each phase's plan.
- **Missing VERIFICATION.md on phases 8-11.** The gap was not caught until the milestone audit. Going forward, every code phase should produce VERIFICATION.md inline.
- **Audit-state staleness.** The audit file status stayed at `gaps_found` even after every gap was closed. Would be useful for the audit to be re-runnable and for the status to reflect current state.
- **REQUIREMENTS.md coverage counters drifted.** "Satisfied: 23" vs actual 25 `[x]` rows — stale after phase 15. Counter updates should be mechanical, perhaps part of `gsd-tools milestone complete`.
- **INT-01 removal broke a GRAPH-05 verification criterion.** The criterion text was `grep 'ensure_graph_indexes' mongodb.py` ≥ 1 match — but the INT-01 fix removed the call. Criteria need to survive refactors, or the traceability system needs to catch criteria-breaking changes.

### Patterns Established

- **"Gate at call site, not inside helpers."** Graph features are gated where they're invoked; helpers stay pure. Makes helpers reusable and the gate auditable.
- **Lenient error mode for best-effort cleanup.** `try/except` + log, not HTTP 500. Matches existing blob/Qdrant semantics; worker safety net is the consistency backstop.
- **`--skip-research` for trivial phases.** When CONTEXT.md is complete and the codebase is well-understood, the researcher adds no value. Saves ~5 minutes per phase.
- **Extend existing test files, don't create siblings.** Phase 15 extended `tests/test_community_detection.py` rather than creating a new file. Keeps discovery simple.
- **ID-keyed lookups beat index-keyed lookups.** The `idx_to_entity` refactor used `graph.vs[m]["name"]` (entity ID) instead of list enumeration. Robust to reordering; should be the default pattern for any entity-collection-to-graph-vertex mapping.

### Key Lessons

1. **Ship requirements docs inline with code.** Not after. Every code phase should have a `requirements:` frontmatter and SUMMARY.md with `requirements-completed:` at the time of the plan, not backfilled.
2. **Feature flags are cheap insurance.** `GRAPH_RAG_ENABLED` let us ship phases 8-11 without disrupting MVP operation. Worth the small conditional branches everywhere.
3. **Audit before milestone completion, plan gap closure as real phases.** Don't try to close audit gaps with ad-hoc fixes. Scope them as phases with CONTEXT + PLAN + VERIFICATION.
4. **"Just grep it" is a valid verification technique for correctness-preserving refactors.** Phase 15's asyncio migration had zero behavioral change — grep-verifying `get_event_loop() returns 0 matches` was faster and more reliable than writing behavioral tests.
5. **Existing Docker-installed dependencies can cause local test env gaps.** `test_entity_extraction.py` fails locally without `en_core_web_sm`; works in the graph-worker image. This is a documentation/setup issue, not a code gap.

### Cost Observations

- Model mix: Opus for planners, Sonnet for researchers/executors/verifiers/checkers (per config).
- Sessions: ~4-5 sessions across gap closure (12, 13, 14, 15 each ran in a single session).
- Notable: Phase 15 executed 10 distinct edits + 5 new tests in ~4 minutes. Tech-debt phases benefit from heavy CONTEXT.md pre-work.

---

## Milestone: v1.0 — MVP (2026-03-04)

*Retrospective not captured at the time. Summary below is reconstructed from MILESTONES.md and phase SUMMARY files.*

**Phases:** 7 | **Plans:** 8 | **Python LOC:** 2,118 | **Duration:** 2 days (2026-03-03 → 2026-03-04)

Delivered a multi-tenant document ingestion engine with full async pipeline, semantic search, API key auth, and structured observability — all running locally without cloud dependencies. Replaced Azure Blob/OpenAI with MinIO/FastEmbed. Implemented structlog JSON logging with trace IDs, Redis token-bucket rate limiting (fail-open), and tenant-scoped Qdrant collections.

Key decisions still standing (all ✓ Good): MinIO single-bucket tenant prefix, FastEmbed bge-small-en-v1.5 (384-dim), per-stage timing via `time.monotonic()`, structlog contextvars for trace_id, lambda Pydantic default_factory for `datetime.now(UTC)`.

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.0.1 | Delta |
|---|---|---|---|
| Phases | 7 | 8 | +8 cumulative (15 total) |
| Plans | 8 | 12 | +12 cumulative (20 total) |
| Python LOC | 2,118 | 4,586 | +2,468 (116% growth) |
| Timeline | 2 days | 44 days | Graph RAG was a slow build |
| New services | 0 | 2 (entity_extraction, community_detection) | |
| New workers | 0 | 1 (graph-worker) | |
| New Pydantic models | 0 | 3 (Entity, Relationship, Community) | |

### Recurring patterns

- **Feature flags enable large additions without disrupting shipped capabilities** (GRAPH_RAG_ENABLED is the pattern; v1.0 used configurable embeddings for similar reasons).
- **Audit-driven gap closure works.** The v1.0.1 audit → phases 12-15 sequence closed every identified gap with per-phase verification.
- **Reuse established patterns.** Both milestones show a strong bias toward mirroring existing code conventions over inventing new ones.

### Recurring pain points

- **Traceability-after-the-fact.** Both milestones had retroactive documentation work. v1.0 was caught before ship; v1.0.1 required a dedicated traceability phase (12). Solution: enforce `requirements:` frontmatter and SUMMARY `requirements-completed:` as plan-execution gates.
- **Coverage counter drift.** REQUIREMENTS.md header counters are edited by hand and drift behind reality. Solution: automated counter update via `gsd-tools`.

---

*Last updated: 2026-04-17 after v1.0.1 ship*
