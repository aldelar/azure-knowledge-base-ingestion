"""Integration tests for CosmosDataLayer — runs against real Cosmos DB.

These tests verify CRUD operations against the actual Azure Cosmos DB
instance.  They require valid Azure credentials and the following env
vars (normally populated by ``azd env get-values``):

- COSMOS_ENDPOINT
- COSMOS_DATABASE_NAME (defaults to "kb-agent")

Usage:
    make azure-test-app      # runs all web app integration tests
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from chainlit.types import Feedback, Pagination, ThreadFilter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data_layer():
    """Create a real CosmosDataLayer backed by Azure Cosmos DB."""
    from app.data_layer import CosmosDataLayer

    return CosmosDataLayer()


@pytest.fixture
def thread_id():
    """Generate a unique thread ID for each test."""
    return f"test-{_unique_id()}"


@pytest.fixture
def user_id():
    """Unique user ID to avoid cross-test interference."""
    return f"test-user-{_unique_id()}"


# ---------------------------------------------------------------------------
# Thread CRUD
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestThreadLifecycle:
    """Create → read → update → delete a thread."""

    @pytest.mark.asyncio
    async def test_create_and_read_thread(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="Integration Test", user_id=user_id
        )
        thread = await data_layer.get_thread(thread_id)
        assert thread is not None
        assert thread["id"] == thread_id
        assert thread["name"] == "Integration Test"

        # Cleanup
        await data_layer.delete_thread(thread_id)

    @pytest.mark.asyncio
    async def test_update_thread_name(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="Original", user_id=user_id
        )
        await data_layer.update_thread(thread_id=thread_id, name="Updated")
        thread = await data_layer.get_thread(thread_id)
        assert thread["name"] == "Updated"

        # Cleanup
        await data_layer.delete_thread(thread_id)

    @pytest.mark.asyncio
    async def test_delete_thread(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="To Delete", user_id=user_id
        )
        await data_layer.delete_thread(thread_id)
        thread = await data_layer.get_thread(thread_id)
        assert thread is None


# ---------------------------------------------------------------------------
# Steps (messages)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStepOperations:
    """Add and update steps inside a thread."""

    @pytest.mark.asyncio
    async def test_create_step(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="Step Test", user_id=user_id
        )

        step_id = f"step-{_unique_id()}"
        step = {
            "id": step_id,
            "threadId": thread_id,
            "type": "user_message",
            "output": "Hello agent",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await data_layer.create_step(step)

        thread = await data_layer.get_thread(thread_id)
        assert any(s["id"] == step_id for s in thread["steps"])

        # Cleanup
        await data_layer.delete_thread(thread_id)

    @pytest.mark.asyncio
    async def test_update_step(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="Update Step", user_id=user_id
        )

        step_id = f"step-{_unique_id()}"
        step = {
            "id": step_id,
            "threadId": thread_id,
            "type": "assistant_message",
            "output": "Original",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await data_layer.create_step(step)

        step["output"] = "Updated answer"
        await data_layer.update_step(step)

        thread = await data_layer.get_thread(thread_id)
        updated = [s for s in thread["steps"] if s["id"] == step_id]
        assert len(updated) == 1
        assert updated[0]["output"] == "Updated answer"

        # Cleanup
        await data_layer.delete_thread(thread_id)


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestElementOperations:
    """Create and read elements attached to a thread."""

    @pytest.mark.asyncio
    async def test_create_and_get_element(self, data_layer, thread_id, user_id):
        await data_layer.update_thread(
            thread_id=thread_id, name="Element Test", user_id=user_id
        )

        element_id = f"el-{_unique_id()}"
        element = {
            "id": element_id,
            "threadId": thread_id,
            "type": "text",
            "name": "test-element",
            "display": "inline",
        }
        await data_layer.create_element(element)

        result = await data_layer.get_element(thread_id, element_id)
        assert result is not None
        assert result["id"] == element_id

        # Cleanup
        await data_layer.delete_thread(thread_id)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestUserManagement:
    """Create and retrieve users from Cosmos DB."""

    @pytest.mark.asyncio
    async def test_create_and_get_user(self, data_layer):
        from chainlit.user import User

        unique = _unique_id()
        user = User(identifier=f"test-{unique}", metadata={})
        persisted = await data_layer.create_user(user)
        assert persisted is not None
        assert persisted.identifier == f"test-{unique}"

        fetched = await data_layer.get_user(f"test-{unique}")
        assert fetched is not None
        assert fetched.identifier == f"test-{unique}"


# ---------------------------------------------------------------------------
# List threads
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestListThreads:
    """Verify list_threads returns threads for a given user."""

    @pytest.mark.asyncio
    async def test_list_returns_created_threads(self, data_layer, user_id):
        # Create two threads
        ids = [f"list-test-{_unique_id()}" for _ in range(2)]
        for tid in ids:
            await data_layer.update_thread(
                thread_id=tid, name=f"Thread {tid}", user_id=user_id
            )

        result = await data_layer.list_threads(
            pagination=Pagination(first=10),
            filters=ThreadFilter(userId=user_id),
        )
        listed_ids = {t["id"] for t in result.data}
        for tid in ids:
            assert tid in listed_ids, f"Thread {tid} not found in listing"

        # Cleanup
        for tid in ids:
            await data_layer.delete_thread(tid)
