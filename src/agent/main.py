"""KB Agent — FastAPI server exposing an OpenAI-compatible Responses API.

Starts the agent as a local HTTP server (port 8088).  The agent is
stateless — conversation history is managed by the client (web app)
and sent with each request.

Endpoints
---------
- ``GET  /health``           — health check
- ``GET  /v1/entities``      — list available agents
- ``POST /v1/responses``     — process a user message (streaming or non-streaming)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_framework.observability import configure_otel_providers

# Setup observability — reads environment variables automatically:
#   - OTEL_EXPORTER_OTLP_ENDPOINT (for Aspire Dashboard/OTLP)
#   - APPLICATIONINSIGHTS_CONNECTION_STRING (for Azure Monitor)
#   - OTEL_SERVICE_NAME (defaults to agent_framework)
configure_otel_providers()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
for _name in ("azure.core", "azure.identity", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global state (initialised in lifespan)
# ---------------------------------------------------------------------------

from agent_framework import ChatAgent  # noqa: E402
from agent.kb_agent import _pending_citations  # noqa: E402

agent: ChatAgent | None = None


# ---------------------------------------------------------------------------
# FastAPI lifespan — create agent on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the ChatAgent on startup, tear down on shutdown."""
    global agent

    logger.info("[KB-AGENT] Server starting up...")

    from agent.kb_agent import create_agent  # noqa: E402
    agent = create_agent()
    logger.info("[KB-AGENT] Agent created and ready.")

    yield

    logger.info("[KB-AGENT] Server shutting down...")


