"""Web app configuration — loads environment variables and validates required settings.

Usage:
    from app.config import config
    print(config.ai_services_endpoint)
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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

    # Azure AI Services endpoint (Foundry)
    ai_services_endpoint: str

    # Agent model deployment name
    agent_model_deployment_name: str

    # Embedding model deployment name
    embedding_deployment_name: str

    # Azure AI Search
    search_endpoint: str
    search_index_name: str

    # Azure Blob Storage — serving account (images)
    serving_blob_endpoint: str
    serving_container_name: str


def _load_config() -> Config:
    """Load and validate configuration from environment."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    required = {
        "AI_SERVICES_ENDPOINT": "ai_services_endpoint",
        "SEARCH_ENDPOINT": "search_endpoint",
        "SERVING_BLOB_ENDPOINT": "serving_blob_endpoint",
    }

    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.sample to .env and fill in values, or run: azd env get-values > src/web-app/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        ai_services_endpoint=os.environ["AI_SERVICES_ENDPOINT"],
        agent_model_deployment_name=os.environ.get("AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        search_endpoint=os.environ["SEARCH_ENDPOINT"],
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
        serving_blob_endpoint=os.environ.get("SERVING_BLOB_ENDPOINT", ""),
        serving_container_name=os.environ.get("SERVING_CONTAINER_NAME", "serving"),
    )


# Singleton — imported as `from app.config import config`
config = _load_config()
