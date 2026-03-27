"""Unit tests for shared client factories."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_blob_factory_uses_connection_string_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("AZURITE_CONNECTION_STRING", "UseDevelopmentStorage=true")

    from shared import config as cfg_mod
    from shared.client_factories import create_blob_service_client

    cfg_mod._config = None

    with patch("shared.client_factories.BlobServiceClient.from_connection_string") as mock_from_connection_string:
        create_blob_service_client("https://ignored.example.com")
        mock_from_connection_string.assert_called_once_with("UseDevelopmentStorage=true")


def test_search_factory_uses_key_credential_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://localhost:7250")
    monkeypatch.setenv("SEARCH_API_KEY", "dev-admin-key")

    from shared import config as cfg_mod
    from shared.client_factories import create_search_client

    cfg_mod._config = None

    with patch("shared.client_factories.SearchClient") as mock_client:
        create_search_client("kb-articles-test")
        kwargs = mock_client.call_args.kwargs
        assert kwargs["endpoint"] == "https://localhost:7250"
        assert kwargs["index_name"] == "kb-articles-test"
        assert kwargs["connection_verify"] is False


def test_cosmos_factory_disables_endpoint_discovery_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://localhost:8081/")
    monkeypatch.setenv("COSMOS_KEY", "emulator-key")

    from shared import config as cfg_mod
    from shared.client_factories import create_cosmos_client

    cfg_mod._config = None

    with patch("shared.client_factories.CosmosClient") as mock_client:
        create_cosmos_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["credential"] == "emulator-key"
        assert kwargs["connection_verify"] is False
        assert kwargs["enable_endpoint_discovery"] is False


def test_embedding_backend_uses_ollama_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama")
    monkeypatch.setenv("EMBEDDING_DEPLOYMENT_NAME", "mxbai-embed-large")

    from shared import config as cfg_mod
    from shared.client_factories import create_embedding_backend

    cfg_mod._config = None

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2])]

    with patch("shared.client_factories.OpenAI", return_value=mock_client):
        backend = create_embedding_backend()
        result = backend.embed(["hello"])
        assert result == [[0.1, 0.2]]
        mock_client.embeddings.create.assert_called_once()