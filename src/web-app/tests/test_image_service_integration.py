"""Integration tests for image_service — runs against real Azure Blob Storage.

These tests verify that ``download_image`` can reach the serving container
and retrieve content.  They require valid Azure credentials and:

- SERVING_BLOB_ENDPOINT

Usage:
    make azure-test-app      # runs all web app integration tests
"""

from __future__ import annotations

import os

import pytest

from app.image_service import ImageBlob, download_image, get_image_url, resolve_image_urls


# ---------------------------------------------------------------------------
# Proxy URL helpers (fast — no Azure needed, but live here for grouping)
# ---------------------------------------------------------------------------


class TestImageUrlHelpers:
    """Verify proxy URL generation (deterministic, no I/O)."""

    def test_get_image_url_format(self):
        url = get_image_url("article-1", "images/fig1.png")
        assert url == "/api/images/article-1/images/fig1.png"

    def test_resolve_batch(self):
        urls = resolve_image_urls("art", ["images/a.png", "images/b.png"])
        assert len(urls) == 2
        assert all(u.startswith("/api/images/art/") for u in urls)


# ---------------------------------------------------------------------------
# Blob download (integration — needs Azure Blob Storage)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def local_blob_test_env():
    updates = {
        "ENVIRONMENT": "dev",
        "SERVING_BLOB_ENDPOINT": "http://localhost:10000/devstoreaccount1",
        "AZURITE_CONNECTION_STRING": (
            "DefaultEndpointsProtocol=http;"
            "AccountName=devstoreaccount1;"
            "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
            "BlobEndpoint=http://localhost:10000/devstoreaccount1;"
            "QueueEndpoint=http://localhost:10001/devstoreaccount1;"
            "TableEndpoint=http://localhost:10002/devstoreaccount1;"
        ),
        "SERVING_CONTAINER_NAME": "serving-test",
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)

    import app.config as config_module
    import app.image_service as image_service_module

    config_module._config = None
    image_service_module._blob_service_client = None

    yield

    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    config_module._config = None
    image_service_module._blob_service_client = None


@pytest.mark.integration
class TestBlobDownload:
    """Download a real image from the serving container."""

    def test_download_existing_image(self):
        """Verify that a known article image can be downloaded.

        This test assumes the KB has been indexed and the serving container
        contains at least one article with an image.  If no images exist,
        the test is skipped gracefully.
        """
        # Use a known article from the KB —
        # content-understanding-overview has images in the index
        from app.client_factories import create_blob_service_client
        from app.config import config

        client = create_blob_service_client(config.serving_blob_endpoint)
        container = client.get_container_client(config.serving_container_name)

        # Find the first image blob in the container
        image_blob_name = None
        for blob in container.list_blobs():
            if blob.name.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
                image_blob_name = blob.name
                break

        if image_blob_name is None:
            pytest.skip("No image blobs found in serving container")

        # Split into article_id / image_path
        parts = image_blob_name.split("/", 1)
        if len(parts) != 2:
            pytest.skip(f"Unexpected blob path format: {image_blob_name}")

        article_id, image_path = parts

        result = download_image(article_id, image_path)
        assert result is not None
        assert isinstance(result, ImageBlob)
        assert len(result.data) > 0
        assert result.content_type != ""

    def test_download_nonexistent_returns_none(self):
        """Attempt to download a blob that doesn't exist."""
        result = download_image("nonexistent-article-xyz", "images/nope.png")
        assert result is None
