"""Shared test fixtures for agent tests.

Environment variables MUST be set at module level (before any agent
modules are imported) because ``agent.config`` evaluates ``_load_config()``
at import time.  pytest processes conftest.py before collecting test
modules, so ``os.environ.setdefault(...)`` here runs early enough.
"""

import os

# Set required env vars before any agent code is imported
os.environ.setdefault("AI_SERVICES_ENDPOINT", "https://test-ai.cognitiveservices.azure.com/")
os.environ.setdefault("SEARCH_ENDPOINT", "https://test-search.search.windows.net")
os.environ.setdefault("SERVING_BLOB_ENDPOINT", "https://teststorage.blob.core.windows.net/")
os.environ.setdefault("PROJECT_ENDPOINT", "https://test-ai.services.ai.azure.com/api/projects/test-project")

import pytest  # noqa: E402
