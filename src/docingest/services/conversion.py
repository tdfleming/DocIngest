import tempfile
from pathlib import Path

import structlog
from docling.document_converter import DocumentConverter

log = structlog.get_logger()

_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


def convert_to_markdown(raw_bytes: bytes, content_type: str, source_ref: str) -> str:
    """Convert a document to Markdown using Docling.

    TXT and MD content types are passed through without Docling conversion.
    For PDF, DOCX, and HTML, writes the raw bytes to a temp file, runs Docling,
    and returns clean Markdown.
    """
    # Pass-through for plain text — no Markdown structure, return as-is
    if content_type == "txt":
        text = raw_bytes.decode("utf-8")
        log.info(
            "pass-through conversion (txt)",
            source_ref=source_ref,
            content_type=content_type,
            text_length=len(text),
        )
        return text

    # Pass-through for Markdown — already in target format
    if content_type == "md":
        text = raw_bytes.decode("utf-8")
        log.info(
            "pass-through conversion (md)",
            source_ref=source_ref,
            content_type=content_type,
            markdown_length=len(text),
        )
        return text

    suffix_map = {"pdf": ".pdf", "html": ".html", "docx": ".docx"}
    suffix = suffix_map.get(content_type, ".bin")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)

    try:
        converter = _get_converter()
        result = converter.convert(tmp_path)
        markdown = result.document.export_to_markdown()
        log.info(
            "conversion complete",
            source_ref=source_ref,
            content_type=content_type,
            markdown_length=len(markdown),
        )
        return markdown
    finally:
        tmp_path.unlink(missing_ok=True)


def extract_metadata(markdown: str) -> dict:
    """Extract basic metadata from converted Markdown."""
    lines = markdown.strip().splitlines()
    title = None
    for line in lines:
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            break

    word_count = len(markdown.split())

    return {
        "title": title,
        "word_count": word_count,
    }
