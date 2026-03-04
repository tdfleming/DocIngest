# Plan 07-01 Summary: Tech Debt Cleanup

## Result: COMPLETE

## What Changed

### Task 1: Fix docstring mismatch in chunker worker
- **File:** `src/docingest/workers/chunker.py`
- **Change:** Updated module docstring from `chunk_document` to `chunk_and_embed` to match the actual ARQ job function name registered in `WorkerSettings`.
- **Lines affected:** Line 3 only (docstring text).

### Task 2: Replace deprecated datetime.utcnow() with datetime.now(UTC)
- **Files modified:**
  - `src/docingest/workers/chunker.py` — 2 instances replaced (lines 142, 190), import updated to `from datetime import UTC, datetime`
  - `src/docingest/db/mongodb.py` — 4 instances replaced (lines 41, 42, 61, 102), import updated to `from datetime import UTC, datetime`
  - `src/docingest/models/document.py` — 2 instances replaced (lines 56, 57 `default_factory`), import updated to `from datetime import UTC, datetime`. Changed from `default_factory=datetime.utcnow` to `default_factory=lambda: datetime.now(UTC)`.

### Gap Closure
The plan listed only `chunker.py` and `mongodb.py`, but the must_have truth "No datetime.utcnow() calls remain in codebase" required also fixing 2 occurrences in `models/document.py`. These were identified during verification and fixed.

## Verification Results

| Check | Result |
|-------|--------|
| `grep -rn "utcnow" src/docingest/` returns no results | PASS |
| `grep -n "chunk_and_embed" src/docingest/workers/chunker.py` shows docstring match | PASS |
| `python -m py_compile src/docingest/workers/chunker.py` | PASS |
| `python -m py_compile src/docingest/db/mongodb.py` | PASS |
| `python -m py_compile src/docingest/models/document.py` | PASS |

## Decisions

- Used `lambda: datetime.now(UTC)` for Pydantic `default_factory` fields since `datetime.now(UTC)` cannot be passed as a bare callable (it requires an argument), unlike the previous `datetime.utcnow` which was a bound method.

## Risks / Follow-ups

None. All changes are non-functional (docstring fix) or semantically equivalent (UTC datetime construction method).
