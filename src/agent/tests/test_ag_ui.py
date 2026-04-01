"""Tests for AG-UI endpoint wiring and session continuity."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

import pytest

from agent_framework import AgentSession
from agent_framework.ag_ui import AgentFrameworkAgent

from main import _PersistedSessionAgent, _create_ag_ui_app


class _FakeAgent:
    """Minimal streaming agent used to exercise the AG-UI adapter."""

    def __init__(self) -> None:
        self.captured_session = None
        self.server_tools = []
        self.next_service_session_id: str | None = None

    async def run(self, messages, **kwargs):
        self.captured_session = kwargs.get("session")
        if self.captured_session is not None and self.next_service_session_id is not None:
            self.captured_session.service_session_id = self.next_service_session_id
        if False:
            yield None


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
    async def test_persisted_session_agent_loads_and_saves_existing_session(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.metadata = {"persisted": True}
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        agent.next_service_session_id = "resp-999"
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")
        request_session.metadata = {"ag_ui_thread_id": "thread-123"}

        updates = [
            update
            async for update in wrapped_agent.run(
                [{"role": "user", "content": "hello"}],
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
        assert stored_session.service_session_id == "thread-123"
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
