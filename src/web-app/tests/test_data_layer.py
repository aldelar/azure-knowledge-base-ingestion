"""Tests for the Cosmos DB data layer."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from chainlit.types import Feedback, PageInfo, Pagination, ThreadFilter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_container():
    """Create a mock Cosmos container."""
    return MagicMock()


@pytest.fixture
def data_layer(mock_container):
    """Create a CosmosDataLayer with a mocked container."""
    with patch("app.data_layer._get_cosmos_client") as mock_client:
        mock_db = MagicMock()
        mock_db.get_container_client.return_value = mock_container
        mock_client.return_value.get_database_client.return_value = mock_db

        from app.data_layer import CosmosDataLayer
        layer = CosmosDataLayer()
        return layer


@pytest.fixture
def degraded_layer():
    """Create a CosmosDataLayer in degraded mode (no Cosmos connection)."""
    with patch("app.data_layer._get_cosmos_client") as mock_client:
        mock_client.return_value = None

        from app.data_layer import CosmosDataLayer
        layer = CosmosDataLayer()
        return layer


# ---------------------------------------------------------------------------
# User tests
# ---------------------------------------------------------------------------

class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "user:alice",
            "identifier": "alice",
            "displayName": "Alice",
            "metadata": {"role": "admin"},
            "createdAt": "2025-01-01T00:00:00+00:00",
        }
        user = await data_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"
        assert user.display_name == "Alice"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        user = await data_layer.get_user("nonexistent")
        assert user is None


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_and_returns_user(self, data_layer, mock_container):
        from chainlit.user import User
        user = User(identifier="bob", display_name="Bob")
        result = await data_layer.create_user(user)
        assert result is not None
        assert result.identifier == "bob"
        mock_container.upsert_item.assert_called_once()


# ---------------------------------------------------------------------------
# Thread tests
# ---------------------------------------------------------------------------

class TestUpdateThread:
    @pytest.mark.asyncio
    async def test_creates_new_thread(self, data_layer, mock_container):
        # _read_thread_doc returns None → cross-partition query returns empty
        mock_container.query_items.return_value = iter([])

        await data_layer.update_thread(
            thread_id="t1",
            name="Test Thread",
            user_id="alice",
        )
        mock_container.upsert_item.assert_called_once()
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "t1"
        assert doc["name"] == "Test Thread"
        assert doc["userId"] == "alice"

    @pytest.mark.asyncio
    async def test_updates_existing_thread(self, data_layer, mock_container):
        existing = {
            "id": "t1",
            "userId": "alice",
            "name": "Old",
            "createdAt": "2025-01-01",
            "steps": [],
            "elements": [],
        }
        mock_container.query_items.return_value = iter([existing])

        await data_layer.update_thread(thread_id="t1", name="New Name")
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["name"] == "New Name"


class TestGetThread:
    @pytest.mark.asyncio
    async def test_returns_thread(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([{
            "id": "t1",
            "userId": "alice",
            "createdAt": "2025-01-01",
            "name": "Test",
            "steps": [{"type": "user_message", "output": "Hello"}],
            "elements": [],
        }])

        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert thread["id"] == "t1"
        assert len(thread["steps"]) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([])
        thread = await data_layer.get_thread("missing")
        assert thread is None


class TestListThreads:
    @pytest.mark.asyncio
    async def test_lists_user_threads(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-02", "name": "Thread 1", "userId": "alice"},
            {"id": "t2", "createdAt": "2025-01-01", "name": "Thread 2", "userId": "alice"},
        ])

        result = await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert len(result.data) == 2
        assert result.pageInfo.hasNextPage is False

    @pytest.mark.asyncio
    async def test_paginates(self, data_layer, mock_container):
        # Return 3 items when page_size=2 → hasNextPage=True, only 2 returned
        items = [
            {"id": f"t{i}", "createdAt": "2025-01-01", "name": f"T{i}", "userId": "u"}
            for i in range(3)
        ]
        mock_container.query_items.return_value = iter(items)

        result = await data_layer.list_threads(
            pagination=Pagination(first=2),
            filters=ThreadFilter(userId="u"),
        )
        assert len(result.data) == 2
        assert result.pageInfo.hasNextPage is True


class TestDeleteThread:
    @pytest.mark.asyncio
    async def test_deletes_existing_thread(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([{
            "id": "t1", "userId": "alice", "steps": [], "elements": [],
        }])
        await data_layer.delete_thread("t1")
        mock_container.delete_item.assert_called_once_with(
            item="t1", partition_key="alice"
        )

    @pytest.mark.asyncio
    async def test_no_error_when_not_found(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([])
        await data_layer.delete_thread("missing")
        mock_container.delete_item.assert_not_called()


class TestGetThreadAuthor:
    @pytest.mark.asyncio
    async def test_returns_clean_id_when_prefixed(self, data_layer, mock_container):
        """Legacy docs store userId as 'user:local-user'; author must be 'local-user'."""
        mock_container.query_items.return_value = iter([
            {"id": "t1", "userId": "user:local-user", "steps": [], "elements": []},
        ])
        author = await data_layer.get_thread_author("t1")
        assert author == "local-user"

    @pytest.mark.asyncio
    async def test_returns_clean_id_when_not_prefixed(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([
            {"id": "t2", "userId": "local-user", "steps": [], "elements": []},
        ])
        author = await data_layer.get_thread_author("t2")
        assert author == "local-user"

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_found(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([])
        author = await data_layer.get_thread_author("missing")
        assert author == ""


# ---------------------------------------------------------------------------
# Step tests
# ---------------------------------------------------------------------------

class TestCreateStep:
    @pytest.mark.asyncio
    async def test_appends_step(self, data_layer, mock_container):
        existing = {
            "id": "t1", "userId": "alice", "steps": [], "elements": [],
        }
        mock_container.query_items.return_value = iter([existing])

        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": "Hello!",
            "id": "s1",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert len(doc["steps"]) == 1
        assert doc["name"] == "Hello!"  # auto-title from first user message

    @pytest.mark.asyncio
    async def test_auto_creates_thread_when_not_found(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([])
        await data_layer.create_step({"threadId": "missing", "type": "user_message"})
        # Thread is auto-created on the fly when document doesn't exist
        mock_container.upsert_item.assert_called_once()
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "missing"
        assert len(doc["steps"]) == 1


class TestUpdateStep:
    @pytest.mark.asyncio
    async def test_replaces_existing_step(self, data_layer, mock_container):
        existing = {
            "id": "t1", "userId": "alice",
            "steps": [{"id": "s1", "output": "old"}],
            "elements": [],
        }
        mock_container.query_items.return_value = iter([existing])

        await data_layer.update_step({
            "threadId": "t1", "id": "s1", "output": "new",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["steps"][0]["output"] == "new"


# ---------------------------------------------------------------------------
# Feedback (no-op)
# ---------------------------------------------------------------------------

class TestNormalizeUserId:
    """Tests for the _normalize_user_id static helper."""

    def test_strips_user_prefix(self, data_layer):
        assert data_layer._normalize_user_id("user:alice") == "alice"

    def test_leaves_clean_id(self, data_layer):
        assert data_layer._normalize_user_id("alice") == "alice"

    def test_none_returns_default(self, data_layer):
        assert data_layer._normalize_user_id(None) == "local-user"

    def test_empty_returns_default(self, data_layer):
        assert data_layer._normalize_user_id("") == "local-user"


class TestUpdateThreadNormalization:
    """Verify update_thread strips the user: prefix before persisting."""

    @pytest.mark.asyncio
    async def test_strips_user_prefix_on_create(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([])

        await data_layer.update_thread(
            thread_id="t1",
            name="New",
            user_id="user:alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["userId"] == "alice"

    @pytest.mark.asyncio
    async def test_strips_user_prefix_on_update(self, data_layer, mock_container):
        existing = {
            "id": "t1",
            "userId": "user:alice",
            "name": "Old",
            "createdAt": "2025-01-01",
            "steps": [],
            "elements": [],
        }
        mock_container.query_items.return_value = iter([existing])

        await data_layer.update_thread(
            thread_id="t1",
            name="Updated",
            user_id="user:alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["userId"] == "alice"


class TestListThreadsCrossPartition:
    """Verify list_threads finds threads stored under both userId variants."""

    @pytest.mark.asyncio
    async def test_uses_cross_partition_query(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-01", "name": "T1", "userId": "alice"},
        ])

        await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )

        call_kwargs = mock_container.query_items.call_args[1]
        assert call_kwargs["enable_cross_partition_query"] is True
        # Query should use IN with both clean and prefixed variants
        params = {p["name"]: p["value"] for p in call_kwargs["parameters"]}
        assert params["@cleanId"] == "alice"
        assert params["@prefixedId"] == "user:alice"

    @pytest.mark.asyncio
    async def test_userIdentifier_strips_prefix(self, data_layer, mock_container):
        """A legacy doc with userId='user:bob' still gets clean userIdentifier."""
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-01", "name": "T1", "userId": "user:bob"},
        ])

        result = await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="bob"),
        )
        assert result.data[0]["userIdentifier"] == "bob"


class TestFeedback:
    @pytest.mark.asyncio
    async def test_upsert_returns_id(self, data_layer):
        fb = Feedback(value=1, id="fb1", forId="step1")
        result = await data_layer.upsert_feedback(fb)
        assert result == "fb1"

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, data_layer):
        assert await data_layer.delete_feedback("fb1") is True


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

class TestMisc:
    @pytest.mark.asyncio
    async def test_build_debug_url(self, data_layer):
        assert await data_layer.build_debug_url() == ""

    @pytest.mark.asyncio
    async def test_close(self, data_layer):
        await data_layer.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_get_favorite_steps(self, data_layer):
        assert await data_layer.get_favorite_steps("user1") == []


# ---------------------------------------------------------------------------
# Degraded mode (no Cosmos connection)
# ---------------------------------------------------------------------------

class TestDegradedMode:
    """Verify the data layer works gracefully when Cosmos is unavailable."""

    @pytest.mark.asyncio
    async def test_create_user_returns_non_persisted(self, degraded_layer):
        from chainlit.user import User
        user = User(identifier="alice", display_name="Alice")
        result = await degraded_layer.create_user(user)
        assert result is not None
        assert result.identifier == "alice"

    @pytest.mark.asyncio
    async def test_get_user_returns_none(self, degraded_layer):
        assert await degraded_layer.get_user("alice") is None

    @pytest.mark.asyncio
    async def test_list_threads_returns_empty(self, degraded_layer):
        result = await degraded_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert result.data == []
        assert result.pageInfo.hasNextPage is False

    @pytest.mark.asyncio
    async def test_get_thread_returns_none(self, degraded_layer):
        assert await degraded_layer.get_thread("t1") is None

    @pytest.mark.asyncio
    async def test_update_thread_no_error(self, degraded_layer):
        await degraded_layer.update_thread(thread_id="t1", name="Test")

    @pytest.mark.asyncio
    async def test_create_step_no_error(self, degraded_layer):
        await degraded_layer.create_step({"threadId": "t1", "type": "user_message"})

    @pytest.mark.asyncio
    async def test_delete_thread_no_error(self, degraded_layer):
        await degraded_layer.delete_thread("t1")
