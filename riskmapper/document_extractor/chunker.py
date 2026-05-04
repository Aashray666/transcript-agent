"""Document chunker — splits loaded documents into LLM-sized chunks.

Design principles:
1. SECTION-AWARE: Splits on detected section boundaries first.
   A section heading always starts a new chunk — never split mid-section
   if the section fits within the target size.

2. OVERLAP: Each chunk overlaps with the previous by ~200 chars.
   This prevents risks that straddle a chunk boundary from being missed.

3. SIZE-BOUNDED: Each chunk is ≤ MAX_CHUNK_CHARS (default 3000).
   Large sections are split further at paragraph boundaries.

4. PROVENANCE: Every chunk carries a ChunkMetadata object so the
   extractor knows exactly where in the document each risk came from.

5. GRACEFUL DEGRADATION: If section detection fails, falls back to
   paragraph-based splitting, then character-based splitting.
"""

from __future__ import annotations

import logging
import re

from riskmapper.document_extractor.schemas import ChunkMetadata, DocumentType

logger = logging.getLogger(__name__)

# Target chunk size in characters (~750-800 tokens at ~4 chars/token)
MAX_CHUNK_CHARS = 3000

# Overlap between consecutive chunks (prevents boundary misses)
OVERLAP_CHARS = 200

# Minimum chunk size — don't create tiny chunks
MIN_CHUNK_CHARS = 100


def chunk_document(
    text: str,
    document_name: str,
    document_type: DocumentType,
    detected_sections: list[str],
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[tuple[str, ChunkMetadata]]:
    """Split document text into overlapping, section-aware chunks.

    Args:
        text: Full document text (from document_loader).
        document_name: Original filename (for metadata).
        document_type: Type of document (for metadata).
        detected_sections: Section headings found by the loader.
        max_chunk_chars: Maximum characters per chunk.
        overlap_chars: Characters of overlap between consecutive chunks.

    Returns:
        List of (chunk_text, ChunkMetadata) tuples.
    """
    if not text.strip():
        logger.warning("Empty document text — returning no chunks")
        return []

    # Step 1: Split into sections
    raw_sections = _split_into_sections(text, detected_sections)
    logger.info(
        "Chunker | document=%s | raw_sections=%d | total_chars=%d",
        document_name, len(raw_sections), len(text),
    )

    # Step 2: Sub-split large sections
    raw_chunks: list[tuple[str, str]] = []  # (section_label, chunk_text)
    for section_label, section_text in raw_sections:
        if len(section_text) <= max_chunk_chars:
            raw_chunks.append((section_label, section_text))
        else:
            sub_chunks = _split_large_section(
                section_label, section_text, max_chunk_chars
            )
            raw_chunks.extend(sub_chunks)

    # Step 3: Add overlap between consecutive chunks
    overlapped = _add_overlap(raw_chunks, overlap_chars)

    # Step 4: Filter tiny chunks
    overlapped = [
        (label, text) for label, text in overlapped
        if len(text.strip()) >= MIN_CHUNK_CHARS
    ]

    # Step 5: Build ChunkMetadata
    total = len(overlapped)
    result: list[tuple[str, ChunkMetadata]] = []
    char_cursor = 0

    for idx, (section_label, chunk_text) in enumerate(overlapped):
        # Approximate char position in original document
        char_start = text.find(chunk_text[:50].strip(), char_cursor)
        if char_start == -1:
            char_start = char_cursor
        char_end = char_start + len(chunk_text)
        char_cursor = max(char_cursor, char_start)

        metadata = ChunkMetadata(
            chunk_id=f"chunk_{idx + 1:03d}",
            document_name=document_name,
            document_type=document_type,
            section_label=section_label,
            char_start=char_start,
            char_end=char_end,
            chunk_index=idx,
            total_chunks=total,
        )
        result.append((chunk_text, metadata))

    logger.info(
        "Chunker complete | chunks=%d | avg_chars=%.0f",
        len(result),
        sum(len(t) for t, _ in result) / max(len(result), 1),
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Patterns that mark the start of a new section in the text
_SECTION_SPLIT_PATTERNS = [
    re.compile(r"^\[SECTION:\s*.+?\]$", re.MULTILINE),
    re.compile(r"^\[PAGE \d+\]$", re.MULTILINE),
    re.compile(r"^#{1,4}\s+.+$", re.MULTILINE),
    re.compile(r"^(\d+\.)+\s+[A-Z].{5,60}$", re.MULTILINE),
    re.compile(r"^[A-Z][A-Z\s&,\-]{5,60}$", re.MULTILINE),
    re.compile(
        r"^(RISK FACTORS|MANAGEMENT.S DISCUSSION|FORWARD.LOOKING|"
        r"AUDIT FINDING|OBSERVATION|RECOMMENDATION|MANAGEMENT RESPONSE|"
        r"EXECUTIVE SUMMARY|CONCLUSION|OVERVIEW|INTRODUCTION)",
        re.MULTILINE | re.IGNORECASE,
    ),
]


def _split_into_sections(
    text: str,
    detected_sections: list[str],
) -> list[tuple[str, str]]:
    """Split text at section boundaries.

    Returns list of (section_label, section_text) tuples.
    Falls back to paragraph splitting if no sections detected.
    """
    if not detected_sections:
        return _split_by_paragraphs(text, "Document")

    # Build a combined pattern from all section headings
    # Escape special regex chars in section names
    escaped = [re.escape(s) for s in detected_sections[:50]]  # cap at 50
    combined = re.compile(
        r"(?=\[SECTION:\s*(?:" + "|".join(escaped) + r")\]|\[PAGE \d+\])",
        re.MULTILINE,
    )

    parts = combined.split(text)
    if len(parts) <= 1:
        # Pattern didn't match — fall back to heuristic splitting
        return _split_by_heuristic_headings(text)

    sections: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract section label from the first line
        first_line = part.split("\n")[0].strip()
        label = _clean_section_label(first_line)
        sections.append((label, part))

    return sections if sections else [("Document", text)]


def _split_by_heuristic_headings(text: str) -> list[tuple[str, str]]:
    """Split by any line that looks like a heading."""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_label = "Document"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        is_heading = any(p.match(stripped) for p in _SECTION_SPLIT_PATTERNS)

        if is_heading and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_label, body))
            current_label = _clean_section_label(stripped)
            current_lines = [line]
        else:
            current_lines.append(line)

    # Flush last section
    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_label, body))

    return sections if sections else [("Document", text)]


