"""Unit tests for agent client factories."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_chat_factory_uses_ollama_chat_client_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama")
    monkeypatch.setenv("AGENT_MODEL_DEPLOYMENT_NAME", "phi4-mini")

    from agent import config as cfg_mod
    from agent.client_factories import create_chat_client

    cfg_mod._config = None

    with patch("agent.client_factories.OpenAIChatClient") as mock_client:
        create_chat_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["model_id"] == "phi4-mini"
        assert kwargs["base_url"] == "http://localhost:11434/v1"


def test_search_factory_uses_api_key_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://localhost:7250")
    monkeypatch.setenv("SEARCH_API_KEY", "dev-admin-key")

    from agent import config as cfg_mod
    from agent.client_factories import create_search_client

    cfg_mod._config = None

    with patch("agent.client_factories.SearchClient") as mock_client:
        create_search_client()
        assert mock_client.call_args.kwargs["connection_verify"] is False


def test_query_embedding_backend_uses_ollama_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama")
    monkeypatch.setenv("EMBEDDING_DEPLOYMENT_NAME", "mxbai-embed-large")

    from agent import config as cfg_mod
    from agent.client_factories import create_query_embedding_backend

    cfg_mod._config = None

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.3, 0.4])]

    with patch("agent.client_factories.OpenAI", return_value=mock_client):
        backend = create_query_embedding_backend()
        assert backend.embed(["query"]) == [[0.3, 0.4]]


def test_async_cosmos_factory_disables_endpoint_discovery_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://localhost:8081/")
    monkeypatch.setenv("COSMOS_KEY", "emulator-key")

    from agent import config as cfg_mod
    from agent.client_factories import create_async_cosmos_client

    cfg_mod._config = None

    with patch("agent.client_factories.AsyncCosmosClient") as mock_client:
        create_async_cosmos_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["credential"] == "emulator-key"
        assert kwargs["connection_verify"] is False
        assert kwargs["enable_endpoint_discovery"] is False