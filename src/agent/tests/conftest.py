"""Shared test fixtures for agent tests.

Environment variables MUST be set at module level (before any agent
modules are imported) because ``agent.config`` evaluates ``_load_config()``
at import time.  pytest processes conftest.py before collecting test
modules, so ``os.environ.setdefault(...)`` here runs early enough.
"""

import os

# Set required env vars before any agent code is imported
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("AI_SERVICES_ENDPOINT", "")
os.environ.setdefault("AGENT_ENDPOINT", "http://localhost:8088")
os.environ.setdefault("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
os.environ.setdefault("OLLAMA_API_KEY", "ollama")
os.environ.setdefault("AGENT_MODEL_DEPLOYMENT_NAME", "phi4-mini")
os.environ.setdefault("EMBEDDING_DEPLOYMENT_NAME", "mxbai-embed-large")
os.environ.setdefault("SEARCH_ENDPOINT", "https://localhost:7250")
os.environ.setdefault("SEARCH_INDEX_NAME", "kb-articles")
os.environ.setdefault("SEARCH_API_KEY", "dev-admin-key")
os.environ.setdefault("SEARCH_VERIFY_CERT", "false")
os.environ.setdefault("SERVING_BLOB_ENDPOINT", "http://localhost:10000/devstoreaccount1")
os.environ.setdefault("PROJECT_ENDPOINT", "")
os.environ.setdefault("COSMOS_DATABASE_NAME", "kb-agent-test")

import pytest  # noqa: E402


@pytest.fixture
def test_search_index_name() -> str:
    """Return the search index reserved for integration-style tests."""
    return "kb-articles"


@pytest.fixture
def test_session_container_name() -> str:
    """Return the Cosmos sessions container reserved for integration-style tests."""
    return "agent-sessions-test"
