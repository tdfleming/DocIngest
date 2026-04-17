---
phase: 12
slug: graph-rag-traceability
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-04-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Phase 12 is a pure-documentation phase — validation is entirely grep/file-presence based.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | shell (grep + test) — no new framework; this phase edits Markdown only |
| **Config file** | none |
| **Quick run command** | `bash .planning/phases/12-graph-rag-traceability/verify.sh` (created by Wave 0 if elected; otherwise run the individual greps per task) |
| **Full suite command** | same as Quick — no separate full suite for a docs phase |
| **Estimated runtime** | <5 seconds |

---

## Sampling Rate

- **After every task commit:** Run the grep/file-test checks listed under that task's `acceptance_criteria` in the PLAN.
- **After every plan wave:** Run all per-task checks for every task in the wave.
- **Before `/gsd:verify-work`:** All per-task checks green + the cross-reference consistency check below.
- **Max feedback latency:** <5 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | REQUIREMENTS.md expansion — schema present for all 25 REQ-IDs | grep/count | `grep -c '^- \[.\] \*\*' .planning/REQUIREMENTS.md` returns `25` | ✅ | ⬜ pending |
| 12-01-02 | 01 | 1 | REQUIREMENTS.md — every entry has Description/DoD/Verification | grep | `grep -c 'Description:' .planning/REQUIREMENTS.md` returns `25` (and same for `Definition of Done:`, `Verification criteria:`) | ✅ | ⬜ pending |
| 12-01-03 | 01 | 1 | Status overrides for GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05 | grep | `grep -E 'GRAPH-WORKER-0[25].*Satisfied\*' .planning/REQUIREMENTS.md` returns 2 matches; same for `COMM-05.*Satisfied\*` returns 1 | ✅ | ⬜ pending |
| 12-02-01 | 02 | 1 | PROJECT.md — Graph RAG removed from Out of Scope | grep | `! grep -q 'Graph RAG / knowledge graph' .planning/PROJECT.md` (must NOT match) | ✅ | ⬜ pending |
| 12-02-02 | 02 | 1 | PROJECT.md — Graph RAG added to Validated | grep | `grep -q 'v1.0 extension' .planning/PROJECT.md` | ✅ | ⬜ pending |
| 12-02-03 | 02 | 1 | PROJECT.md — Last updated bumped | grep | `grep -q '2026-04-16' .planning/PROJECT.md` | ✅ | ⬜ pending |
| 12-03-01 | 03 | 1 | MILESTONES.md — Graph RAG Extension block present | grep | `grep -q '### v1.0 Graph RAG Extension' .planning/MILESTONES.md` | ✅ | ⬜ pending |
| 12-03-02 | 03 | 1 | MILESTONES.md — Phase range 8-11 recorded | grep | `grep -qE 'Phases?:.*8.*11' .planning/MILESTONES.md` | ✅ | ⬜ pending |
| 12-04-01 | 04 | 1 | 10-01-SUMMARY frontmatter | grep | `grep -q 'requirements-completed: \[GRAPH-WORKER-01, GRAPH-WORKER-02, GRAPH-WORKER-03, GRAPH-WORKER-04, GRAPH-WORKER-05\]' .planning/phases/10-graph-builder-worker/10-01-SUMMARY.md` | ✅ | ⬜ pending |
| 12-04-02 | 04 | 1 | 11-01-SUMMARY frontmatter | grep | `grep -q 'requirements-completed: \[COMM-01, COMM-02, COMM-03, COMM-04\]' .planning/phases/11-community-detection/11-01-SUMMARY.md` | ✅ | ⬜ pending |
| 12-04-03 | 04 | 1 | 11-02-SUMMARY frontmatter | grep | `grep -q 'requirements-completed: \[COMM-05\]' .planning/phases/11-community-detection/11-02-SUMMARY.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Cross-Reference Consistency Check (Phase Gate)

Before marking phase complete, run these consistency checks:

```bash
# Every REQ-ID declared in REQUIREMENTS.md must also appear in at least one PLAN requirements: frontmatter
comm -23 \
  <(grep -oE '\*\*[A-Z-]+-[0-9]+\*\*' .planning/REQUIREMENTS.md | tr -d '*' | sort -u) \
  <(grep -hoE '(GRAPH|EE|GRAPH-WORKER|COMM)-[0-9]+' .planning/phases/{08,09,10,11}-*/*PLAN.md | sort -u)
# Expected: empty output (no REQ-IDs in REQUIREMENTS.md absent from plans)

# Every SUMMARY with requirements-completed declares REQ-IDs that also appear in REQUIREMENTS.md
grep -hoE '(GRAPH|EE|GRAPH-WORKER|COMM)-[0-9]+' .planning/phases/{08,09,10,11}-*/*SUMMARY.md | sort -u | \
  while read req; do grep -q "\*\*${req}\*\*" .planning/REQUIREMENTS.md || echo "ORPHAN: $req"; done
# Expected: no ORPHAN lines
```

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — this is a documentation phase. No new test files, fixtures, or tooling required.*

Optional convenience script (planner's call): create `.planning/phases/12-graph-rag-traceability/verify.sh` that bundles the per-task greps for rapid re-runs.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| REQUIREMENTS.md prose readability — descriptions/DoD are human-comprehensible and match shipped behavior | all 25 REQ-IDs | Prose quality cannot be grep-verified | Reviewer reads each REQ-ID entry and spot-checks 3-5 entries against the source file anchors from 12-RESEARCH.md |
| PROJECT.md Validated entries accurately describe Graph RAG scope | GRAPH-* summary entry | Semantic accuracy | Reviewer compares new bullet points with `.planning/v1.0-MILESTONE-AUDIT.md` scope reconciliation section |
| MILESTONES.md block narrative matches what shipped | v1.0 extension block | Semantic accuracy | Reviewer cross-references with SUMMARY files for phases 8-11 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify (grep/file-test commands)
- [ ] Sampling continuity: every task is independently grep-verifiable
- [ ] Wave 0 covers all MISSING references (none needed for docs phase)
- [ ] No watch-mode flags (N/A — no test runner)
- [ ] Feedback latency <5s (grep commands run in ms)
- [ ] `nyquist_compliant: true` set in frontmatter after all automated checks pass + cross-reference consistency check is clean

**Approval:** pending
