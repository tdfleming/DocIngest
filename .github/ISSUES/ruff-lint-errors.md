# Fix 25 remaining ruff lint errors

## Summary

There are 25 remaining ruff lint errors across the codebase. These are pre-existing issues that should be resolved to maintain code quality.

## Error Breakdown

### E402: Module level import not at top of file (14 errors)
**Files:** `workers/chunker.py` (8), `workers/converter.py` (6)

These are caused by the `configure_logging()` call placed between imports. The logging configuration must run before other docingest modules are imported (so structlog is configured before any logger is created). Options:
- Suppress E402 for these files with a `# noqa: E402` comment on each line
- Restructure logging init to avoid the issue (e.g., move `configure_logging()` into a module `__init__` or use a lazy-init pattern)

### B008: Function call in argument defaults (3 errors)
**File:** `api/auth.py` (lines 52, 75), `api/routes/documents.py` (line 140)

FastAPI idiom: `Security(...)`, `Depends(...)`, `File(...)` in function signatures. This is standard FastAPI practice and flagged by bugbear.
- **Fix:** Add `# noqa: B008` to these lines, or suppress B008 globally for FastAPI route files in `pyproject.toml`

### B904: `raise` without `from` in `except` clause (3 errors)
**Files:** `api/auth.py` (lines 64, 66), `api/routes/documents.py` (line 398)

```python
# Current:
except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Token expired")

# Fix:
except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Token expired") from None
```

### E501: Line too long (3 errors)
**Files:** `api/middleware.py` (line 35), `api/routes/documents.py` (line 147), `services/chunking.py` (line 130)

Lines 101-106 chars over the 100-char limit. Wrap or shorten.

### SIM105: Use `contextlib.suppress` instead of `try-except-pass` (2 errors)
**File:** `api/routes/documents.py` (lines 339, 344)

```python
# Current:
try:
    delete_blob(blob_client, tenant["tenant_id"], doc["blob_path"])
except Exception:
    pass

# Fix:
with contextlib.suppress(Exception):
    delete_blob(blob_client, tenant["tenant_id"], doc["blob_path"])
```

## Suggested Approach

1. Fix B904, E501, and SIM105 errors directly (straightforward code changes)
2. Suppress B008 for FastAPI dependency injection lines (idiomatic usage)
3. Decide on E402 strategy for worker files (suppress vs. restructure)
