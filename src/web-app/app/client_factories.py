"""Environment-aware SDK factories for the web app."""

from __future__ import annotations

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.config import get_config


def create_cosmos_client(endpoint: str | None = None) -> CosmosClient:
    cfg = get_config()
    if cfg.is_dev:
        return CosmosClient(
            url=endpoint or cfg.cosmos_endpoint,
            credential=cfg.cosmos_key,
            connection_verify=cfg.cosmos_verify_cert,
            enable_endpoint_discovery=False,
        )
    return CosmosClient(
        url=endpoint or cfg.cosmos_endpoint,
        credential=DefaultAzureCredential(),
    )


def create_blob_service_client(account_url: str | None = None) -> BlobServiceClient:
    cfg = get_config()
    if cfg.is_dev and cfg.azurite_connection_string:
        return BlobServiceClient.from_connection_string(cfg.azurite_connection_string)
    return BlobServiceClient(
        account_url=(account_url or cfg.serving_blob_endpoint).rstrip("/"),
        credential=DefaultAzureCredential(),
    )