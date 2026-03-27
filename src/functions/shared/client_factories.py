"""Environment-aware SDK factories for ingestion functions."""

from __future__ import annotations

from typing import Protocol

from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient, ContainerClient
from openai import OpenAI

from shared.config import Config, get_config

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class ChatBackend(Protocol):
    def complete(self, *, prompt: str, max_tokens: int, temperature: float) -> str:
        ...


class _AzureEmbeddingBackend:
    def __init__(self, cfg: Config) -> None:
        endpoint = f"{cfg.ai_services_endpoint.rstrip('/')}/openai/deployments/{cfg.embedding_deployment_name}"
        self._client = EmbeddingsClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
            credential_scopes=[_COGNITIVE_SCOPE],
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embed(input=texts)
        return [item.embedding for item in response.data]


class _OllamaEmbeddingBackend:
    def __init__(self, cfg: Config) -> None:
        self._client = OpenAI(base_url=cfg.ollama_endpoint, api_key=cfg.ollama_api_key)
        self._model = cfg.embedding_deployment_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]


class _AzureChatBackend:
    def __init__(self, cfg: Config, deployment_name: str) -> None:
        endpoint = f"{cfg.ai_services_endpoint.rstrip('/')}/openai/deployments/{deployment_name}"
        self._client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
            credential_scopes=[_COGNITIVE_SCOPE],
        )

    def complete(self, *, prompt: str, max_tokens: int, temperature: float) -> str:
        response = self._client.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()


class _OllamaChatBackend:
    def __init__(self, cfg: Config, model_name: str) -> None:
        self._client = OpenAI(base_url=cfg.ollama_endpoint, api_key=cfg.ollama_api_key)
        self._model = model_name

    def complete(self, *, prompt: str, max_tokens: int, temperature: float) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()


def create_blob_service_client(account_url: str | None = None) -> BlobServiceClient:
    cfg = get_config()
    if cfg.is_dev and cfg.azurite_connection_string:
        return BlobServiceClient.from_connection_string(cfg.azurite_connection_string)
    return BlobServiceClient(
        account_url=(account_url or cfg.serving_blob_endpoint).rstrip("/"),
        credential=DefaultAzureCredential(),
    )


def create_container_client(account_url: str, container_name: str) -> ContainerClient:
    cfg = get_config()
    if cfg.is_dev and cfg.azurite_connection_string:
        blob_service = BlobServiceClient.from_connection_string(cfg.azurite_connection_string)
        return blob_service.get_container_client(container_name)
    return ContainerClient(
        account_url=account_url.rstrip("/"),
        container_name=container_name,
        credential=DefaultAzureCredential(),
    )


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


def create_async_cosmos_client(endpoint: str | None = None) -> AsyncCosmosClient:
    cfg = get_config()
    if cfg.is_dev:
        return AsyncCosmosClient(
            url=endpoint or cfg.cosmos_endpoint,
            credential=cfg.cosmos_key,
            connection_verify=cfg.cosmos_verify_cert,
            enable_endpoint_discovery=False,
        )
    return AsyncCosmosClient(
        url=endpoint or cfg.cosmos_endpoint,
        credential=DefaultAzureCredential(),
    )


def create_search_client(index_name: str | None = None) -> SearchClient:
    cfg = get_config()
    if cfg.is_dev:
        return SearchClient(
            endpoint=cfg.search_endpoint,
            index_name=index_name or cfg.search_index_name,
            credential=AzureKeyCredential(cfg.search_api_key),
            connection_verify=cfg.search_verify_cert,
        )
    return SearchClient(
        endpoint=cfg.search_endpoint,
        index_name=index_name or cfg.search_index_name,
        credential=DefaultAzureCredential(),
    )


def create_search_index_client() -> SearchIndexClient:
    cfg = get_config()
    if cfg.is_dev:
        return SearchIndexClient(
            endpoint=cfg.search_endpoint,
            credential=AzureKeyCredential(cfg.search_api_key),
            connection_verify=cfg.search_verify_cert,
        )
    return SearchIndexClient(
        endpoint=cfg.search_endpoint,
        credential=DefaultAzureCredential(),
    )


def create_embedding_backend() -> EmbeddingBackend:
    cfg = get_config()
    if cfg.is_dev:
        return _OllamaEmbeddingBackend(cfg)
    return _AzureEmbeddingBackend(cfg)


def create_chat_backend(deployment_name: str | None = None) -> ChatBackend:
    cfg = get_config()
    model_name = deployment_name or cfg.summary_deployment_name
    if cfg.is_dev:
        return _OllamaChatBackend(cfg, model_name)
    return _AzureChatBackend(cfg, model_name)