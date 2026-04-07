"""Shared configuration — lazy-loaded, per-function validation.

Usage:
    from shared.config import get_config
    cfg = get_config()    # validates required env vars on first call
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_DEFAULT_COSMOS_KEY = (
    "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPM"
    "bIZnqyMsEcaGQy67XIw/Jw=="
)


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _default_vector_dimensions(environment: str) -> int:
    return 1024 if environment == "dev" else 1536


def _default_enable_chunk_summaries(environment: str) -> bool:
    return environment != "dev"


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/functions/
    candidates = [
        current / ".env",
        current.parent.parent / ".env",  # repo root
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@dataclass(frozen=True)
class Config:
    """Typed configuration loaded from environment variables."""

    environment: str = "prod"

    # Azure AI Services (Content Understanding + Embeddings)
    ai_services_endpoint: str = ""

    # Local Ollama endpoint
    ollama_endpoint: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"

    # Embedding model deployment name
    embedding_deployment_name: str = "text-embedding-3-small"
    summary_deployment_name: str = "gpt-4.1-mini"
    vision_deployment_name: str = "gpt-4.1"
    agent_model_deployment_name: str = "gpt-4.1"
    embedding_vector_dimensions: int = 1536
    enable_chunk_summaries: bool = True

    # Mistral Document AI deployment name
    mistral_deployment_name: str = "mistral-document-ai-2512"

    # Azure AI Search
    search_endpoint: str = ""
    search_index_name: str = "kb-articles"
    search_api_key: str = ""
    search_verify_cert: bool = True

    # Azure Blob Storage endpoints
    staging_blob_endpoint: str = ""
    serving_blob_endpoint: str = ""
    staging_container_name: str = "staging"
    serving_container_name: str = "serving"
    azurite_connection_string: str = ""

    # Cosmos DB (used by dev tooling and shared factories)
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_verify_cert: bool = True

    # Local paths (for local file I/O mode)
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)

    @property
    def staging_path(self) -> Path:
        return self.project_root / "kb" / "staging"

    @property
    def serving_path(self) -> Path:
        return self.project_root / "kb" / "serving"

    @property
    def is_azure_mode(self) -> bool:
        """True when blob storage endpoints are configured (running in Azure)."""
        return bool(self.staging_blob_endpoint and self.serving_blob_endpoint)

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


_config: Config | None = None


def get_config() -> Config:
    """Load configuration from environment (lazy, cached).

    Returns a Config instance populated from environment variables.
    No validation of required vars here — each function validates
    what it needs at its own entry point.
    """
    global _config
    if _config is not None:
        return _config

    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    environment = os.environ.get("ENVIRONMENT", "prod").strip().lower() or "prod"

    _config = Config(
        environment=environment,
        ai_services_endpoint=os.environ.get("AI_SERVICES_ENDPOINT", ""),
        ollama_endpoint=os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1"),
        ollama_api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        summary_deployment_name=os.environ.get("SUMMARY_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        vision_deployment_name=os.environ.get("VISION_DEPLOYMENT_NAME", "gpt-4.1"),
        agent_model_deployment_name=os.environ.get("AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        embedding_vector_dimensions=_get_int(
            "EMBEDDING_VECTOR_DIMENSIONS",
            _default_vector_dimensions(environment),
        ),
        enable_chunk_summaries=_get_bool(
            "ENABLE_CHUNK_SUMMARIES",
            _default_enable_chunk_summaries(environment),
        ),
        mistral_deployment_name=os.environ.get("MISTRAL_DEPLOYMENT_NAME", "mistral-document-ai-2512"),
        search_endpoint=os.environ.get("SEARCH_ENDPOINT", ""),
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
        search_api_key=os.environ.get(
            "SEARCH_API_KEY",
            "dev-admin-key" if environment == "dev" else "",
        ),
        search_verify_cert=_get_bool("SEARCH_VERIFY_CERT", environment != "dev"),
        staging_blob_endpoint=os.environ.get("STAGING_BLOB_ENDPOINT", ""),
        serving_blob_endpoint=os.environ.get("SERVING_BLOB_ENDPOINT", ""),
        staging_container_name=os.environ.get("STAGING_CONTAINER_NAME", "staging"),
        serving_container_name=os.environ.get("SERVING_CONTAINER_NAME", "serving"),
        azurite_connection_string=os.environ.get("AZURITE_CONNECTION_STRING", ""),
        cosmos_endpoint=os.environ.get(
            "COSMOS_ENDPOINT",
            "https://localhost:8081/" if environment == "dev" else "",
        ),
        cosmos_key=os.environ.get(
            "COSMOS_KEY",
            _DEFAULT_COSMOS_KEY if environment == "dev" else "",
        ),
        cosmos_verify_cert=_get_bool("COSMOS_VERIFY_CERT", environment != "dev"),
    )
    return _config


# Backward compat: `from shared.config import config` still works.
# This is a lazy property that loads on first access.
class _ConfigProxy:
    """Proxy that loads config on first attribute access."""

    def __getattr__(self, name: str):
        return getattr(get_config(), name)


config = _ConfigProxy()
