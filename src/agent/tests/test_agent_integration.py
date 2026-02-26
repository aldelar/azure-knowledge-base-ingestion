"""Agent integration tests — run against a live agent endpoint.

These tests call a real agent (local or deployed) and verify the HTTP
contract.  They do NOT mock anything.

Usage (local):
    make test-agent-integration      # expects agent running on localhost:8088

Usage (Azure):
    make azure-test-agent            # reads AGENT_ENDPOINT from azd env

The ``AGENT_ENDPOINT`` env var controls the target.  When the URL uses
``https://`` an Entra bearer token is attached automatically.
"""

from __future__ import annotations

import json
import os
import time

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT", "http://localhost:8088")


def _get_headers() -> dict[str, str]:
    """Return request headers — adds Entra token for https endpoints."""
    if AGENT_ENDPOINT.startswith("https://"):
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base_url() -> str:
    return AGENT_ENDPOINT.rstrip("/")


@pytest.fixture(scope="module")
def headers() -> dict[str, str]:
    return _get_headers()


@pytest.fixture(scope="module")
def client(base_url, headers) -> httpx.Client:
    """Synchronous HTTP client for integration tests."""
    with httpx.Client(base_url=base_url, headers=headers, timeout=60.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHealth:
    """Verify the /health endpoint is reachable."""

    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["entities_count"] >= 1


# ---------------------------------------------------------------------------
# Entities endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEntities:
    """Verify /v1/entities lists at least one agent."""

    def test_entities_list(self, client):
        resp = client.get("/v1/entities")
        assert resp.status_code == 200
        entities = resp.json()["entities"]
        assert len(entities) >= 1
        assert entities[0]["type"] == "agent"


# ---------------------------------------------------------------------------
# Non-streaming KB question
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestKnowledgeBaseQuery:
    """Send a real question and verify the response shape."""

    def test_non_streaming_answer(self, client):
        resp = client.post(
            "/v1/responses",
            json={"input": "What is Azure AI Search?", "stream": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "response"
        assert len(body["output"]) >= 1
        text = body["output"][0]["content"][0]["text"]
        assert len(text) > 10, "Expected a non-trivial answer"


# ---------------------------------------------------------------------------
# Streaming KB question
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStreamingQuery:
    """Send a streaming request and verify SSE events."""

    def test_streaming_produces_events(self, client):
        with client.stream(
            "POST",
            "/v1/responses",
            json={"input": "What is Azure AI Search?", "stream": True},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events: list[str] = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(line)

        # Must have at least one delta + completion + [DONE]
        assert len(events) >= 2, f"Expected >= 2 SSE events, got {len(events)}"
        assert events[-1].strip() == "data: [DONE]"

        # The second-to-last event should be the completion event
        completion = json.loads(events[-2].removeprefix("data: "))
        assert completion["object"] == "response"
        assert len(completion["output"]) >= 1


# ---------------------------------------------------------------------------
# Citations / images
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCitationsPresent:
    """Verify that KB answers include citations when the topic is known."""

    def test_answer_references_sources(self, client):
        resp = client.post(
            "/v1/responses",
            json={
                "input": "What is agentic retrieval in Azure AI Search? Cite sources.",
                "stream": False,
            },
        )
        assert resp.status_code == 200
        text = resp.json()["output"][0]["content"][0]["text"]
        # The agent should mention a reference (e.g. [Ref #1]) or cite a source
        assert "ref" in text.lower() or "source" in text.lower() or "#" in text, (
            f"Expected citations in answer, got: {text[:200]}"
        )
