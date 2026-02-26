"""Shared test fixtures for web-app tests."""

import os

# Config is loaded at import time — set required env vars before any app
# modules are imported by the test collector.
os.environ.setdefault("AGENT_ENDPOINT", "http://localhost:8088")
os.environ.setdefault("SERVING_BLOB_ENDPOINT", "https://test.blob.core.windows.net/")

import pytest
