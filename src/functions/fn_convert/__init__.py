"""fn-convert — Stage 1: HTML → Markdown + images.

Orchestrates the conversion of a source KB article (HTML + images) into
clean Markdown with AI-generated image descriptions.

Steps:
    1a. Send HTML to CU ``prebuilt-documentSearch`` → Markdown + summary
    1b. Parse HTML DOM → image map + link map
    2.  Send each image to CU ``kb_image_analyzer`` → descriptions
    3.  Merge: recover hyperlinks, insert image blocks at correct positions
    4.  Write ``article.md`` + copy images as PNGs to the output directory
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fn_convert import cu_images, cu_text, html_parser, merge

logger = logging.getLogger(__name__)


def run(article_path: str, output_path: str) -> None:
    """Convert a single KB article from HTML to Markdown with image descriptions.

    Parameters
    ----------
    article_path:
        Path to the source article folder (contains HTML + image files).
    output_path:
        Path to write the processed article (``article.md`` + ``images/``).
    """
    article_dir = Path(article_path).resolve()
    output_dir = Path(output_path).resolve()

    logger.info("fn-convert: %s → %s", article_dir.name, output_dir)

    # ── 1a. Text extraction via CU ─────────────────────────────────────
    html_file = _find_html(article_dir)
    text_result = cu_text.extract_text(html_file)
    logger.info("Extracted %d chars of Markdown from %s", len(text_result.markdown), html_file.name)

    # ── 1b. HTML DOM parsing ───────────────────────────────────────────
    image_map = html_parser.extract_image_map(html_file)
    link_map = html_parser.extract_link_map(html_file)
    logger.info("HTML DOM: %d images, %d links", len(image_map), len(link_map))

    # ── 2. Image analysis via CU ───────────────────────────────────────
    unique_image_paths = _resolve_image_paths(article_dir, image_map)
    analyses = cu_images.analyze_all_images(unique_image_paths)
    logger.info("Analyzed %d images", len(analyses))

    # ── 3. Merge ───────────────────────────────────────────────────────
    markdown = merge.recover_links(text_result.markdown, link_map)
    markdown = merge.insert_image_blocks(markdown, image_map, analyses)

    # ── 4. Write outputs ───────────────────────────────────────────────
    _write_outputs(output_dir, markdown, text_result.summary, unique_image_paths)
    logger.info("fn-convert complete: %s", article_dir.name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_html(article_dir: Path) -> Path:
    """Find the primary HTML file in an article directory.

    Checks ``index.html`` first (DITA convention), then falls back to
    the first ``.html`` file (excluding base64 variants and
    Windows security zone markers).
    """
    index = article_dir / "index.html"
    if index.exists():
        return index

    html_files = [
        f
        for f in article_dir.glob("*.html")
        if "base64" not in f.name and ":" not in f.name
    ]
    if html_files:
        return sorted(html_files)[0]

    raise FileNotFoundError(f"No HTML file found in {article_dir}")


def _resolve_image_paths(
    article_dir: Path,
    image_map: list[tuple[str, str]],
) -> list[Path]:
    """Resolve unique image stems from the image map to actual file paths.

    Searches for each stem in:
    1. ``article_dir/<stem>.image``  (DITA articles)
    2. ``article_dir/images/<stem>.png``  (standard HTML)
    3. ``article_dir/<stem>.png``
    4. Glob fallback: ``article_dir/**/<stem>.*``

    Returns a deduplicated, ordered list of resolved paths.
    """
    # Preserve insertion order, deduplicate
    seen: set[str] = set()
    stems: list[str] = []
    for _, stem in image_map:
        if stem not in seen:
            seen.add(stem)
            stems.append(stem)

    paths: list[Path] = []
    for stem in stems:
        candidates = [
            article_dir / f"{stem}.image",
            article_dir / "images" / f"{stem}.png",
            article_dir / f"{stem}.png",
        ]
        found = next((c for c in candidates if c.exists()), None)
        if found:
            paths.append(found)
        else:
            # Glob for any extension (skip Zone.Identifier etc.)
            matches = [
                m
                for m in article_dir.rglob(f"{stem}.*")
                if ":" not in m.name
            ]
            if matches:
                paths.append(matches[0])
            else:
                logger.warning("Image file not found for stem %s in %s", stem, article_dir)

    return paths


def _write_outputs(
    output_dir: Path,
    markdown: str,
    summary: str,
    image_paths: list[Path],
) -> None:
    """Write ``article.md``, ``summary.txt``, and copy images as PNGs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Write article.md
    (output_dir / "article.md").write_text(markdown, encoding="utf-8")
    logger.info("Wrote article.md (%d chars)", len(markdown))

    # Write summary.txt
    if summary:
        (output_dir / "summary.txt").write_text(summary, encoding="utf-8")
        logger.info("Wrote summary.txt (%d chars)", len(summary))

    # Copy images → images/<stem>.png
    for img_path in image_paths:
        dest = images_dir / f"{img_path.stem}.png"
        shutil.copy2(img_path, dest)
        logger.debug("Copied %s → %s", img_path.name, dest.name)
