"""Merge OCR markdown + image descriptions + recovered links into final article.md.

Replaces ``[[IMG:<filename>]]`` markers with styled image blocks containing
GPT-generated descriptions, recovers hyperlinks from the source HTML, copies
source images to the output directory, and writes the final ``article.md``.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex to extract structured sections from GPT image descriptions.
# Handles numbered/unnumbered and bold/plain variants:
#   "1. **Description**:", "**Description**:", "Description:", "1. Description:"
_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+\.\s*)?(?:\*\*([^*]+)\*\*|(Description|UIElements|NavigationPath))\s*:[ \t]*",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Hyperlink recovery
# ---------------------------------------------------------------------------


def extract_link_map(html_path: Path) -> list[tuple[str, str]]:
    """Extract ``(link_text, url)`` pairs from ``<a>`` tags in HTML.

    Skips anchors (``#``), image-wrapper links, and empty link text.
    Uses regex so we don't need a BeautifulSoup dependency.
    """
    html = html_path.read_text(encoding="utf-8")
    results: list[tuple[str, str]] = []

    a_pattern = re.compile(
        r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for m in a_pattern.finditer(html):
        href = m.group(1).strip()
        inner_html = m.group(2).strip()

        # Skip anchors and javascript links
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        # Skip links that wrap images
        if "<img" in inner_html.lower():
            continue

        # Strip HTML tags from inner text
        text = re.sub(r"<[^>]+>", "", inner_html).strip()
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)

        if text and href:
            results.append((text, href))

    return results


def recover_links(markdown: str, link_map: list[tuple[str, str]]) -> str:
    """Re-inject hyperlinks into markdown using the link map.

    For each ``(link_text, url)`` pair, finds the *link_text* in *markdown*
    and wraps it as ``[link_text](url)``.  Skips texts that are already
    inside a Markdown link.  Only replaces the **first** occurrence.

    Uses word-boundary anchors at whichever end of the link text starts/ends
    with a word character, so ``"Foundry Tool"`` won't match inside
    ``"Foundry Tools"``.
    """
    result = markdown
    for text, url in link_map:
        if not text or not url:
            continue

        escaped_text = re.escape(text)

        # Apply \b only where the link text starts/ends with a word char
        prefix = r"\b" if re.match(r"\w", text) else ""
        suffix = r"\b" if re.search(r"\w$", text) else ""

        # Ensure we're not already inside a Markdown link [...](...)
        pattern = rf"(?<!\[){prefix}{escaped_text}{suffix}(?!\]\()"
        match = re.search(pattern, result)
        if match:
            replacement = f"[{text}]({url})"
            result = result[: match.start()] + replacement + result[match.end() :]
            logger.debug("Recovered link: %s → %s", text[:40], url[:60])
        else:
            logger.debug("Link text not found in markdown: %s", text[:40])

    return result


# ---------------------------------------------------------------------------
# Description cleanup
# ---------------------------------------------------------------------------


def _clean_description(raw: str) -> str:
    """Extract meaningful content from a structured GPT image description.

    The GPT prompt returns text in the form::

        1. **Description**: ...
        2. **UIElements**: None.
        3. **NavigationPath**: N/A.

    This function extracts each section, keeps Description always, and only
    includes UIElements / NavigationPath when they contain actual content
    (not ``None``, ``N/A``, or empty).
    """
    # Split by section headers: "1. **Description**:", "2. **UIElements**:", etc.
    parts = _SECTION_RE.split(raw)

    # If we don't find structured sections, return the raw text as-is
    # With 2 capture groups, we need at least 4 parts: [preamble, g1, g2, body]
    if len(parts) < 4:  # noqa: PLR2004 — need at least one header + body
        return raw.strip()

    # parts alternates: [preamble, group1_bold, group2_plain, body, ...]
    # Because re has two capture groups, each split entry alternates:
    # [preamble, bold_or_None, plain_or_None, body, bold_or_None, plain_or_None, body, ...]
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 2, 3):
        header = (parts[i] or parts[i + 1] or "").strip().lower()
        body = parts[i + 2].strip().rstrip(".")
        if header:
            sections[header] = body

    description = sections.get("description", "").strip()
    if not description:
        return raw.strip()

    lines = [description]

    ui_elements = sections.get("uielements", "").strip()
    if ui_elements and ui_elements.lower() not in ("none", "n/a", ""):
        lines.append(f"**UI Elements**: {ui_elements}")

    nav_path = sections.get("navigationpath", "").strip()
    if nav_path and nav_path.lower() not in ("none", "n/a", ""):
        lines.append(f"**Navigation Path**: {nav_path}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Article assembly
# ---------------------------------------------------------------------------


def merge_article(
    ocr_markdown: str,
    source_filenames: list[str],
    descriptions: dict[str, str],
    staging_dir: Path,
    output_dir: Path,
    link_map: list[tuple[str, str]] | None = None,
) -> None:
    """Merge OCR markdown with image descriptions and produce the final article.

    Replaces ``[[IMG:<filename>]]`` markers with styled image blocks,
    recovers hyperlinks from the source HTML, copies source images to the
    output directory, and writes the final ``article.md``.

    Args:
        ocr_markdown: Raw OCR markdown text with ``[[IMG:...]]`` markers.
        source_filenames: Unique list of source image filenames found via
            marker scanning.
        descriptions: Mapping from source filename to image description text.
        staging_dir: Directory containing the original staged images.
        output_dir: Directory where the final article and images will be written.
        link_map: Optional list of ``(text, url)`` pairs extracted from the
            source HTML for hyperlink recovery.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(parents=True, exist_ok=True)

    article = ocr_markdown

    # Replace [[IMG:filename]] markers with image description blocks
    for source_filename in source_filenames:
        stem = Path(source_filename).stem
        raw_description = descriptions.get(source_filename, "No description available.")
        description = _clean_description(raw_description)

        # Format each line of the description as a blockquote continuation
        desc_lines = description.split("\n")
        quoted = "\n".join(f"> {line}" for line in desc_lines)
        block = f"> **[Image: {stem}](images/{stem}.png)**\n{quoted}"

        marker = f"[[IMG:{source_filename}]]"
        article = article.replace(marker, block)

        # Copy source image to output
        source_in_images = staging_dir / "images" / source_filename
        source_direct = staging_dir / source_filename
        dest = output_dir / "images" / f"{stem}.png"

        if source_in_images.exists():
            shutil.copy2(source_in_images, dest)
        elif source_direct.exists():
            shutil.copy2(source_direct, dest)
        else:
            logger.warning("Source image not found: %s", source_filename)

    # Recover hyperlinks from the source HTML
    if link_map:
        article = recover_links(article, link_map)

    # Write final article
    (output_dir / "article.md").write_text(article, encoding="utf-8")
    logger.info("Article written: %s (%d chars)", output_dir / "article.md", len(article))
