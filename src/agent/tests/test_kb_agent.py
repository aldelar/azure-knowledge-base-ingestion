"""Tests for the KB Search Agent (Microsoft Agent Framework)."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.kb_agent import (
    AgentResponse,
    Citation,
    _SYSTEM_PROMPT,
    create_agent,
    search_knowledge_base,
)
from agent.search_tool import SearchResult


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

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
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

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
    def test_includes_citation_fields(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        """Function result includes chunk_index and image_urls for citation extraction."""
        mock_search.return_value = [
            SearchResult(
                id="a_0", article_id="a", chunk_index=3,
                content="C", title="T", section_header="S",
                image_urls=["images/fig.png"], score=0.5,
            )
        ]
        mock_get_url.return_value = "/api/images/a/images/fig.png"

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert parsed[0]["article_id"] == "a"
        assert parsed[0]["chunk_index"] == 3
        assert parsed[0]["image_urls"] == ["images/fig.png"]

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
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

    @patch("agent.kb_agent.search_kb")
    def test_handles_search_error(self, mock_search: MagicMock) -> None:
        mock_search.side_effect = RuntimeError("connection error")

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert "error" in parsed


# ---------------------------------------------------------------------------
# create_agent() factory tests
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """Test the create_agent factory function."""

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_returns_chat_agent(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() returns a ChatAgent instance."""
        mock_agent_instance = MagicMock()
        mock_agent_cls.return_value = mock_agent_instance

        agent = create_agent()

        assert agent is mock_agent_instance
        mock_credential.assert_called_once()
        mock_client_cls.assert_called_once()
        mock_agent_cls.assert_called_once()

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_has_search_tool(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures the search tool."""
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert search_knowledge_base in call_kwargs.kwargs["tools"]

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_name(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() sets the agent name."""
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["name"] == "KBSearchAgent"

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_client_uses_vision_middleware(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures vision middleware on the client."""
        create_agent()

        call_kwargs = mock_client_cls.call_args
        middleware = call_kwargs.kwargs["middleware"]
        assert len(middleware) == 1
        from agent.vision_middleware import VisionImageMiddleware
        assert isinstance(middleware[0], VisionImageMiddleware)

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_uses_default_credential(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() uses DefaultAzureCredential."""
        create_agent()

        mock_credential.assert_called_once()
        client_kwargs = mock_client_cls.call_args.kwargs
        assert client_kwargs["credential"] is mock_credential.return_value

    @patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key-123"})
    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    def test_uses_api_key_when_provided(
        self,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() uses API key when AZURE_OPENAI_API_KEY is set."""
        create_agent()

        client_kwargs = mock_client_cls.call_args.kwargs
        assert client_kwargs["api_key"] == "test-key-123"
        assert "credential" not in client_kwargs
