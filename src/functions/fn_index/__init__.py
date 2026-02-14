"""fn-index — Stage 2: Markdown → AI Search index.

Orchestrates chunking, embedding, and indexing of a processed KB article.

Steps:
    1. Read ``article.md`` from the article directory
    2. Chunk by Markdown headers via :mod:`fn_index.chunker`
    3. Embed all chunks via :mod:`fn_index.embedder`
    4. Push to AI Search via :mod:`fn_index.indexer`
"""

from __future__ import annotations

import logging
from pathlib import Path

from fn_index import chunker, embedder, indexer

logger = logging.getLogger(__name__)


def run(article_path: str) -> None:
    """Index a single processed KB article into Azure AI Search.

    Parameters
    ----------
    article_path:
        Path to the processed article folder (contains ``article.md`` + ``images/``).
    """
    article_dir = Path(article_path).resolve()
    article_id = article_dir.name

    logger.info("fn-index: %s", article_id)

    # 1. Read article.md
    article_md = article_dir / "article.md"
    if not article_md.exists():
        raise FileNotFoundError(f"article.md not found in {article_dir}")
    markdown = article_md.read_text(encoding="utf-8")

    # 2. Chunk
    chunks = chunker.chunk_article(markdown)
    logger.info("Chunked into %d sections", len(chunks))

    # 3. Embed
    embedded_chunks = embedder.embed_chunks(chunks)
    logger.info("Embedded %d chunks", len(embedded_chunks))

    # 4. Index
    indexer.ensure_index_exists()
    indexer.index_chunks(article_id, embedded_chunks)
    logger.info("fn-index complete: %s (%d chunks indexed)", article_id, len(embedded_chunks))
