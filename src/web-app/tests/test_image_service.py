"""Tests for the image service (proxy URL generation and blob download)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app import image_service
from app.image_service import get_image_url, resolve_image_urls


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons between tests."""
    image_service._blob_service_client = None
    yield
    image_service._blob_service_client = None


class TestGetImageUrl:
    """Test proxy URL generation for individual images."""

    def test_generates_valid_url(self) -> None:
        url = get_image_url("article-id", "images/fig.png")

        assert url == "/api/images/article-id/images/fig.png"

    def test_url_encodes_special_characters(self) -> None:
        url = get_image_url("my article", "images/my file.png")

        assert "/api/images/my%20article/images/my%20file.png" == url

    def test_preserves_path_slashes(self) -> None:
        url = get_image_url("article-id", "images/sub/deep/fig.png")

        assert url == "/api/images/article-id/images/sub/deep/fig.png"


class TestResolveImageUrls:
    """Test batch URL resolution."""

    def test_resolves_multiple_images(self) -> None:
        urls = resolve_image_urls("a", ["images/1.png", "images/2.png"])

        assert len(urls) == 2
        assert urls[0] == "/api/images/a/images/1.png"
        assert urls[1] == "/api/images/a/images/2.png"

    def test_empty_list(self) -> None:
        urls = resolve_image_urls("a", [])

        assert urls == []


class TestDownloadImage:
    """Test blob download functionality."""

    @patch("app.image_service._get_blob_service_client")
    def test_downloads_blob(self, mock_client_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_blob_client = MagicMock()
        mock_download = MagicMock()
        mock_download.readall.return_value = b"PNG_DATA"
        mock_download.properties.content_settings.content_type = "image/png"
        mock_blob_client.download_blob.return_value = mock_download
        mock_client.get_blob_client.return_value = mock_blob_client
        mock_client_factory.return_value = mock_client

        result = image_service.download_image("article-id", "images/fig.png")

        assert result is not None
        assert result.data == b"PNG_DATA"
        assert result.content_type == "image/png"

    @patch("app.image_service._get_blob_service_client")
    def test_returns_none_on_failure(self, mock_client_factory: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get_blob_client.side_effect = Exception("Blob not found")
        mock_client_factory.return_value = mock_client

        result = image_service.download_image("article-id", "images/missing.png")

        assert result is None
