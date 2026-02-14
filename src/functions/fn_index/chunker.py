"""Markdown chunker — split by headers and extract image refs per chunk.

Splits ``article.md`` by Markdown headers (H1, H2, H3).  Each header-delimited
section becomes one chunk.  Image references matching the pattern
``[Image: <name>](images/<name>.png)`` are extracted per chunk.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Regex for image references in the format > **[Image: stem](images/stem.png)**
_IMAGE_REF_RE = re.compile(
    r"\[Image:\s*([^\]]+)\]\(images/([^)]+\.png)\)"
)

# Regex matching a Markdown header line (# / ## / ### at line start)
_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


@dataclass
class Chunk:
    """A single chunk of article content."""

    content: str
    title: str  # Article title (H1)
    section_header: str  # H2/H3 for this chunk (empty for the intro/H1 chunk)
    image_refs: list[str] = field(default_factory=list)  # e.g. ["img1.png"]


def chunk_article(markdown: str) -> list[Chunk]:
    """Split Markdown text into header-delimited chunks.

    Parameters
    ----------
    markdown:
        Full Markdown text of a processed article.

    Returns
    -------
    list[Chunk]
        Ordered list of chunks.  The first chunk is the intro/preamble
        before the first header (may be empty and is skipped).
    """
    if not markdown.strip():
        return []

    # Find all header positions
    headers: list[tuple[int, int, str, str]] = []  # (start, level, title, full_match)
    for m in _HEADER_RE.finditer(markdown):
        level = len(m.group(1))
        header_text = m.group(2).strip()
        headers.append((m.start(), level, header_text, m.group(0)))

    # Extract H1 title (first H1 header)
    article_title = ""
    for _, level, text, _ in headers:
        if level == 1:
            article_title = text
            break

    # Split into sections by header boundaries
    sections: list[tuple[int, str, str]] = []  # (level, header_text, content)

    if not headers:
        # No headers — entire document is one chunk
        return [
            _build_chunk(markdown.strip(), article_title, ""),
        ]

    # Preamble before first header
    preamble = markdown[: headers[0][0]].strip()
    if preamble:
        sections.append((0, "", preamble))

    # Each header section
    for i, (start, level, header_text, full_match) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(markdown)
        section_content = markdown[start:end].strip()
        sections.append((level, header_text, section_content))

    # Build chunks — track the current H2 context for H3 chunks
    chunks: list[Chunk] = []
    current_h2 = ""

    for level, header_text, content in sections:
        if not content:
            continue

        if level == 2:
            current_h2 = header_text
        elif level == 3:
            # H3 inherits the parent H2
            if current_h2 and current_h2 not in header_text:
                header_text = f"{current_h2} > {header_text}"

        section_header = header_text if level >= 2 else ""
        chunks.append(_build_chunk(content, article_title, section_header))

    return chunks


def _build_chunk(content: str, title: str, section_header: str) -> Chunk:
    """Create a Chunk with image refs extracted from the content."""
    image_refs = [m.group(2) for m in _IMAGE_REF_RE.finditer(content)]
    return Chunk(
        content=content,
        title=title,
        section_header=section_header,
        image_refs=image_refs,
    )

