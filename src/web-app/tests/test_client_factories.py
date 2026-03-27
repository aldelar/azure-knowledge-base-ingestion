"""Unit tests for web app client factories."""

from __future__ import annotations

from unittest.mock import patch


def test_cosmos_factory_uses_emulator_key_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://localhost:8081/")
    monkeypatch.setenv("COSMOS_KEY", "emulator-key")

    from app import config as cfg_mod
    from app.client_factories import create_cosmos_client

    cfg_mod._config = None

    with patch("app.client_factories.CosmosClient") as mock_client:
        create_cosmos_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["credential"] == "emulator-key"
        assert kwargs["connection_verify"] is False
        assert kwargs["enable_endpoint_discovery"] is False


def test_blob_factory_uses_connection_string_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("AZURITE_CONNECTION_STRING", "UseDevelopmentStorage=true")

    from app import config as cfg_mod
    from app.client_factories import create_blob_service_client

    cfg_mod._config = None

    with patch("app.client_factories.BlobServiceClient.from_connection_string") as mock_from_connection_string:
        create_blob_service_client()
        mock_from_connection_string.assert_called_once_with("UseDevelopmentStorage=true")