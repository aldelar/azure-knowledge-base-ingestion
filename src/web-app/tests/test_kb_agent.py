"""Tests for the KB Search Agent (Microsoft Agent Framework)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.kb_agent import (
    AgentResponse,
    Citation,
    KBAgent,
    _SYSTEM_PROMPT,
    _pending_citations,
    _pending_images,
    search_knowledge_base,
)
from app.agent.search_tool import SearchResult


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    """Test response dataclasses."""

    def test_citation(self) -> None:
        c = Citation(
            article_id="article-1",
            title="Test Article",
            section_header="Overview",
            chunk_index=0,
        )
        assert c.article_id == "article-1"
        assert c.title == "Test Article"

    def test_agent_response_defaults(self) -> None:
        r = AgentResponse(text="Hello")
        assert r.text == "Hello"
        assert r.citations == []
        assert r.images == []

    def test_agent_response_with_data(self) -> None:
        r = AgentResponse(
            text="Answer",
            citations=[Citation("a", "T", "S", 0)],
            images=["https://example.com/img.png"],
        )
        assert len(r.citations) == 1
        assert len(r.images) == 1


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Test the system prompt content."""

    def test_prompt_mentions_search_tool(self) -> None:
        assert "search_knowledge_base" in _SYSTEM_PROMPT

    def test_prompt_mentions_citations(self) -> None:
        assert "source" in _SYSTEM_PROMPT.lower() or "cite" in _SYSTEM_PROMPT.lower()

    def test_prompt_mentions_images(self) -> None:
        assert "image" in _SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------


class TestSearchKnowledgeBaseTool:
    """Test the search_knowledge_base tool function directly."""

    def setup_method(self) -> None:
        _pending_citations.clear()
        _pending_images.clear()

    @patch("app.agent.kb_agent.get_image_url")
    @patch("app.agent.kb_agent.search_kb")
    def test_returns_json_results(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = [
            SearchResult(
                id="article_0",
                article_id="article",
                chunk_index=0,
                content="Test content",
                title="Test Article",
                section_header="Section",
                image_urls=[],
                score=0.9,
            )
        ]
        mock_get_url.return_value = "/api/images/article/images/fig.png"

        result = search_knowledge_base("test query")
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["title"] == "Test Article"
        assert parsed[0]["content"] == "Test content"

    @patch("app.agent.kb_agent.get_image_url")
    @patch("app.agent.kb_agent.search_kb")
    def test_populates_citations(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = [
            SearchResult(
                id="a_0", article_id="a", chunk_index=0,
                content="C", title="T", section_header="S",
                image_urls=[], score=0.5,
            )
        ]
        mock_get_url.return_value = "/api/images/a/images/fig.png"

        search_knowledge_base("query")

        assert len(_pending_citations) == 1
        assert _pending_citations[0].article_id == "a"

    @patch("app.agent.kb_agent.get_image_url")
    @patch("app.agent.kb_agent.search_kb")
    def test_resolves_images(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = [
            SearchResult(
                id="a_0", article_id="article", chunk_index=0,
                content="C", title="T", section_header="S",
                image_urls=["images/fig.png"], score=0.5,
            )
        ]
        mock_get_url.return_value = "/api/images/article/images/fig.png"

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert len(parsed[0]["images"]) == 1
        assert "fig.png" in parsed[0]["images"][0]["url"]

    @patch("app.agent.kb_agent.search_kb")
    def test_handles_search_error(self, mock_search: MagicMock) -> None:
        mock_search.side_effect = RuntimeError("connection error")

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert "error" in parsed


# ---------------------------------------------------------------------------
# KBAgent tests
# ---------------------------------------------------------------------------


class TestKBAgentChat:
    """Test the KBAgent.chat method with mocked Agent Framework."""

    @patch("app.agent.kb_agent.ChatAgent")
    @patch("app.agent.kb_agent.AzureOpenAIChatClient")
    @patch("app.agent.kb_agent.DefaultAzureCredential")
    def _create_agent(
        self,
        mock_cred: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> tuple[KBAgent, MagicMock]:
        """Create a KBAgent with mocked framework components."""
        mock_agent_instance = MagicMock()
        mock_agent_cls.return_value = mock_agent_instance
        agent = KBAgent()
        return agent, mock_agent_instance

    @pytest.mark.asyncio
    async def test_direct_text_response(self) -> None:
        """Agent returns text from the framework response."""
        agent, mock_framework_agent = self._create_agent()

        mock_response = MagicMock()
        mock_response.text = "Here is your answer."
        mock_framework_agent.run = AsyncMock(return_value=mock_response)

        result = await agent.chat("Hello")

        assert result.text == "Here is your answer."
        assert result.citations == []
        assert result.images == []

    @pytest.mark.asyncio
    async def test_handles_agent_error(self) -> None:
        """Agent returns error message when framework raises."""
        agent, mock_framework_agent = self._create_agent()
        mock_framework_agent.run = AsyncMock(side_effect=Exception("API error"))

        result = await agent.chat("test question")

        assert "error" in result.text.lower()

    @pytest.mark.asyncio
    async def test_passes_thread(self) -> None:
        """Thread is forwarded to the framework agent."""
        from agent_framework import AgentThread

        agent, mock_framework_agent = self._create_agent()
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_framework_agent.run = AsyncMock(return_value=mock_response)

        thread = AgentThread()
        await agent.chat("question", thread=thread)

        call_kwargs = mock_framework_agent.run.call_args
        assert call_kwargs.kwargs["thread"] is thread

    @pytest.mark.asyncio
    async def test_none_text_becomes_empty_string(self) -> None:
        """If framework returns None text, it becomes empty string."""
        agent, mock_framework_agent = self._create_agent()
        mock_response = MagicMock()
        mock_response.text = None
        mock_framework_agent.run = AsyncMock(return_value=mock_response)

        result = await agent.chat("question")

        assert result.text == ""

    @pytest.mark.asyncio
    async def test_accumulators_reset_each_call(self) -> None:
        """Citations and images are reset between calls."""
        agent, mock_framework_agent = self._create_agent()

        # Simulate leftover state
        _pending_citations.append(Citation("old", "Old", "Old", 0))
        _pending_images.append("https://old.png")

        mock_response = MagicMock()
        mock_response.text = "fresh"
        mock_framework_agent.run = AsyncMock(return_value=mock_response)

        result = await agent.chat("new question")

        # Accumulators should have been cleared
        assert result.citations == []
        assert result.images == []
