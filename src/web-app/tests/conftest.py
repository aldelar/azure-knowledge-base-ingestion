"""Shared test fixtures for web-app tests."""

import os

_DEFAULT_COSMOS_KEY = (
	"C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPM"
	"bIZnqyMsEcaGQy67XIw/Jw=="
)

# Config is loaded at import time — set required env vars before any app
# modules are imported by the test collector.
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("AGENT_ENDPOINT", "http://localhost:8088")
os.environ.setdefault("SERVING_BLOB_ENDPOINT", "http://localhost:10000/devstoreaccount1")
os.environ.setdefault(
	"AZURITE_CONNECTION_STRING",
	"DefaultEndpointsProtocol=http;"
	"AccountName=devstoreaccount1;"
	"AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
	"BlobEndpoint=http://localhost:10000/devstoreaccount1;"
	"QueueEndpoint=http://localhost:10001/devstoreaccount1;"
	"TableEndpoint=http://localhost:10002/devstoreaccount1;"
)
os.environ.setdefault("SERVING_CONTAINER_NAME", "serving")
os.environ.setdefault("COSMOS_ENDPOINT", "https://localhost:8081/")
os.environ.setdefault("COSMOS_KEY", _DEFAULT_COSMOS_KEY)
os.environ.setdefault("COSMOS_VERIFY_CERT", "false")
os.environ.setdefault("COSMOS_DATABASE_NAME", "kb-agent")
os.environ.setdefault("COSMOS_CONVERSATIONS_CONTAINER", "conversations")
os.environ.setdefault("COSMOS_MESSAGES_CONTAINER", "messages")
os.environ.setdefault("COSMOS_REFERENCES_CONTAINER", "references")

import pytest


@pytest.fixture
def test_serving_container_name() -> str:
    """Return the blob container reserved for integration-style tests."""
    return "serving-test"


@pytest.fixture
def test_cosmos_container_names() -> dict[str, str]:
    """Return Cosmos container names reserved for integration-style tests."""
    return {
        "conversations": "conversations-test",
        "messages": "messages-test",
        "references": "references-test",
    }