app = FastAPI(
    title="KB Search Agent",
    description="Knowledge-base search agent with vision — Responses API compatible",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models (OpenAI Responses API compatible)
# ---------------------------------------------------------------------------

class ResponsesRequest(BaseModel):
    """Request model for /v1/responses."""
    input: str
    instructions: str | None = None
    metadata: dict[str, Any] | None = None
    stream: bool = False


class ContentItem(BaseModel):
    type: str = "output_text"
    text: str
    annotations: list = []


class OutputMessage(BaseModel):
    id: str
    role: str = "assistant"
    type: str = "message"
    status: str = "completed"
    content: list[ContentItem]


class UsageDetails(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ResponsesResponse(BaseModel):
    id: str
    object: str = "response"
    created_at: float
    model: str = "kb-agent"
    output: list[OutputMessage]
    usage: UsageDetails
    error: str | None = None


class EntityInfo(BaseModel):
    id: str
    type: str = "agent"
    name: str
    description: str
    tools: list[str]


class EntitiesResponse(BaseModel):
    entities: list[EntityInfo]


class HealthResponse(BaseModel):
    status: str
    entities_count: int


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", entities_count=1)


@app.get("/v1/entities", response_model=EntitiesResponse)
async def list_entities():
    """List available entities (agents)."""
    return EntitiesResponse(
        entities=[
            EntityInfo(
                id="kb-agent",
                name="KBSearchAgent",
                description="Knowledge-base search agent with vision-grounded answers",
                tools=["search_knowledge_base"],
            )
        ]
    )


@app.post("/v1/responses")
async def create_response(request: ResponsesRequest):
    """Process a user message and return the agent's response.

    Compatible with the OpenAI Responses API format.
    Supports ``stream=True`` for Server-Sent Events.
    """
    try:
        full_input = request.input
        if request.instructions:
            full_input = f"[Context]\n{request.instructions}\n[/Context]\n\n{request.input}"

        logger.info(
            "[KB-AGENT] Processing request (stream=%s): %s...",
            request.stream,
            request.input[:100],
        )

        if request.stream:
            return await _create_streaming_response(full_input)

        # Non-streaming response
        result = await agent.run(full_input)
        response_text = str(result) if result else ""
        logger.info("[KB-AGENT] Response generated: %s...", response_text[:100])

        return ResponsesResponse(
            id=f"resp_{uuid.uuid4().hex[:12]}",
            created_at=time.time(),
            output=[
                OutputMessage(
                    id=f"msg_{uuid.uuid4().hex[:8]}",
                    content=[ContentItem(text=response_text)],
                )
            ],
            usage=UsageDetails(
                input_tokens=len(full_input.split()),
                output_tokens=len(response_text.split()),
                total_tokens=len(full_input.split()) + len(response_text.split()),
            ),
        )

    except Exception as e:
        logger.error("[KB-AGENT] Error processing request: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


async def _create_streaming_response(full_input: str):
    """Create a streaming SSE response."""

    async def generate():
        response_id = f"resp_{uuid.uuid4().hex[:12]}"
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        created_at = time.time()

        def _sse(event_type: str, data: dict) -> str:
            payload = {"type": event_type, **data}
            return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

        try:
            # --- response.created ---
            base_response = {
                "id": response_id,
                "object": "response",
                "created_at": created_at,
                "model": "kb-agent",
                "status": "in_progress",
                "output": [],
                "usage": None,
            }
            yield _sse("response.created", {"response": base_response})

            # --- response.output_item.added ---
            output_item = {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "status": "in_progress",
                "content": [],
            }
            yield _sse("response.output_item.added", {
                "output_index": 0,
                "item": output_item,
            })

            # --- response.content_part.added ---
            yield _sse("response.content_part.added", {
                "item_id": msg_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            })

            # --- clear pending citations before agent runs ---
            _pending_citations.clear()

            # --- stream text deltas ---
            full_response = ""

            if hasattr(agent, "run_stream"):
                async for chunk in agent.run_stream(full_input):
                    chunk_text = str(chunk) if chunk else ""
                    if chunk_text:
                        full_response += chunk_text
                        yield _sse("response.output_text.delta", {
                            "item_id": msg_id,
                            "output_index": 0,
                            "content_index": 0,
                            "delta": chunk_text,
                        })
            else:
                result = await agent.run(full_input)
                full_response = str(result) if result else ""
                if full_response:
                    yield _sse("response.output_text.delta", {
                        "item_id": msg_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": full_response,
                    })

            # --- response.output_text.done ---
            yield _sse("response.output_text.done", {
                "item_id": msg_id,
                "output_index": 0,
                "content_index": 0,
                "text": full_response,
            })

            # --- response.content_part.done ---
            yield _sse("response.content_part.done", {
                "item_id": msg_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": full_response},
            })

            # --- response.output_item.done ---
            output_item["status"] = "completed"
            output_item["content"] = [{"type": "output_text", "text": full_response}]
            yield _sse("response.output_item.done", {
                "output_index": 0,
                "item": output_item,
            })

            # --- response.completed ---
            usage = {
                "input_tokens": len(full_input.split()),
                "output_tokens": len(full_response.split()),
                "total_tokens": len(full_input.split()) + len(full_response.split()),
            }
            # Attach citation metadata so the UI can build clickable refs
            citations_payload = [
                {
                    "article_id": c.article_id,
                    "title": c.title,
                    "section_header": c.section_header,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "image_urls": c.image_urls,
                }
                for c in _pending_citations
            ]
            base_response["status"] = "completed"
            base_response["output"] = [output_item]
            base_response["usage"] = usage
            base_response["metadata"] = {"citations": citations_payload}
            yield _sse("response.completed", {"response": base_response})

        except Exception as e:
            logger.error("[KB-AGENT] Streaming error: %s", e)
            yield _sse("response.failed", {
                "response": {
                    "id": response_id,
                    "object": "response",
                    "status": "failed",
                    "error": {"message": str(e), "type": "server_error", "code": None},
                },
            })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Launch the KB Agent server.

    The agent is stateless — conversation history is managed by the
    client (web app) and sent with each request.
    """
    port = int(os.environ.get("PORT", "8088"))

    logger.info("[KB-AGENT] Starting server on port %d", port)
    logger.info("[KB-AGENT] Health:    http://localhost:%d/health", port)
    logger.info("[KB-AGENT] Entities:  http://localhost:%d/v1/entities", port)
    logger.info("[KB-AGENT] Responses: http://localhost:%d/v1/responses", port)

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
