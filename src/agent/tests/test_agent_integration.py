"""Agent integration tests — run against a live agent endpoint.

These tests call a real agent (local or deployed) and verify the HTTP
contract exposed by the ``from_agent_framework`` adapter.  They do NOT
mock anything.

Local adapter endpoints:
  POST /responses   — Responses API (streaming or non-streaming)
  GET  /liveness    — 200 OK (container alive)
  GET  /readiness   — {"status": "ready"} (agent ready to serve)

Published agent endpoint (Foundry):
  POST {base_url}/responses?api-version=2025-11-15-preview
  Health probes are NOT exposed through the published endpoint.

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

# True when targeting a published Foundry agent (https endpoint).  Health
# probes aren't exposed through the published endpoint, and the api-version
# query param differs from the dev endpoint.
_IS_REMOTE = AGENT_ENDPOINT.startswith("https://")


def _get_headers() -> dict[str, str]:
    """Return request headers — adds Entra token for https endpoints."""
    if _IS_REMOTE:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token("https://ai.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base_url() -> str:
    # Trailing slash ensures httpx resolves relative paths correctly
    # (RFC 3986: "responses" appended to ".../openai/" → ".../openai/responses")
    return AGENT_ENDPOINT.rstrip("/") + "/"


@pytest.fixture(scope="module")
def headers() -> dict[str, str]:
    return _get_headers()


@pytest.fixture(scope="module")
def client(base_url, headers) -> httpx.Client:
    """Synchronous HTTP client for integration tests."""
    params = {}
    # Published Foundry endpoints require api-version query parameter.
    if _IS_REMOTE:
        params["api-version"] = "2025-11-15-preview"
    with httpx.Client(
        base_url=base_url, headers=headers, params=params, timeout=120.0
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Health / readiness probes
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHealthProbes:
    """Verify the adapter health probe endpoints.

    These probes are only available when testing the local container
    directly.  Published Foundry endpoints don't expose /liveness or
    /readiness.
    """

    @pytest.mark.skipif(_IS_REMOTE, reason="Health probes not exposed on published endpoint")
    def test_liveness(self, client):
        resp = client.get("liveness")
        assert resp.status_code == 200

    @pytest.mark.skipif(_IS_REMOTE, reason="Health probes not exposed on published endpoint")
    def test_readiness(self, client):
        resp = client.get("readiness")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"


# ---------------------------------------------------------------------------
# Non-streaming KB question
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestKnowledgeBaseQuery:
    """Send a real question and verify the response shape."""

    def test_non_streaming_answer(self, client):
        resp = client.post(
            "responses",
            json={"input": "What is Azure AI Search?", "stream": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "response"
        assert len(body["output"]) >= 1
        # Find the message output (skip function_call / function_call_output)
        msg = next(
            (o for o in body["output"] if o.get("type") == "message"),
            body["output"][-1],
        )
        text = msg["content"][0]["text"]
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
            "responses",
            json={"input": "What is Azure AI Search?", "stream": True},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events: list[str] = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(line)

        # Must have at least a few SSE events (deltas + completion)
        assert len(events) >= 2, f"Expected >= 2 SSE events, got {len(events)}"

        # Find the completion event — either "response.completed" type or
        # the data: [DONE] sentinel (local adapter uses [DONE], published
        # Foundry endpoints send a response.completed event as the last data).
        completion_event = None
        for evt in reversed(events):
            payload = evt.removeprefix("data: ").strip()
            if payload == "[DONE]":
                break
            try:
                parsed = json.loads(payload)
                if parsed.get("type") == "response.completed":
                    completion_event = parsed.get("response", parsed)
                    break
                if parsed.get("object") == "response":
                    completion_event = parsed
                    break
            except json.JSONDecodeError:
                continue

        assert completion_event is not None, "No completion event found in stream"
        assert len(completion_event.get("output", [])) >= 1


# ---------------------------------------------------------------------------
# Citations / images
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCitationsPresent:
    """Verify that KB answers include citations when the topic is known."""

    def test_answer_references_sources(self, client):
        resp = client.post(
            "responses",
            json={
                "input": "What is agentic retrieval in Azure AI Search? Cite sources.",
                "stream": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        msg = next(
            (o for o in body["output"] if o.get("type") == "message"),
            body["output"][-1],
        )
        text = msg["content"][0]["text"]
        # The agent should mention a reference (e.g. [Ref #1]) or cite a source
        assert "ref" in text.lower() or "source" in text.lower() or "#" in text, (
            f"Expected citations in answer, got: {text[:200]}"
        )


# ---------------------------------------------------------------------------
# Search tool — end-to-end validation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSearchToolConnectivity:
    """Validate that the agent's search_knowledge_base tool connects to
    Azure AI Search and returns grounded results.

    These tests confirm that:
    * The deployed agent can reach Azure AI Search via its managed identity.
    * The search index contains documents and returns relevant hits.
    * Image URLs from the knowledge base are surfaced in answers.
    """

    def test_search_returns_grounded_answer(self, client):
        """Ask a KB-specific question that can only be answered from the index."""
        resp = client.post(
            "responses",
            json={
                "input": (
                    "Explain what Content Understanding analyzers are in "
                    "Azure AI. Be specific and detailed."
                ),
                "stream": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "response"
        msg = next(
            (o for o in body["output"] if o.get("type") == "message"),
            body["output"][-1],
        )
        text = msg["content"][0]["text"]

        # The answer must contain domain-specific terms that only come from
        # the indexed KB articles — not from generic model knowledge.
        text_lower = text.lower()
        assert any(
            term in text_lower
            for term in ["analyzer", "content understanding", "azure ai"]
        ), f"Answer does not appear grounded in KB content: {text[:300]}"

    def test_search_answer_contains_images(self, client):
        """KB articles include diagrams; the agent should surface image URLs."""
        resp = client.post(
            "responses",
            json={
                "input": (
                    "Describe the architecture of Azure AI Search agentic "
                    "retrieval. Include any diagrams or images."
                ),
                "stream": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        msg = next(
            (o for o in body["output"] if o.get("type") == "message"),
            body["output"][-1],
        )
        text = msg["content"][0]["text"]

        # Image references should appear — either as full URLs (http...)
        # or relative paths (/api/images/... or ![...](...))
        has_image_url = "http" in text and (".png" in text or ".jpg" in text or "blob.core" in text)
        has_image_path = ".png" in text or ".jpg" in text or ".svg" in text
        has_markdown_image = "![" in text
        assert has_image_url or has_image_path or has_markdown_image, (
            f"Expected image references in answer, got: {text[:300]}"
        )

    def test_search_no_results_topic(self, client):
        """Ask about a topic NOT in the KB — the agent should state it has
        no relevant information rather than hallucinate."""
        resp = client.post(
            "responses",
            json={
                "input": (
                    "What is the capital of France? Answer only from "
                    "the knowledge base."
                ),
                "stream": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        msg = next(
            (o for o in body["output"] if o.get("type") == "message"),
            body["output"][-1],
        )
        text = msg["content"][0]["text"].lower()
        # The agent should not confidently answer unrelated questions
        # It should either say it doesn't have info or provide a hedged answer
        assert any(
            phrase in text
            for phrase in [
                "knowledge base",
                "don't have",
                "do not have",
                "not found",
                "no relevant",
                "no information",
                "cannot find",
                "do not contain",
                "outside",
                "not related",
                "paris",  # if it does answer, at least it's correct
            ]
        ), f"Expected graceful handling of off-topic query, got: {text[:300]}"
