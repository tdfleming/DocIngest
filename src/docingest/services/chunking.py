import re

import structlog

from docingest.config import settings
from docingest.services.embedding import count_tokens

log = structlog.get_logger()

# Matches Markdown headings ## and ###
_HEADING_PATTERN = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


def _split_by_headings(markdown: str) -> list[dict]:
    """Pass 1: Split Markdown into sections by ## and ### headings.

    Returns a list of sections, each with heading_chain and text.
    """
    sections: list[dict] = []
    heading_stack: list[str] = []
    current_text_lines: list[str] = []
    current_level = 0

    for line in markdown.splitlines(keepends=True):
        match = _HEADING_PATTERN.match(line.rstrip())
        if match:
            # Flush current section
            if current_text_lines:
                sections.append({
                    "heading_chain": list(heading_stack),
                    "text": "".join(current_text_lines).strip(),
                })
                current_text_lines = []

            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Update heading stack
            if level <= current_level:
                heading_stack = heading_stack[: level - 2]
            heading_stack.append(heading_text)
            current_level = level
        else:
            current_text_lines.append(line)

    # Flush final section
    if current_text_lines:
        text = "".join(current_text_lines).strip()
        if text:
            sections.append({
                "heading_chain": list(heading_stack),
                "text": text,
            })

    # Handle case where there are no headings at all
    if not sections and markdown.strip():
        sections.append({"heading_chain": [], "text": markdown.strip()})

    return sections


def _semantic_sub_split(text: str, max_tokens: int, overlap_pct: int) -> list[str]:
    """Pass 2: Split large sections into smaller chunks.

    Uses paragraph boundaries first, then sentence boundaries as fallback.
    Adds overlap between chunks for context preservation.
    """
    tokens = count_tokens(text)
    if tokens <= max_tokens:
        return [text]

    # Split by paragraphs (double newline)
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) == 1:
        # Fallback: split by sentences
        paragraphs = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0
    overlap_tokens = int(max_tokens * overlap_pct / 100)

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if current_tokens + para_tokens > max_tokens and current_chunk:
            chunks.append("\n\n".join(current_chunk))

            # Keep tail paragraphs for overlap
            overlap_text: list[str] = []
            overlap_count = 0
            for p in reversed(current_chunk):
                t = count_tokens(p)
                if overlap_count + t > overlap_tokens:
                    break
                overlap_text.insert(0, p)
                overlap_count += t

            current_chunk = overlap_text
            current_tokens = overlap_count

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def chunk_document(
    markdown: str,
    *,
    max_tokens: int | None = None,
    overlap_percent: int | None = None,
) -> list[dict]:
    """Two-pass chunking: structural split then semantic sub-split.

    Args:
        markdown: The markdown text to chunk.
        max_tokens: Optional per-document override for max tokens per chunk.
            Falls back to settings.chunk_max_tokens when None.
        overlap_percent: Optional per-document override for overlap percentage.
            Falls back to settings.chunk_overlap_percent when None.

    Returns list of chunks with metadata:
        {chunk_text, heading_chain, chunk_index, char_offset, token_count}
    """
    _max_tokens = max_tokens if max_tokens is not None else settings.chunk_max_tokens
    _overlap_pct = overlap_percent if overlap_percent is not None else settings.chunk_overlap_percent

    sections = _split_by_headings(markdown)

    all_chunks: list[dict] = []
    chunk_index = 0
    char_offset = 0

    for section in sections:
        sub_chunks = _semantic_sub_split(
            section["text"],
            max_tokens=_max_tokens,
            overlap_pct=_overlap_pct,
        )

        for sub_chunk in sub_chunks:
            token_count = count_tokens(sub_chunk)
            all_chunks.append({
                "chunk_text": sub_chunk,
                "heading_chain": section["heading_chain"],
                "chunk_index": chunk_index,
                "char_offset": char_offset,
                "token_count": token_count,
            })
            chunk_index += 1
            char_offset += len(sub_chunk)

    log.info("chunking complete", total_chunks=len(all_chunks))
    return all_chunks
