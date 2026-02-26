"""Adapter integration tests for the KB Agent server.

The ``from_agent_framework`` adapter manages the HTTP layer (routes, SSE
streaming, health probes).  These tests verify the contract between our
code and the adapter — primarily the ``create_agent`` factory and the
server object it produces.

Full HTTP endpoint tests (streaming, health, error handling) are covered
by integration tests that require a running server.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Agent factory tests
# ---------------------------------------------------------------------------


class TestCreateAgentFactory:
    """Test the create_agent() factory used by main()."""

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_factory_returns_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() returns a ChatAgent instance."""
        from agent.kb_agent import create_agent

        agent = create_agent()

        mock_agent_cls.assert_called_once()
        assert agent is mock_agent_cls.return_value


# ---------------------------------------------------------------------------
# Adapter instantiation tests
# ---------------------------------------------------------------------------


class TestAdapterInstantiation:
    """Test that from_agent_framework accepts our ChatAgent."""

    @patch("agent.kb_agent.ChatAgent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_adapter_wraps_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """from_agent_framework() wraps our ChatAgent without error."""
        from azure.ai.agentserver.agentframework import from_agent_framework
        from agent.kb_agent import create_agent

        agent = create_agent()
        server = from_agent_framework(agent)

        # The adapter returns an object with a .run() method
        assert hasattr(server, "run")
        assert hasattr(server, "run_async")
