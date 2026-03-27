"""Agent configuration — lazy-loaded, environment-aware settings."""

import os
from dataclasses import dataclass
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


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/agent/
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

    # Foundry project endpoint
    project_endpoint: str = ""

    # Azure AI Services endpoint
    ai_services_endpoint: str = ""

    # Local Ollama endpoint
    ollama_endpoint: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"

    # Agent model deployment name
    agent_model_deployment_name: str = "gpt-4.1"

    # Embedding model deployment name
    embedding_deployment_name: str = "text-embedding-3-small"
    embedding_vector_dimensions: int = 1536

    # Azure AI Search
    search_endpoint: str = ""
    search_index_name: str = "kb-articles"
    search_api_key: str = ""
    search_verify_cert: bool = True

    # Azure Blob Storage — serving account (images for vision)
    serving_blob_endpoint: str = ""
    serving_container_name: str = "serving"
    azurite_connection_string: str = ""

    # Cosmos DB — agent session persistence (optional: empty = no persistence)
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_verify_cert: bool = True
    cosmos_database_name: str = "kb-agent"
    cosmos_sessions_container: str = "agent-sessions"

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


def _load_config() -> Config:
    """Load configuration from environment."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    environment = os.environ.get("ENVIRONMENT", "prod").strip().lower() or "prod"

    return Config(
        environment=environment,
        project_endpoint=os.environ.get(
            "PROJECT_ENDPOINT",
            os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        ),
        ai_services_endpoint=os.environ.get("AI_SERVICES_ENDPOINT", ""),
        ollama_endpoint=os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1"),
        ollama_api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        agent_model_deployment_name=os.environ.get("AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        embedding_vector_dimensions=_get_int(
            "EMBEDDING_VECTOR_DIMENSIONS",
            _default_vector_dimensions(environment),
        ),
        search_endpoint=os.environ.get("SEARCH_ENDPOINT", ""),
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
        search_api_key=os.environ.get(
            "SEARCH_API_KEY",
            "dev-admin-key" if environment == "dev" else "",
        ),
        search_verify_cert=_get_bool("SEARCH_VERIFY_CERT", environment != "dev"),
        serving_blob_endpoint=os.environ.get("SERVING_BLOB_ENDPOINT", ""),
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
        cosmos_database_name=os.environ.get("COSMOS_DATABASE_NAME", "kb-agent"),
        cosmos_sessions_container=os.environ.get("COSMOS_SESSIONS_CONTAINER", "agent-sessions"),
    )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = _load_config()
    return _config


class _ConfigProxy:
    def __getattr__(self, name: str):
        return getattr(get_config(), name)


config = _ConfigProxy()
