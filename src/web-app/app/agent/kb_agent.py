"""KB Search Agent — conversational agent using Microsoft Agent Framework.

Uses gpt-4.1 via ``AzureOpenAIChatClient`` and ``ChatAgent`` with a single
``search_knowledge_base`` function tool to answer knowledge-base questions
grounded in Azure AI Search results.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Annotated, AsyncIterator, Union

from azure.identity import DefaultAzureCredential
from agent_framework import ChatAgent, AgentThread
from agent_framework._types import TextContent
from agent_framework.azure import AzureOpenAIChatClient

from app.agent.search_tool import SearchResult, search_kb
from app.agent.image_service import get_image_url
from app.agent.vision_middleware import VisionImageMiddleware
from app.config import config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a helpful knowledge-base assistant. You answer questions about Azure \
services, features, and how-to guides using the search_knowledge_base tool.

Rules:
1. ALWAYS use the search_knowledge_base tool to find relevant information \
   before answering.
2. Ground your answers in the search results — do not make up information.
3. You have vision capabilities. The actual images from search results are \
   attached to the conversation so you can see them. When an image would \
   genuinely help illustrate or clarify your answer, embed it inline using \
   standard Markdown: ![brief description](url). You MUST copy the URL \
   exactly from the "url" field in each search result's "images" array — \
   it will always start with "/api/images/". \
   CORRECT example: ![Architecture diagram](/api/images/my-article/images/arch.png) \
   WRONG — do NOT use any of these formats: \
     • https://learn.microsoft.com/... (external URLs) \
     • attachment:filename.png (attachment scheme) \
     • api/images/... (missing leading slash) \
   Only include images that add value — do not embed every available image. \
   Refer to visual details you can see in the images when they are relevant.
4. Use inline reference markers to attribute information to its source. Each \
   search result has a ref_number — insert [Ref #N] immediately after the \
   sentence or paragraph that uses that result. For example: \
   "Azure AI Search supports IP firewall rules [Ref #1]."
5. Do NOT include a Sources section at the end — the UI handles that.
6. If the search results don't contain enough information to answer the \
   question, say so honestly.
7. Use clear Markdown formatting: headings, bullet points, bold for emphasis.
8. Be concise but thorough.
"""


# ---------------------------------------------------------------------------
# Dataclasses for structured output
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """A source citation from a search result."""

    article_id: str
    title: str
    section_header: str
    chunk_index: int
    content: str = ""
    image_urls: list[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    """The agent's response to a user question."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    images: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool function — exposed to the agent as a callable function tool.
#
# The agent framework discovers the function signature and docstring
# automatically; no manual JSON schema definition is needed.
# ---------------------------------------------------------------------------

# Accumulator populated by the tool function during a single agent.run()
# cycle.  Reset before each call to agent.run() by KBAgent.chat().
_pending_citations: list[Citation] = []
_pending_images: list[str] = []


def search_knowledge_base(
    query: Annotated[str, "The search query — use natural language describing what information is needed"],
) -> str:
    """Search the knowledge base for articles about Azure services, features, and how-to guides.

    Returns relevant text chunks with optional images.
    """
    logger.info("search_knowledge_base(query='%s')", query[:80])

    try:
        results: list[SearchResult] = search_kb(query)
    except Exception:
        logger.error("search_kb execution failed", exc_info=True)
        return json.dumps({"error": "Search failed. Please try again."})

    result_dicts: list[dict] = []
    for idx, r in enumerate(results, start=1):
        # Store raw image paths in citations (used by the UI to download blobs)
        _pending_citations.append(Citation(
            article_id=r.article_id,
            title=r.title,
            section_header=r.section_header,
            chunk_index=r.chunk_index,
            content=r.content,
            image_urls=list(r.image_urls),  # raw paths like 'images/foo.png'
        ))

        result_dicts.append({
            "ref_number": idx,
            "content": r.content,
            "title": r.title,
            "section_header": r.section_header,
            "article_id": r.article_id,
            "images": [
                {"name": url.split("/")[-1], "url": get_image_url(r.article_id, url)}
                for url in r.image_urls
            ] if r.image_urls else [],
        })

    return json.dumps(result_dicts, ensure_ascii=False)


# ---------------------------------------------------------------------------
# KBAgent — wraps Microsoft Agent Framework ChatAgent
# ---------------------------------------------------------------------------

class KBAgent:
    """Conversational KB search agent using Microsoft Agent Framework.

    Uses :class:`~agent_framework.ChatAgent` with
    :class:`~agent_framework.azure.AzureOpenAIChatClient` (backed by Azure
    OpenAI) and a single ``search_knowledge_base`` function tool.

    Conversation state is managed via :class:`~agent_framework.AgentThread`.
    """

    def __init__(self) -> None:
        client = AzureOpenAIChatClient(
            credential=DefaultAzureCredential(),
            endpoint=config.ai_services_endpoint,
            deployment_name=config.agent_model_deployment_name,
            api_version="2025-03-01-preview",
            middleware=[VisionImageMiddleware()],
        )
        self._agent = ChatAgent(
            chat_client=client,
            name="KBSearchAgent",
            instructions=_SYSTEM_PROMPT,
            tools=[search_knowledge_base],
        )
        logger.info(
            "KBAgent initialized (model=%s)",
            config.agent_model_deployment_name,
        )

    async def chat(
        self,
        user_message: str,
        thread: AgentThread | None = None,
    ) -> AgentResponse:
        """Send a user message and get an agent response.

        Parameters
        ----------
        user_message:
            The user's question or message.
        thread:
            An existing :class:`AgentThread` for multi-turn conversations.
            Pass ``None`` to start a new conversation.  The thread is mutated
            in-place by the framework so subsequent calls with the same
            thread maintain history automatically.

        Returns
        -------
        AgentResponse
            The agent's text answer, citations, and image URLs.
        """
        # Reset per-request accumulators
        _pending_citations.clear()
        _pending_images.clear()

        try:
            response = await self._agent.run(
                user_message,
                thread=thread,
            )
            text = response.text or ""
        except Exception:
            logger.error("Agent run failed", exc_info=True)
            text = "Sorry, I encountered an error processing your request. Please try again."

        return AgentResponse(
            text=text,
            citations=list(_pending_citations),
            images=list(_pending_images),
        )

    async def chat_stream(
        self,
        user_message: str,
        thread: AgentThread | None = None,
    ) -> AsyncIterator[Union[str, AgentResponse]]:
        """Stream the agent response, yielding text deltas then a final AgentResponse.

        Yields
        ------
        str
            Incremental text chunks as they arrive from the LLM.
        AgentResponse
            The final complete response (always the last item yielded).
        """
        # Reset per-request accumulators
        _pending_citations.clear()
        _pending_images.clear()

        full_text = ""
        try:
            async for update in self._agent.run_stream(
                user_message,
                thread=thread,
            ):
                # Each update may contain multiple content items; extract text only
                delta = ""
                for content in update.contents:
                    if isinstance(content, TextContent):
                        delta += content.text
                if delta:
                    full_text += delta
                    yield delta
        except Exception:
            logger.error("Agent stream failed", exc_info=True)
            full_text = "Sorry, I encountered an error processing your request. Please try again."
            yield full_text

        yield AgentResponse(
            text=full_text,
            citations=list(_pending_citations),
            images=list(_pending_images),
        )
