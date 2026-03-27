"""Web app configuration — lazy-loaded, environment-aware settings."""

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


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/web-app/
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

    # Agent endpoint (local: http://localhost:8088, deployed: Foundry endpoint)
    agent_endpoint: str = "http://localhost:8088"

    # Azure Blob Storage — serving account (images)
    serving_blob_endpoint: str = ""
    serving_container_name: str = "serving"
    azurite_connection_string: str = ""

    # Cosmos DB — conversation persistence (4-container model)
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_verify_cert: bool = True
    cosmos_database_name: str = "kb-agent"
    cosmos_sessions_container: str = "agent-sessions"
    cosmos_conversations_container: str = "conversations"
    cosmos_messages_container: str = "messages"
    cosmos_references_container: str = "references"

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
        agent_endpoint=os.environ.get("AGENT_ENDPOINT", "http://localhost:8088"),
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
        cosmos_conversations_container=os.environ.get("COSMOS_CONVERSATIONS_CONTAINER", "conversations"),
        cosmos_messages_container=os.environ.get("COSMOS_MESSAGES_CONTAINER", "messages"),
        cosmos_references_container=os.environ.get("COSMOS_REFERENCES_CONTAINER", "references"),
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
