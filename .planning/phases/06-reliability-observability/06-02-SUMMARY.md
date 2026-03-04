# Plan 06-02 Summary

## Plan Info
- **Plan ID:** 06-02
- **Plan Name:** Structured JSON logging with trace IDs and per-stage timing
- **Phase:** 06-reliability-observability
- **Status:** complete

## Tasks Completed

### Task 1: Create logging config and add request logging middleware with trace IDs
- **Commit:** `2f4042c` — feat(06-02): create logging config and add request logging middleware with trace IDs
- **Files modified:**
  - `src/docingest/logging_config.py` — New file: configures structlog with JSONRenderer, TimeStamper, merge_contextvars, and routes stdlib logging through structlog
  - `src/docingest/api/middleware.py` — Added RequestLoggingMiddleware that generates trace_id, logs method/path/status/duration_ms, sets X-Trace-Id response header
  - `src/docingest/api/app.py` — Imported and called configure_logging() at module level; added RequestLoggingMiddleware before RateLimitHeaderMiddleware

### Task 2: Add trace_id and per-stage timing to pipeline workers
- **Commit:** `ab5c8c6` — feat(06-02): add trace_id and per-stage timing to pipeline workers
- **Files modified:**
  - `src/docingest/api/routes/documents.py` — Added `request: Request` param and trace_id generation to upload_document, ingest_from_url, batch_ingest, and reprocess_document; updated _enqueue_conversion to pass trace_id; renamed body params to avoid collision with Request
  - `src/docingest/workers/converter.py` — Added trace_id parameter, structlog contextvars binding, per-stage timing (download_ms, convert_ms, upload_ms), timing in success log, contextvars cleanup in finally block, trace_id forwarded to chunking job
  - `src/docingest/workers/chunker.py` — Added trace_id parameter, structlog contextvars binding, per-stage timing (download_ms, chunk_ms, embed_ms, upsert_ms), timing in success log, contextvars cleanup in finally block

## Files Modified
- `src/docingest/logging_config.py` (new)
- `src/docingest/api/middleware.py`
- `src/docingest/api/app.py`
- `src/docingest/api/routes/documents.py`
- `src/docingest/workers/converter.py`
- `src/docingest/workers/chunker.py`

## Deviations from Plan
- Renamed `request` parameter to `body` in `ingest_from_url` and `batch_ingest` to avoid name collision with the added `request: Request` FastAPI parameter. This is a purely internal naming change with no behavioral impact.
- Removed redundant `doc_id=doc_id` from worker log calls since doc_id is now bound via structlog contextvars and automatically included in all log output.

## Key Decisions
- structlog contextvars used for trace_id propagation (bind at start, unbind in finally block) — ensures trace_id appears in all log output within the request/worker scope
- trace_id extracted from middleware request.state when available, otherwise generated fresh (fallback for non-HTTP callers)
- Per-stage timing uses time.monotonic() for accurate elapsed measurement
- All error handling from 06-01 preserved intact — timing wraps only the happy-path calls within existing try/except blocks
- Workers use finally block for contextvars cleanup to ensure cleanup even on unexpected exceptions

## Verification
- All six files pass `python -m py_compile`
- logging_config.py configures structlog with JSONRenderer
- RequestLoggingMiddleware generates trace_id and logs requests with duration_ms
- X-Trace-Id header returned in responses
- trace_id passed through job queue to workers via enqueue_job kwargs
- Workers bind trace_id to structlog context via contextvars
- Workers log per-stage timing (download_ms, convert_ms, upload_ms, chunk_ms, embed_ms, upsert_ms)
