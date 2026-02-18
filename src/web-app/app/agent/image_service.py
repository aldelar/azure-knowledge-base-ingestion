"""Image service — proxy article images from Azure Blob Storage.

Images are served through a local proxy endpoint (``/api/images/...``) so
that the browser never needs direct access to Azure Blob Storage.  This
avoids CSP / CORS issues entirely.

The proxy endpoint downloads the blob on the server side using
``DefaultAzureCredential`` — no SAS tokens are sent to the browser.
"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from urllib.parse import quote

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blob client singleton
# ---------------------------------------------------------------------------

_blob_service_client: BlobServiceClient | None = None


def _get_blob_service_client() -> BlobServiceClient:
    """Lazy singleton for the BlobServiceClient."""
    global _blob_service_client
    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient(
            account_url=config.serving_blob_endpoint,
            credential=DefaultAzureCredential(),
        )
    return _blob_service_client


# ---------------------------------------------------------------------------
# Image download (used by the proxy endpoint)
# ---------------------------------------------------------------------------

@dataclass
class ImageBlob:
    """Downloaded image content + metadata."""
    data: bytes
    content_type: str


def download_image(article_id: str, image_path: str) -> ImageBlob | None:
    """Download an image blob from the serving container.

    Returns ``None`` if the blob does not exist or cannot be read.
    """
    blob_path = f"{article_id}/{image_path}"
    try:
        client = _get_blob_service_client()
        blob_client = client.get_blob_client(
            container=config.serving_container_name,
            blob=blob_path,
        )
        download = blob_client.download_blob()
        data = download.readall()
        content_type = (
            download.properties.content_settings.content_type
            or mimetypes.guess_type(image_path)[0]
            or "application/octet-stream"
        )
        logger.debug("Downloaded blob %s (%d bytes)", blob_path, len(data))
        return ImageBlob(data=data, content_type=content_type)
    except Exception:
        logger.warning("Failed to download blob %s", blob_path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Proxy URL helpers
# ---------------------------------------------------------------------------

def get_image_url(article_id: str, image_path: str) -> str:
    """Return a local proxy URL for the image.

    The URL points to the ``/api/images/{article_id}/{image_path}`` endpoint
    served by the Chainlit app, which fetches the blob server-side.
    """
    encoded_path = quote(image_path, safe="/")
    encoded_article = quote(article_id, safe="")
    return f"/api/images/{encoded_article}/{encoded_path}"


def resolve_image_urls(article_id: str, image_urls: list[str]) -> list[str]:
    """Batch-resolve relative image paths to proxy URLs.

    Parameters
    ----------
    article_id:
        Article folder name.
    image_urls:
        List of relative image paths from the search index.

    Returns
    -------
    list[str]
        Local proxy URLs for each image.
    """
    return [get_image_url(article_id, p) for p in image_urls]
