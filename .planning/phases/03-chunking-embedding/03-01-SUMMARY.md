# Plan 03-01 Summary: Fix Pipeline Wiring and Add Per-Upload Chunking Config

## Status: COMPLETE

## What Changed

### Pipeline Wiring Fix (workers/converter.py)
- **Fixed:** `enqueue_job("chunk_document", ...)` changed to `enqueue_job("chunk_and_embed", ...)` on line 62
- **Impact:** The converter worker now enqueues jobs with the function name that matches the chunker worker function (`chunk_and_embed` in `chunker.py` line 25). Previously, the mismatched name meant the chunking step never fired after conversion.

### Chunking Strategy Default (config.py)
- **Added:** `chunking_strategy: str = "fixed"` to Settings class (after `chunk_overlap_percent`)
- **Impact:** Provides a global default strategy. Only "fixed" is supported in v1.

### Per-Upload Chunking Params (api/routes/documents.py)
- **Added:** `Field` import from pydantic
- **Added:** Three optional fields to `UrlIngestRequest` model: `chunk_size` (100-2000), `chunk_overlap` (0-50), `chunking_strategy`
- **Added:** Three optional Query params to `upload_document()`: `chunk_size`, `chunk_overlap`, `chunking_strategy`
- **Added:** 400 validation in both `upload_document()` and `ingest_from_url()` when `chunking_strategy` is not "fixed"
- **Added:** `chunking_config` dict construction from non-None params in both upload paths
- **Added:** `chunking_config` stored in MongoDB document insert dict (only when non-empty)
- **Unchanged:** Batch ingest delegates to `ingest_from_url()` and inherits the new params via `UrlIngestRequest`

### Chunking Service Overrides (services/chunking.py)
- **Changed:** `chunk_document()` signature now accepts keyword-only `max_tokens: int | None = None` and `overlap_percent: int | None = None`
- **Added:** Resolution logic: per-doc values used when provided, global `settings` defaults used as fallback
- **Changed:** `_semantic_sub_split()` call uses resolved `_max_tokens` and `_overlap_pct` instead of reading `settings` directly
- **Unchanged:** `_split_by_headings()` and `_semantic_sub_split()` internal logic untouched

### Chunker Worker Per-Doc Config (workers/chunker.py)
- **Added:** `chunk_cfg = doc.get("chunking_config", {})` to read per-doc config from MongoDB document record
- **Changed:** `chunk_document(markdown)` call now passes `max_tokens=chunk_cfg.get("chunk_size")` and `overlap_percent=chunk_cfg.get("chunk_overlap")`
- **Impact:** When a document has `chunking_config` stored (from upload params), those values override global defaults. When no config is stored, `None` values cause `chunk_document()` to fall back to global settings.

## Files Modified
- `src/docingest/workers/converter.py`
- `src/docingest/config.py`
- `src/docingest/api/routes/documents.py`
- `src/docingest/services/chunking.py`
- `src/docingest/workers/chunker.py`

## Verification Results
- [x] All 5 modified files pass `py_compile` with no syntax errors
- [x] Converter enqueues `"chunk_and_embed"` (matches chunker function name)
- [x] `"chunk_document"` no longer appears in converter.py (old name removed)
- [x] Upload endpoint accepts `chunk_size`, `chunk_overlap`, `chunking_strategy` query params
- [x] URL ingest endpoint accepts `chunk_size`, `chunk_overlap`, `chunking_strategy` in request body
- [x] Invalid `chunking_strategy` returns 400 in both endpoints
- [x] `chunking_config` stored in MongoDB document insert (both upload paths)
- [x] Chunker worker reads `chunking_config` from document record
- [x] `chunk_document()` accepts optional `max_tokens` and `overlap_percent` kwargs
- [x] Default behavior unchanged when no chunking params provided (falls back to settings)
