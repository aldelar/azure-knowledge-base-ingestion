"""Merge CU Markdown + recovered links + image description blocks.

Combines three inputs into the final ``article.md``:

1. **CU Markdown** — text extracted from HTML by ``prebuilt-documentSearch``
2. **Recovered links** — hyperlinks parsed from the HTML DOM (CU strips URLs)
3. **Image blocks** — AI-generated image descriptions positioned by matching
   preceding text from the HTML DOM image map
"""

from __future__ import annotations

import logging
import re

from fn_convert.cu_images import ImageAnalysisResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recover_links(markdown: str, link_map: list[tuple[str, str]]) -> str:
    """Re-inject hyperlinks into CU Markdown using the link map.

    For each ``(link_text, url)`` pair, finds the *link_text* in *markdown*
    and wraps it as ``[link_text](url)``.  Skips texts that are already
    inside a Markdown link.

    Only replaces the **first** occurrence of each link text to avoid
    duplicating links for repeated phrases.
    """
    result = markdown
    for text, url in link_map:
        if not text or not url:
            continue

        # Skip if this text is already a Markdown link
        # Look for the text NOT preceded by [ or followed by ]( — crude but effective
        escaped_text = re.escape(text)
        # Match the text only if it's NOT already inside [...](...) 
        pattern = rf"(?<!\[){escaped_text}(?!\]\()"
        match = re.search(pattern, result)
        if match:
            replacement = f"[{text}]({url})"
            result = result[:match.start()] + replacement + result[match.end():]
            logger.debug("Recovered link: %s → %s", text[:40], url[:60])
        else:
            logger.debug("Link text not found in markdown: %s", text[:40])

    return result


def insert_image_blocks(
    markdown: str,
    image_map: list[tuple[str, str]],
    image_analyses: list[ImageAnalysisResult],
) -> str:
    """Insert image description blocks at the correct positions in Markdown.

    For each image in *image_map*, finds the ``preceding_text`` in *markdown*
    and inserts an image block immediately after it.  Uses fuzzy matching
    to handle minor CU text reformatting.

    Image block format (from architecture.md)::

        > **[Image: <stem>](images/<stem>.png)**
        > <description>
    """
    # Build a lookup: filename_stem → ImageAnalysisResult
    analysis_by_stem: dict[str, ImageAnalysisResult] = {
        a.filename_stem: a for a in image_analyses
    }

    result = markdown

    # Process images in reverse document order so insertions don't shift
    # positions of earlier matches
    for preceding_text, stem in reversed(image_map):
        analysis = analysis_by_stem.get(stem)
        if not analysis:
            logger.warning("No analysis found for image %s", stem)
            continue

        block = _format_image_block(stem, analysis)
        result = _insert_after_text(result, preceding_text, block)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_image_block(stem: str, analysis: ImageAnalysisResult) -> str:
    """Format an image description as a Markdown blockquote."""
    lines = [f"> **[Image: {stem}](images/{stem}.png)**"]
    if analysis.description:
        lines.append(f"> {analysis.description}")
    return "\n".join(lines)


def _insert_after_text(markdown: str, search_text: str, block: str) -> str:
    """Insert *block* after the first occurrence of *search_text* in *markdown*.

    Uses fuzzy matching: normalizes whitespace in both the search text and
    the markdown for comparison, but preserves original formatting.
    """
    # Normalize the search text for matching
    norm_search = _normalize_for_match(search_text)

    if not norm_search or len(norm_search) < 5:
        logger.warning("Search text too short for matching: %r", search_text)
        return markdown + "\n\n" + block

    # Build a regex pattern from the normalized search text that allows
    # flexible whitespace between words
    words = norm_search.split()
    # Use last 15 words for a focused match (long texts may have CU edits)
    if len(words) > 15:
        words = words[-15:]
    pattern = r"\s+".join(re.escape(w) for w in words)

    match = re.search(pattern, markdown, re.IGNORECASE)
    if match:
        # Find the end of the line containing the match
        end_pos = match.end()
        next_newline = markdown.find("\n", end_pos)
        if next_newline == -1:
            insert_pos = len(markdown)
        else:
            insert_pos = next_newline

        result = markdown[:insert_pos] + "\n\n" + block + markdown[insert_pos:]
        logger.debug("Inserted image block after: ...%s", norm_search[-40:])
        return result

    logger.warning("Could not find match for preceding text: ...%s", norm_search[-40:])
    # Fallback: append at the end
    return markdown + "\n\n" + block


def _normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching — lowercase, collapse whitespace,
    strip Markdown formatting characters."""
    text = re.sub(r"[\s\xa0]+", " ", text).strip().lower()
    # Remove bold/italic markers
    text = re.sub(r"[*_`]", "", text)
    return text
