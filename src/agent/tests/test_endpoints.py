"""FastAPI endpoint tests for the KB Agent server.

These tests use httpx.AsyncClient + FastAPI's ASGITransport so they
exercise the real HTTP layer (routing, serialisation, error handling)
without needing a running server or Azure credentials — the agent is
mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Patch the agent before importing the app — lifespan creates the real one
_mock_agent = AsyncMock()


@pytest.fixture(autouse=True)
def _patch_agent(monkeypatch):
    """Replace the global ``agent`` with a mock for every test."""
    import main as _mod

    monkeypatch.setattr(_mod, "agent", _mock_agent)
    _mock_agent.reset_mock()
    _mock_agent.run = AsyncMock(return_value="mocked response")

    # Provide a default run_stream that yields the full response in one chunk.
    # AsyncMock auto-creates attributes so hasattr() always returns True;
    # setting a real async generator avoids "'NoneType' not callable" errors.
    async def _default_stream(inp):
        yield "mocked response"

    _mock_agent.run_stream = _default_stream


@pytest.fixture
def transport():
    """ASGI transport wrapping the FastAPI app (no lifespan events)."""
    from main import app

    return ASGITransport(app=app)


@pytest_asyncio.fixture
async def client(transport):
    """Async HTTP client bound to the FastAPI app."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_body(self, client):
        body = (await client.get("/health")).json()
        assert body["status"] == "healthy"
        assert body["entities_count"] == 1


# -----------------------------------------------------------------------
# Entities
# -----------------------------------------------------------------------


class TestEntitiesEndpoint:
    """Tests for GET /v1/entities."""

    @pytest.mark.asyncio
    async def test_entities_returns_agent(self, client):
        body = (await client.get("/v1/entities")).json()
        assert len(body["entities"]) == 1
        ent = body["entities"][0]
        assert ent["id"] == "kb-agent"
        assert ent["type"] == "agent"
        assert "search_knowledge_base" in ent["tools"]


# -----------------------------------------------------------------------
# Non-streaming responses
# -----------------------------------------------------------------------


class TestNonStreamingResponse:
    """Tests for POST /v1/responses (stream=false)."""

    @pytest.mark.asyncio
    async def test_returns_200(self, client):
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": False},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_shape(self, client):
        body = (
            await client.post(
                "/v1/responses",
                json={"input": "hello"},
            )
        ).json()
        assert body["object"] == "response"
        assert body["model"] == "kb-agent"
        assert len(body["output"]) == 1
        msg = body["output"][0]
        assert msg["role"] == "assistant"
        assert msg["content"][0]["text"] == "mocked response"

    @pytest.mark.asyncio
    async def test_instructions_prepended(self, client):
        await client.post(
            "/v1/responses",
            json={"input": "hello", "instructions": "be concise"},
        )
        call_args = _mock_agent.run.call_args
        full_input = call_args[0][0]
        assert "[Context]" in full_input
        assert "be concise" in full_input


# -----------------------------------------------------------------------
# Streaming responses
# -----------------------------------------------------------------------


class TestStreamingResponse:
    """Tests for POST /v1/responses (stream=true)."""

    def _parse_sse_events(self, text: str) -> list[tuple[str, dict]]:
        """Parse SSE text into a list of (event_type, data_dict) tuples."""
        events = []
        current_event = None
        for line in text.split("\n"):
            if line.startswith("event: "):
                current_event = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
                events.append((current_event, data))
                current_event = None
        return events

    @pytest.mark.asyncio
    async def test_streaming_content_type(self, client):
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": True},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_streaming_has_completed_event(self, client):
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": True},
        )
        events = self._parse_sse_events(resp.text)
        event_types = [e[0] for e in events]
        assert "response.completed" in event_types

    @pytest.mark.asyncio
    async def test_streaming_completion_event(self, client):
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": True},
        )
        events = self._parse_sse_events(resp.text)
        completed = [e[1] for e in events if e[0] == "response.completed"]
        assert len(completed) == 1
        # response.completed wraps the response object under "response" key
        resp_obj = completed[0]["response"]
        assert resp_obj["object"] == "response"
        assert resp_obj["status"] == "completed"
        assert len(resp_obj["output"]) == 1

    @pytest.mark.asyncio
    async def test_streaming_with_run_stream(self, client):
        """When the agent has ``run_stream``, chunks are sent as deltas."""

        async def _stream(inp):
            for word in ["one", "two"]:
                yield word

        _mock_agent.run_stream = _stream

        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": True},
        )
        events = self._parse_sse_events(resp.text)
        delta_events = [e[1] for e in events if e[0] == "response.output_text.delta"]
        assert len(delta_events) == 2
        assert delta_events[0]["delta"] == "one"
        assert delta_events[1]["delta"] == "two"

    @pytest.mark.asyncio
    async def test_streaming_event_sequence(self, client):
        """Verify the correct sequence of SSE events."""
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello", "stream": True},
        )
        events = self._parse_sse_events(resp.text)
        event_types = [e[0] for e in events]
        assert event_types[0] == "response.created"
        assert event_types[1] == "response.output_item.added"
        assert event_types[2] == "response.content_part.added"
        assert "response.output_text.delta" in event_types
        assert event_types[-1] == "response.completed"


# -----------------------------------------------------------------------
# Error handling
# -----------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error propagation."""

    @pytest.mark.asyncio
    async def test_agent_error_returns_500(self, client):
        _mock_agent.run = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await client.post(
            "/v1/responses",
            json={"input": "hello"},
        )
        assert resp.status_code == 500
        assert "boom" in resp.json()["detail"]
