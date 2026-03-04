# Plan 02-01 Summary: Add TXT/MD Support and File Size Metadata

## Status: COMPLETE

## What Changed

### Content Type Enum (models/document.py)
- **Added:** `TXT = "txt"` and `MD = "md"` to the `ContentType` enum (after DOCX)
- **Added:** `file_size_bytes: int = 0` field to the `Document` model (after `blob_path`)

### MIME and Extension Detection (api/routes/documents.py)
- **Added:** CONTENT_TYPE_MAP entries: `"text/plain": ContentType.TXT`, `"text/markdown": ContentType.MD`
- **Added:** EXTENSION_MAP entries: `".txt": ContentType.TXT`, `".md": ContentType.MD`, `".markdown": ContentType.MD`
- **Added:** `file_size_bytes: int = 0` to `DocumentResponse` model
- **Added:** `file_size_bytes` to `_doc_to_response()` helper (reads from doc with default 0)
- **Added:** `file_size = len(raw_bytes)` and `"file_size_bytes": file_size` in `upload_document()` insert
- **Added:** `file_size = len(raw_bytes)` and `"file_size_bytes": file_size` in `ingest_from_url()` insert

### Pass-Through Conversion (services/conversion.py)
- **Added:** Early-return pass-through for `content_type == "txt"` -- decodes UTF-8 and returns raw text without Docling
- **Added:** Early-return pass-through for `content_type == "md"` -- decodes UTF-8 and returns markdown without Docling
- **Unchanged:** PDF, DOCX, HTML continue to use Docling conversion via temp file path

### Converter Worker (workers/converter.py)
- **No changes needed:** Already calls `convert_to_markdown()` which now handles TXT/MD via pass-through. The rest of the pipeline (metadata extraction, blob upload, chunking enqueue) works identically regardless of format.

## Files Modified
- `src/docingest/models/document.py`
- `src/docingest/services/conversion.py`
- `src/docingest/api/routes/documents.py`

## Verification Results
- [x] `ContentType` enum values: `['pdf', 'html', 'docx', 'txt', 'md']`
- [x] `Document.model_fields` includes `file_size_bytes`
- [x] `text/plain` MIME mapping present in documents.py
- [x] `text/markdown` MIME mapping present in documents.py
- [x] `.txt`, `.md`, `.markdown` extension mappings present in documents.py
- [x] Pass-through logic for `content_type == "txt"` in conversion.py (no Docling)
- [x] Pass-through logic for `content_type == "md"` in conversion.py (no Docling)
- [x] `file_size_bytes` stored in both upload paths (file upload and URL ingestion)
- [x] `file_size_bytes` returned in `DocumentResponse` via `_doc_to_response()`
- [x] All 4 files pass `py_compile` with no syntax errors
