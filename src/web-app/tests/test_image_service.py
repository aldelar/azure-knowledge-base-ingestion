"""Tests for the image service (Blob SAS URL generation)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.agent import image_service
from app.agent.image_service import get_image_url, resolve_image_urls


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons between tests."""
    image_service._blob_service_client = None
    image_service._user_delegation_key = None
    image_service._key_expiry = None
    yield
    image_service._blob_service_client = None
    image_service._user_delegation_key = None
    image_service._key_expiry = None


class TestGetImageUrl:
    """Test SAS URL generation for individual images."""

    @patch("app.agent.image_service.generate_blob_sas")
    @patch("app.agent.image_service._get_user_delegation_key")
    def test_generates_valid_url(
        self, mock_key: MagicMock, mock_sas: MagicMock
    ) -> None:
        mock_key.return_value = MagicMock()
        mock_sas.return_value = "sv=2023-01-01&sig=abc123"

        url = get_image_url("article-id", "images/fig.png")

        assert "article-id/images/fig.png" in url
        assert "sv=2023-01-01&sig=abc123" in url
        mock_sas.assert_called_once()

    @patch("app.agent.image_service._get_user_delegation_key")
    def test_returns_empty_on_failure(self, mock_key: MagicMock) -> None:
        mock_key.side_effect = Exception("Auth failed")

        url = get_image_url("article-id", "images/fig.png")

        assert url == ""


class TestResolveImageUrls:
    """Test batch URL resolution."""

    @patch("app.agent.image_service.get_image_url")
    def test_resolves_multiple_images(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            "https://storage.blob.core.windows.net/serving/a/images/1.png?sas",
            "https://storage.blob.core.windows.net/serving/a/images/2.png?sas",
        ]

        urls = resolve_image_urls("a", ["images/1.png", "images/2.png"])

        assert len(urls) == 2
        assert mock_get.call_count == 2

    @patch("app.agent.image_service.get_image_url")
    def test_skips_failed_urls(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            "https://storage.blob.core.windows.net/serving/a/images/1.png?sas",
            "",  # failed
        ]

        urls = resolve_image_urls("a", ["images/1.png", "images/missing.png"])

        assert len(urls) == 1

    @patch("app.agent.image_service.get_image_url")
    def test_empty_list(self, mock_get: MagicMock) -> None:
        urls = resolve_image_urls("a", [])

        assert urls == []
        mock_get.assert_not_called()


class TestDelegationKeyCaching:
    """Test that user delegation keys are cached and reused."""

    @patch("app.agent.image_service._get_blob_service_client")
    def test_key_is_cached(self, mock_client_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_key = MagicMock()
        mock_client.get_user_delegation_key.return_value = mock_key
        mock_client_factory.return_value = mock_client

        from app.agent.image_service import _get_user_delegation_key

        key1 = _get_user_delegation_key()
        key2 = _get_user_delegation_key()

        assert key1 is key2
        # Should only be called once since key is cached
        assert mock_client.get_user_delegation_key.call_count == 1
