import tempfile
import threading
from pathlib import Path

import structlog
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

log = structlog.get_logger()

_converter: DocumentConverter | None = None
_ocr_converter: DocumentConverter | None = None
_converter_lock = threading.Lock()


def _get_converter() -> DocumentConverter:
    """Standard converter with default OCR (bitmap-region only).

    Thread-safe via double-checked locking.
    """
    global _converter
    if _converter is None:
        with _converter_lock:
            if _converter is None:
                _converter = DocumentConverter()
    return _converter


def _get_ocr_converter() -> DocumentConverter:
    """Converter with force_full_page_ocr for image-heavy documents.

    Thread-safe via double-checked locking.
    """
    global _ocr_converter
    if _ocr_converter is None:
        with _converter_lock:
            if _ocr_converter is None:
                pipeline_options = PdfPipelineOptions(
                    do_ocr=True,
                    ocr_options=PdfPipelineOptions().ocr_options.model_copy(
                        update={"force_full_page_ocr": True}
                    ),
                )
                _ocr_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=pipeline_options
                        ),
                    }
                )
    return _ocr_converter


def convert_to_markdown(raw_bytes: bytes, content_type: str, source_ref: str) -> str:
    """Convert a document to Markdown using Docling.

    TXT and MD content types are passed through without Docling conversion.
    For PDF, DOCX, and HTML, writes the raw bytes to a temp file, runs Docling,
    and returns clean Markdown. If the first pass yields empty output for a PDF,
    retries with force_full_page_ocr to handle image-heavy/scanned documents.
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
        with _converter_lock:
            result = converter.convert(tmp_path)
        markdown = result.document.export_to_markdown()

        # Retry with full-page OCR if first pass produced no text (image-heavy PDF)
        if not markdown.strip() and content_type == "pdf":
            log.warning(
                "empty markdown from standard conversion, retrying with full-page OCR",
                source_ref=source_ref,
            )
            ocr_converter = _get_ocr_converter()
            with _converter_lock:
                result = ocr_converter.convert(tmp_path)
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