def _split_by_paragraphs(
    text: str,
    section_label: str,
) -> list[tuple[str, str]]:
    """Split text into paragraph-sized chunks."""
    paragraphs = re.split(r"\n{2,}", text)
    return [
        (section_label, para.strip())
        for para in paragraphs
        if para.strip()
    ]


def _split_large_section(
    section_label: str,
    section_text: str,
    max_chars: int,
) -> list[tuple[str, str]]:
    """Split a section that exceeds max_chars into smaller pieces.

    Tries paragraph boundaries first, then sentence boundaries,
    then hard character splits as a last resort.
    """
    # Try paragraph split first
    paragraphs = re.split(r"\n{2,}", section_text)
    if len(paragraphs) > 1:
        chunks = _group_paragraphs(paragraphs, section_label, max_chars)
        if chunks:
            return chunks

    # Try sentence split
    sentences = re.split(r"(?<=[.!?])\s+", section_text)
    if len(sentences) > 1:
        chunks = _group_sentences(sentences, section_label, max_chars)
        if chunks:
            return chunks

    # Hard split as last resort
    chunks = []
    for i in range(0, len(section_text), max_chars):
        part = section_text[i: i + max_chars]
        sub_label = f"{section_label} (part {i // max_chars + 1})"
        chunks.append((sub_label, part))
    return chunks


def _group_paragraphs(
    paragraphs: list[str],
    section_label: str,
    max_chars: int,
) -> list[tuple[str, str]]:
    """Group paragraphs into chunks that fit within max_chars."""
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_len = 0
    part_num = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if current_len + len(para) > max_chars and current:
            chunks.append((f"{section_label} (part {part_num})", "\n\n".join(current)))
            part_num += 1
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        label = f"{section_label} (part {part_num})" if part_num > 1 else section_label
        chunks.append((label, "\n\n".join(current)))

    return chunks


def _group_sentences(
    sentences: list[str],
    section_label: str,
    max_chars: int,
) -> list[tuple[str, str]]:
    """Group sentences into chunks that fit within max_chars."""
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_len = 0
    part_num = 1

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if current_len + len(sent) > max_chars and current:
            chunks.append((f"{section_label} (part {part_num})", " ".join(current)))
            part_num += 1
            current = [sent]
            current_len = len(sent)
        else:
            current.append(sent)
            current_len += len(sent)

    if current:
        label = f"{section_label} (part {part_num})" if part_num > 1 else section_label
        chunks.append((label, " ".join(current)))

    return chunks


def _add_overlap(
    chunks: list[tuple[str, str]],
    overlap_chars: int,
) -> list[tuple[str, str]]:
    """Prepend the tail of the previous chunk to each chunk.

    This ensures risks that straddle a chunk boundary are captured
    in at least one chunk.
    """
    if len(chunks) <= 1 or overlap_chars <= 0:
        return chunks

    result: list[tuple[str, str]] = [chunks[0]]

    for i in range(1, len(chunks)):
        prev_label, prev_text = chunks[i - 1]
        curr_label, curr_text = chunks[i]

        # Take the last `overlap_chars` of the previous chunk
        tail = prev_text[-overlap_chars:].strip()

        if tail:
            overlapped_text = f"[...continued from {prev_label}...]\n{tail}\n\n{curr_text}"
        else:
            overlapped_text = curr_text

        result.append((curr_label, overlapped_text))

    return result


def _clean_section_label(raw: str) -> str:
    """Clean a raw heading string into a readable section label."""
    # Remove [SECTION: ...] wrapper
    m = re.match(r"^\[SECTION:\s*(.+?)\]$", raw)
    if m:
        return m.group(1).strip()

    # Remove [PAGE N] wrapper
    m = re.match(r"^\[PAGE (\d+)\]$", raw)
    if m:
        return f"Page {m.group(1)}"

    # Remove markdown heading markers
    raw = re.sub(r"^#{1,4}\s+", "", raw)

    return raw.strip()[:80]  # Cap label length
