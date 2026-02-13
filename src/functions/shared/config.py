"""Shared configuration — loads environment variables and validates required settings.

Usage:
    from shared.config import config
    print(config.ai_services_endpoint)
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


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

    # Azure AI Services (Content Understanding + Embeddings)
    ai_services_endpoint: str

    # Embedding model deployment name
    embedding_deployment_name: str

    # Azure AI Search
    search_endpoint: str
    search_index_name: str

    # Local paths (for Epic 1 — local file I/O mode)
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)

    @property
    def staging_path(self) -> Path:
        return self.project_root / "kb" / "staging"

    @property
    def serving_path(self) -> Path:
        return self.project_root / "kb" / "serving"


def _load_config() -> Config:
    """Load and validate configuration from environment."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    required = {
        "AI_SERVICES_ENDPOINT": "ai_services_endpoint",
        "SEARCH_ENDPOINT": "search_endpoint",
    }

    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.sample to .env and fill in values, or run: azd env get-values > src/functions/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        ai_services_endpoint=os.environ["AI_SERVICES_ENDPOINT"],
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        search_endpoint=os.environ["SEARCH_ENDPOINT"],
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
    )


# Singleton — imported as `from shared.config import config`
config = _load_config()
