"""Tests for GroundingResponseMiddleware.

Verifies that grounded search answers gain deterministic source and image
markers only when the model omitted them.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_framework import ChatResponse, Content, Message

from agent.grounding_middleware import GroundingResponseMiddleware


def _make_search_result_payload(*, include_images: bool = True) -> str:
    images = []
    if include_images:
        images = [{"name": "diagram.png", "url": "/api/images/article-1/images/diagram.png"}]

    return json.dumps({
        "results": [{
            "ref_number": 1,
            "content": "Azure AI Search is a retrieval system.",
            "title": "Azure AI Search overview",
            "section_header": "Overview",
            "article_id": "article-1",
            "chunk_index": 0,
            "image_urls": ["images/diagram.png"] if include_images else [],
            "images": images,
        }],
        "summary": "One result",
    })


def _make_context(*, stream: bool = False, assistant_text: str, include_images: bool = True) -> MagicMock:
    context = MagicMock()
    context.stream = stream
    context.stream_result_hooks = []
    context.messages = [
        Message(
            role="tool",
            contents=[Content.from_function_result(call_id="call-1", result=_make_search_result_payload(include_images=include_images))],
        )
    ]
    context.result = ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(assistant_text)])])
    return context


class TestGroundingResponseMiddleware:
    """Test post-generation grounding fallbacks."""

    @pytest.mark.asyncio
    async def test_appends_sources_and_image_when_missing(self) -> None:
        context = _make_context(
            assistant_text="Azure AI Search is Microsoft Azure's search and retrieval system.",
        )

        middleware = GroundingResponseMiddleware()
        next_fn = AsyncMock()

        await middleware.process(context, next_fn)

        text = context.result.messages[0].text
        assert "Sources: [Ref #1]" in text
        assert "Relevant image:" in text
        assert "/api/images/article-1/images/diagram.png" in text
        next_fn.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_preserves_existing_citation_and_image_markers(self) -> None:
        context = _make_context(
            assistant_text=(
                "Azure AI Search helps with retrieval [Ref #1].\n\n"
                "![Diagram](/api/images/article-1/images/diagram.png)"
            ),
        )

        middleware = GroundingResponseMiddleware()
        next_fn = AsyncMock()

        await middleware.process(context, next_fn)

        text = context.result.messages[0].text
        assert text.count("Sources:") == 0
        assert text.count("Relevant image:") == 0

    @pytest.mark.asyncio
    async def test_appends_only_sources_when_no_images_exist(self) -> None:
        context = _make_context(
            assistant_text="Azure AI Search provides indexing and retrieval.",
            include_images=False,
        )

        middleware = GroundingResponseMiddleware()
        next_fn = AsyncMock()

        await middleware.process(context, next_fn)

        text = context.result.messages[0].text
        assert "Sources: [Ref #1]" in text
        assert "Relevant image:" not in text

    @pytest.mark.asyncio
    async def test_registers_stream_result_hook(self) -> None:
        context = _make_context(
            stream=True,
            assistant_text="Azure AI Search provides indexing and retrieval.",
        )

        middleware = GroundingResponseMiddleware()
        next_fn = AsyncMock()

        await middleware.process(context, next_fn)

        assert len(context.stream_result_hooks) == 1
        hooked_response = context.stream_result_hooks[0](context.result)
        assert "Sources: [Ref #1]" in hooked_response.messages[0].text