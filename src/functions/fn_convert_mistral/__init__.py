"""fn-convert (Mistral) — Stage 1: HTML → Markdown + images via Mistral Document AI.

Orchestrates the conversion of a source KB article (HTML + images) into
clean Markdown with AI-generated image descriptions using Mistral Document AI
for OCR and GPT-4.1 vision for image analysis.

Steps:
    1. Render HTML to PDF with ``[[IMG:filename]]`` markers (Playwright)
    2. Send PDF to Mistral Document AI OCR → Markdown
    3. Scan OCR Markdown for ``[[IMG:...]]`` markers → image map
    4. Describe each unique image via GPT-4.1 vision
    5. Merge: replace markers with image blocks, recover hyperlinks, copy images

This module shares the same input/output contract as ``fn_convert_cu``:
    - Input: ``article_path`` — folder containing HTML + images
    - Output: ``article_path`` — folder with ``article.md`` + ``images/``
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fn_convert_mistral import describe_images, map_images, merge, mistral_ocr, render_pdf
from shared.config import config

logger = logging.getLogger(__name__)


def run(article_path: str, output_path: str) -> None:
    """Convert a single KB article from HTML to Markdown using Mistral Document AI.

    Parameters
    ----------
    article_path:
        Path to the source article folder (contains HTML + image files).
    output_path:
        Path to write the processed article (``article.md`` + ``images/``).
    """
    article_dir = Path(article_path).resolve()
    output_dir = Path(output_path).resolve()

    logger.info("fn-convert (mistral): %s → %s", article_dir.name, output_dir)

    endpoint = config.ai_services_endpoint
    mistral_deployment = config.mistral_deployment_name
    # Use gpt-4.1 for image descriptions (same model as CU kb-image-analyzer)
    gpt_deployment = "gpt-4.1"

    # ── 1. Render HTML to PDF with image markers ──────────────────────
    html_file = _find_html(article_dir)

    with tempfile.TemporaryDirectory(prefix="mistral-convert-") as tmp:
        pdf_path = Path(tmp) / "article.pdf"
        render_pdf.render_pdf(html_file, pdf_path)
        logger.info("PDF rendered: %d bytes", pdf_path.stat().st_size)

        # ── 2. Send PDF to Mistral OCR ────────────────────────────────
        ocr_response = mistral_ocr.ocr_pdf(pdf_path, endpoint, mistral_deployment)

    pages = ocr_response.get("pages", [])
    if not pages:
        raise ValueError(f"Mistral OCR returned no pages for {html_file.name}")
    pages_markdown = [p.get("markdown", "") for p in pages]
    logger.info("OCR: %d pages extracted", len(pages))

    # ── 3. Scan for image markers ─────────────────────────────────────
    full_markdown, source_filenames = map_images.find_image_markers(pages_markdown)
    unique_filenames = list(dict.fromkeys(source_filenames))
    logger.info("Found %d image markers (%d unique)", len(source_filenames), len(unique_filenames))

    # ── 4. Describe images with GPT-4.1 vision ───────────────────────
    image_mapping = {f: f for f in unique_filenames}
    descriptions = describe_images.describe_all_images(
        image_mapping=image_mapping,
        staging_dir=article_dir,
        endpoint=endpoint,
        deployment=gpt_deployment,
    )
    logger.info("Described %d images", len(descriptions))

    # ── 5. Merge: markers → image blocks, recover links, copy images ─
    link_map = merge.extract_link_map(html_file)
    merge.merge_article(
        ocr_markdown=full_markdown,
        source_filenames=unique_filenames,
        descriptions=descriptions,
        staging_dir=article_dir,
        output_dir=output_dir,
        link_map=link_map,
    )
    logger.info("fn-convert (mistral) complete: %s", article_dir.name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_html(article_dir: Path) -> Path:
    """Find the primary HTML file in an article directory.

    Checks ``index.html`` first, then falls back to the first ``.html`` file
    (excluding base64 variants and Windows security zone markers).
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
