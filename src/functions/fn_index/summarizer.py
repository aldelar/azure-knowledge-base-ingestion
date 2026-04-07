"""Chunk summarizer — generate 1–2 sentence summaries via gpt-4.1-mini.

Used at index time to create compact per-chunk summaries stored in AI Search.
These summaries serve as compacted representations when the agent's
ToolResultCompactionStrategy replaces older tool output.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.client_factories import ChatBackend, create_chat_backend
from shared.config import config, get_config

if TYPE_CHECKING:
    from fn_index.chunker import Chunk

logger = logging.getLogger(__name__)

_client: ChatBackend | None = None


def _get_client() -> ChatBackend:
    """Lazy singleton for the chat backend."""
    global _client
    if _client is None:
        _client = create_chat_backend(config.summary_deployment_name)
    return _client


def summarize_chunk(chunk_content: str, title: str, section_header: str) -> str:
    """Generate a 1–2 sentence summary for a chunk.

    Parameters
    ----------
    chunk_content:
        The full text content of the chunk.
    title:
        Article title for context.
    section_header:
        Section header for context.

    Returns
    -------
    str
        A concise 1–2 sentence summary.
    """
    prompt = (
        f"Summarize the following knowledge base content in 1-2 sentences. "
        f"Be concise and capture the key information.\n\n"
        f"Article: {title}\n"
        f"Section: {section_header}\n\n"
        f"Content:\n{chunk_content[:2000]}"
    )
    try:
        client = _get_client()
        summary = client.complete(
            prompt=prompt,
            max_tokens=100,
            temperature=0.0,
        )
        logger.debug("Summarized chunk (%s > %s): %s", title, section_header, summary[:80])
        return summary
    except Exception:
        logger.warning("Failed to summarize chunk (%s > %s)", title, section_header, exc_info=True)
        return ""


def summarize_chunks(chunks: list[Chunk]) -> list[str]:
    """Generate summaries for all chunks.

    Parameters
    ----------
    chunks:
        List of Chunk objects from the chunker.

    Returns
    -------
    list[str]
        Summaries in the same order as the input chunks.
    """
    if not get_config().enable_chunk_summaries:
        logger.info("Chunk summaries disabled for current environment")
        return ["" for _ in chunks]

    summaries = []
    for chunk in chunks:
        summary = summarize_chunk(chunk.content, chunk.title, chunk.section_header)
        summaries.append(summary)
    logger.info("Generated %d chunk summaries", len(summaries))
    return summaries
