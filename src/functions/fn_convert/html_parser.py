"""HTML DOM parsing — extract image map and link map using BeautifulSoup.

Parses source HTML articles to extract:
- **Image map**: ordered list of ``(preceding_text, image_filename_stem)`` pairs —
  used later to insert image description blocks at the correct positions in the
  CU-generated Markdown.
- **Link map**: list of ``(link_text, url)`` pairs — used to recover hyperlinks
  that CU strips from HTML input.

Handles both DITA-generated HTML (``div.itemgroup.info`` step images) and
standard HTML (inline ``<img>`` / ``<a><img></a>`` patterns).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_image_map(html_path: Path) -> list[tuple[str, str]]:
    """Return ordered ``(preceding_text, image_filename_stem)`` pairs.

    ``preceding_text`` is a snippet of text that appears in the document
    just before the image — used for position-matching in the CU Markdown.

    ``image_filename_stem`` is the filename without extension (e.g.
    ``zzy1770827101433`` from ``zzy1770827101433.image``).
    """
    soup = _parse(html_path)
    result: list[tuple[str, str]] = []

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue

        stem = Path(src).stem
        preceding = _find_preceding_text(img)

        if preceding:
            result.append((preceding, stem))
        else:
            logger.warning("No preceding text found for image %s in %s", stem, html_path.name)

    return result


def extract_link_map(html_path: Path) -> list[tuple[str, str]]:
    """Return ``(link_text, url)`` pairs, excluding image-wrapping links.

    Skips ``<a>`` tags that:
    - Wrap an ``<img>`` (image enlargement links)
    - Point to ``#`` anchors (internal navigation)
    - Have empty link text
    """
    soup = _parse(html_path)
    result: list[tuple[str, str]] = []

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]

        # Skip anchors, image wrappers, and javascript
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        if a_tag.find("img"):
            continue

        text = _normalize(a_tag.get_text())
        if text and href:
            result.append((text, href))

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse(html_path: Path) -> BeautifulSoup:
    """Parse an HTML file into a BeautifulSoup tree."""
    return BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")


def _normalize(text: str) -> str:
    """Collapse all whitespace (including ``\\xa0``) and strip."""
    return re.sub(r"[\s\xa0]+", " ", text).strip()


def _find_preceding_text(img: Tag) -> str:
    """Find text that precedes *img* for position-matching in CU Markdown.

    Strategy 1 — **DITA step structure**: if the image is inside a
    ``div.itemgroup.info`` block within a ``li.step``, use the step
    command text (``span.ph.cmd``).

    Strategy 2 — **General**: walk up the DOM tree and, at each level,
    scan previous siblings for the nearest element with meaningful text.
    """
    # ── Strategy 1: DITA step ──────────────────────────────────────────
    step_li = img.find_parent("li", class_=lambda c: c and "step" in c)
    if step_li:
        cmd = step_li.find("span", class_=lambda c: c and "cmd" in c)
        if cmd:
            return _normalize(cmd.get_text())

    # ── Strategy 2: Walk up + back ─────────────────────────────────────
    for ancestor in img.parents:
        if ancestor.name in ("body", "html", "[document]"):
            # Reached top level — search siblings at this level
            break

        for sibling in ancestor.previous_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if _is_image_only(sibling):
                continue
            text = _normalize(sibling.get_text())
            if len(text) > 10:
                # Return last 200 chars for a compact but unique snippet
                return text[-200:]

    # ── Fallback at body level ─────────────────────────────────────────
    # If the image container (e.g. <a>) is a direct child of <body>,
    # we didn't enter the loop above.  Search from the image container.
    container = img.parent
    if container:
        for sibling in container.previous_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag):
                if _is_image_only(sibling):
                    continue
                text = _normalize(sibling.get_text())
                if len(text) > 10:
                    return text[-200:]

    return ""


def _is_image_only(element: Tag) -> bool:
    """Return ``True`` if *element* contains only image(s) with no meaningful text."""
    if not isinstance(element, Tag):
        return False
    text = _normalize(element.get_text())
    # Subtract img alt texts
    for child_img in element.find_all("img"):
        alt = child_img.get("alt", "")
        if alt:
            text = text.replace(alt.strip(), "", 1).strip()
    return len(text) < 5
