"""Tests for AG-UI endpoint wiring and session continuity."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

import pytest

from agent_framework import AgentSession, Message
from agent_framework.ag_ui import AgentFrameworkAgent

from main import _PersistedSessionAgent, _create_ag_ui_app


class _FakeAgent:
    """Minimal streaming agent used to exercise the AG-UI adapter."""

    def __init__(self) -> None:
        self.captured_session = None
        self.captured_messages = None
        self.captured_service_session_id = None
        self.server_tools = []
        self.next_service_session_id: str | None = None

    async def run(self, messages, **kwargs):
        self.captured_messages = messages
        self.captured_session = kwargs.get("session")
        self.captured_service_session_id = getattr(self.captured_session, "service_session_id", None)
        if self.captured_session is not None and self.next_service_session_id is not None:
            self.captured_session.service_session_id = self.next_service_session_id
        if False:
            yield None


class _MessageModel:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, *, exclude_none: bool = False) -> dict[str, object]:
        return self._payload


class TestAGUIEndpoint:
    """AG-UI endpoint composition on the existing Starlette server."""

    @pytest.mark.parametrize("path", ["/ag-ui", "/ag-ui/"])
    def test_mount_accepts_post_without_redirect(
        self,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        app = Starlette()
        app.mount("/ag-ui", _create_ag_ui_app(_FakeAgent()))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            path,
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 200
        assert '"type":"RUN_STARTED"' in response.text

    def test_mount_enforces_auth_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "true")

        app = Starlette()
        app.mount("/ag-ui", _create_ag_ui_app(_FakeAgent()))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/ag-ui",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "unauthorized"


class _FakeSessionRepository:
    def __init__(self, session: AgentSession | None = None) -> None:
        self.session = session
        self.saved: list[tuple[str, AgentSession]] = []
        self.requested_conversation_ids: list[str] = []

    async def get(self, conversation_id: str) -> AgentSession | None:
        self.requested_conversation_ids.append(conversation_id)
        return self.session

    async def set(self, conversation_id: str, session: AgentSession) -> None:
        self.saved.append((conversation_id, session))


class TestAGUIThreadContinuity:
    """AG-UI wrapper should map thread IDs to service session IDs."""

    @pytest.mark.asyncio
    async def test_persisted_session_agent_prefers_request_history_over_stored_session(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.metadata = {"persisted": True}
        stored_session.state = {
            "in_memory": {"messages": ["persisted-history"]},
            "preferences": {"department": "engineering"},
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        agent.next_service_session_id = "resp-999"
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")
        request_session.metadata = {"ag_ui_thread_id": "thread-123"}
        request_session.state = {
            "local": {"draft": True},
            "messages": ["client-state-history"],
            "in_memory": {"messages": ["client-in-memory-history"]},
        }

        updates = [
            update
            async for update in wrapped_agent.run(
                [{"role": "user", "content": "hello"}],
                session=request_session,
            )
        ]

        assert updates == []
        assert repository.requested_conversation_ids == ["thread-123"]
        assert agent.captured_session is request_session
        assert request_session.metadata == {
            "persisted": True,
            "ag_ui_thread_id": "thread-123",
        }
        assert request_session.state == {
            "preferences": {"department": "engineering"},
            "local": {"draft": True},
        }
        assert agent.captured_service_session_id is None
        assert request_session.service_session_id == "thread-123"
        assert repository.saved == [("thread-123", request_session)]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_reuses_stored_session_when_request_history_absent(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.metadata = {"persisted": True}
        stored_session.state = {"in_memory": {"messages": ["persisted-history"]}}
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")
        request_session.metadata = {"ag_ui_thread_id": "thread-123"}

        updates = [
            update
            async for update in wrapped_agent.run(
                [],
                session=request_session,
            )
        ]

        assert updates == []
        assert repository.requested_conversation_ids == ["thread-123"]
        assert agent.captured_session is stored_session
        assert stored_session.metadata == {
            "persisted": True,
            "ag_ui_thread_id": "thread-123",
        }
        assert stored_session.state == {"in_memory": {"messages": ["persisted-history"]}}
        assert agent.captured_service_session_id == "thread-123"
        assert repository.saved == [("thread-123", stored_session)]

    @pytest.mark.asyncio
    async def test_thread_id_becomes_service_session_id(self) -> None:
        agent = _FakeAgent()
        wrapper = AgentFrameworkAgent(agent=agent, use_service_session=True)

        events = [
            event
            async for event in wrapper.run(
                {
                    "messages": [{"role": "user", "content": "hello"}],
                    "threadId": "thread-123",
                }
            )
        ]

        assert [type(event).__name__ for event in events] == [
            "RunStartedEvent",
            "RunFinishedEvent",
        ]
        assert agent.captured_session is not None
        assert agent.captured_session.service_session_id == "thread-123"
        assert agent.captured_session.metadata["ag_ui_thread_id"] == "thread-123"

    def test_normalize_replayed_messages_reorders_tool_results_within_turn(self) -> None:
        replayed_messages = [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "toolName": "search_knowledge_base",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "toolName": "search_knowledge_base",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    def test_normalize_replayed_messages_drops_orphaned_tool_calls_when_content_exists(self) -> None:
        replayed_messages = [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-1-response",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    def test_normalize_replayed_messages_accepts_message_models(self) -> None:
        replayed_messages = [
            _MessageModel({"id": "user-1", "role": "user", "content": "What is Azure AI Search?"}),
            _MessageModel(
                {
                    "id": "assistant-1",
                    "role": "assistant",
                    "toolCalls": [
                        {
                            "id": "tool-call-1",
                            "type": "function",
                            "function": {
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        },
                    ],
                }
            ),
            _MessageModel(
                {
                    "id": "assistant-2",
                    "role": "assistant",
                    "content": "Azure AI Search is a cloud search service.",
                }
            ),
            _MessageModel({"id": "user-2", "role": "user", "content": "How does indexing work?"}),
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {"id": "assistant-2", "role": "assistant", "content": "Azure AI Search is a cloud search service."},
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_malformed_history_from_stored_session(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "messages": [
                {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
                {
                    "id": "assistant-2",
                    "role": "assistant",
                    "toolCalls": [
                        {
                            "id": "tool-call-1",
                            "type": "function",
                            "function": {
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        },
                    ],
                },
                {
                    "id": "tool-3",
                    "role": "tool",
                    "toolCallId": "tool-call-1",
                    "content": '{"results":[{"title":"Azure AI Search overview"}]}',
                },
                {
                    "id": "assistant-4",
                    "role": "assistant",
                    "content": "Azure AI Search is a cloud search service.",
                },
            ]
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    _MessageModel({"id": "user-1", "role": "user", "content": "What is Azure AI Search?"}),
                    _MessageModel(
                        {
                            "id": "assistant-2",
                            "role": "assistant",
                            "toolCalls": [
                                {
                                    "id": "tool-call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_knowledge_base",
                                        "arguments": '{}',
                                    },
                                },
                            ],
                        }
                    ),
                    _MessageModel(
                        {
                            "id": "assistant-4",
                            "role": "assistant",
                            "content": "Azure AI Search is a cloud search service.",
                        }
                    ),
                    _MessageModel({"id": "user-5", "role": "user", "content": "How does indexing work?"}),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert agent.captured_messages == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-2",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-3",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "assistant-4",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-5", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_history_from_internal_session_messages(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "message_id": "stored-user-1",
                        "contents": [
                            {"type": "text", "text": "What is Azure AI Search?"},
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-2",
                        "contents": [
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "tool",
                        "contents": [
                            {
                                "type": "function_result",
                                "call_id": "tool-call-1",
                                "result": '{"results":[{"title":"Azure AI Search overview"}]}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-4",
                        "contents": [
                            {"type": "text", "text": "Azure AI Search is a cloud search service."},
                        ],
                    },
                ]
            }
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    _MessageModel({"id": "request-user-1", "role": "user", "content": "What is Azure AI Search?"}),
                    _MessageModel(
                        {
                            "id": "request-assistant-2",
                            "role": "assistant",
                            "toolCalls": [
                                {
                                    "id": "tool-call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_knowledge_base",
                                        "arguments": '{}',
                                    },
                                },
                            ],
                        }
                    ),
                    _MessageModel(
                        {
                            "id": "request-assistant-4",
                            "role": "assistant",
                            "content": "Azure AI Search is a cloud search service.",
                        }
                    ),
                    _MessageModel({"id": "request-user-5", "role": "user", "content": "How does indexing work?"}),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert agent.captured_messages == [
            {"id": "stored-user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "stored-assistant-2",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-3",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "stored-assistant-4",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "request-user-5", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_history_from_framework_message_objects(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "message_id": "stored-user-1",
                        "contents": [
                            {"type": "text", "text": "What is Azure AI Search?"},
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-2",
                        "contents": [
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "tool",
                        "contents": [
                            {
                                "type": "function_result",
                                "call_id": "tool-call-1",
                                "result": '{"results":[{"title":"Azure AI Search overview"}]}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-4",
                        "contents": [
                            {"type": "text", "text": "Azure AI Search is a cloud search service."},
                        ],
                    },
                ]
            }
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    Message(role="user", contents=["What is Azure AI Search?"], message_id="request-user-1"),
                    Message(
                        role="assistant",
                        contents=[
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{}',
                            },
                        ],
                        message_id="request-assistant-2",
                    ),
                    Message(
                        role="assistant",
                        contents=["Azure AI Search is a cloud search service."],
                        message_id="request-assistant-4",
                    ),
                    Message(role="user", contents=["How does indexing work?"], message_id="request-user-5"),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert all(isinstance(message, Message) for message in agent.captured_messages)
        captured_messages = [message.to_dict() for message in agent.captured_messages]
        assert [message["role"] for message in captured_messages] == [
            "user",
            "assistant",
            "tool",
            "assistant",
            "user",
        ]
        assert [message.get("message_id") for message in captured_messages] == [
            "stored-user-1",
            "stored-assistant-2",
            "tool-3",
            "stored-assistant-4",
            "request-user-5",
        ]
        assert captured_messages[0]["contents"][0]["type"] == "text"
        assert captured_messages[0]["contents"][0]["text"] == "What is Azure AI Search?"
        assert captured_messages[1]["contents"][0]["type"] == "function_call"
        assert captured_messages[1]["contents"][0]["call_id"] == "tool-call-1"
        assert captured_messages[1]["contents"][0]["name"] == "search_knowledge_base"
        assert captured_messages[1]["contents"][0]["arguments"] == '{"query":"azure ai search"}'
        assert captured_messages[2]["contents"][0]["type"] == "function_result"
        assert captured_messages[2]["contents"][0]["call_id"] == "tool-call-1"
        assert captured_messages[2]["contents"][0]["result"] == '{"results":[{"title":"Azure AI Search overview"}]}'
        assert captured_messages[3]["contents"][0]["type"] == "text"
        assert captured_messages[3]["contents"][0]["text"] == "Azure AI Search is a cloud search service."
        assert captured_messages[4]["contents"][0]["type"] == "text"
        assert captured_messages[4]["contents"][0]["text"] == "How does indexing work?"
