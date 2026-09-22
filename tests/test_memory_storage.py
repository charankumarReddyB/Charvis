"""
Tests for SQLite persistent memory storage (Phase 13).
Verifies parameterized SQL execution, schema creation, CRUD operations, and expiration cleanup.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from memory.models import (
    MemoryCategory,
    MemoryItem,
    MemorySource,
    MemoryStorageError,
)
from memory.storage import SQLiteMemoryStorage


@pytest.fixture
def temp_db(tmp_path: Path) -> SQLiteMemoryStorage:
    db_file = tmp_path / "test_memory.db"
    storage = SQLiteMemoryStorage(db_file)
    yield storage
    storage.close()


class TestSQLiteMemoryStorage:
    """Test SQLiteMemoryStorage implementation."""

    def test_schema_initialization(self, temp_db: SQLiteMemoryStorage) -> None:
        conn = temp_db._get_connection()
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories';")
        assert cur.fetchone() is not None

    def test_create_and_get_memory(self, temp_db: SQLiteMemoryStorage) -> None:
        item = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="theme",
            value="dark",
            source=MemorySource.USER_EXPLICIT,
            confidence=1.0,
            tags=["ui", "appearance"],
        )
        saved = temp_db.create(item)
        assert saved.id == item.id

        retrieved = temp_db.get(item.id)
        assert retrieved is not None
        assert retrieved.key == "theme"
        assert retrieved.value == "dark"
        assert retrieved.tags == ["ui", "appearance"]
        assert retrieved.confidence == 1.0

    def test_get_by_key(self, temp_db: SQLiteMemoryStorage) -> None:
        item = MemoryItem(
            category=MemoryCategory.PROJECT,
            key="framework",
            value="FastAPI",
            source=MemorySource.SYSTEM,
        )
        temp_db.create(item)

        found = temp_db.get_by_key("framework", MemoryCategory.PROJECT)
        assert found is not None
        assert found.value == "FastAPI"

        missing = temp_db.get_by_key("nonexistent")
        assert missing is None

    def test_update_memory(self, temp_db: SQLiteMemoryStorage) -> None:
        item = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="editor",
            value="Sublime",
            source=MemorySource.USER_EXPLICIT,
        )
        temp_db.create(item)

        item.value = "VSCode"
        item.updated_at = datetime.now(timezone.utc).isoformat()
        updated = temp_db.update(item)
        assert updated.value == "VSCode"

        fetched = temp_db.get(item.id)
        assert fetched is not None
        assert fetched.value == "VSCode"

    def test_delete_by_id(self, temp_db: SQLiteMemoryStorage) -> None:
        item = MemoryItem(
            category=MemoryCategory.FACT,
            key="city",
            value="San Francisco",
            source=MemorySource.CONVERSATION,
        )
        temp_db.create(item)
        assert temp_db.get(item.id) is not None

        deleted = temp_db.delete(item.id)
        assert deleted is True
        assert temp_db.get(item.id) is None

        # Deleting non-existent returns False
        assert temp_db.delete("non-existent-id") is False

    def test_delete_by_key(self, temp_db: SQLiteMemoryStorage) -> None:
        item1 = MemoryItem(
            category=MemoryCategory.FACT,
            key="delete_me",
            value="val1",
            source=MemorySource.SYSTEM,
        )
        temp_db.create(item1)

        count = temp_db.delete_by_key("delete_me")
        assert count == 1
        assert temp_db.get(item1.id) is None

    def test_list_and_filter(self, temp_db: SQLiteMemoryStorage) -> None:
        temp_db.create(
            MemoryItem(category=MemoryCategory.PREFERENCE, key="k1", value="v1", source=MemorySource.USER_EXPLICIT)
        )
        temp_db.create(
            MemoryItem(category=MemoryCategory.PROJECT, key="k2", value="v2", source=MemorySource.SYSTEM)
        )

        all_items = temp_db.list()
        assert len(all_items) == 2

        pref_items = temp_db.list(category=MemoryCategory.PREFERENCE)
        assert len(pref_items) == 1
        assert pref_items[0].key == "k1"

    def test_search(self, temp_db: SQLiteMemoryStorage) -> None:
        temp_db.create(
            MemoryItem(
                category=MemoryCategory.PROJECT,
                key="database",
                value="PostgreSQL backend",
                source=MemorySource.USER_EXPLICIT,
                tags=["db", "sql"],
            )
        )
        temp_db.create(
            MemoryItem(
                category=MemoryCategory.PROJECT,
                key="auth",
                value="OAuth2 provider",
                source=MemorySource.USER_EXPLICIT,
            )
        )

        results = temp_db.search("PostgreSQL")
        assert len(results) == 1
        assert results[0].key == "database"

        tag_results = temp_db.search("sql")
        assert len(tag_results) == 1
        assert tag_results[0].key == "database"

    def test_parameterized_sql_injection_defense(self, temp_db: SQLiteMemoryStorage) -> None:
        malicious_key = "test'; DROP TABLE memories; --"
        item = MemoryItem(
            category=MemoryCategory.FACT,
            key=malicious_key,
            value="safe value",
            source=MemorySource.USER_EXPLICIT,
        )
        temp_db.create(item)

        # Confirm table still exists and record was stored as literal string
        found = temp_db.get_by_key(malicious_key)
        assert found is not None
        assert found.key == malicious_key

    def test_cleanup_expired(self, temp_db: SQLiteMemoryStorage) -> None:
        # Expired item
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        expired_item = MemoryItem(
            category=MemoryCategory.SESSION,
            key="old_temp",
            value="old_val",
            source=MemorySource.CONVERSATION,
            expires_at=past_iso,
        )
        temp_db.create(expired_item)

        # Active item
        future_iso = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        active_item = MemoryItem(
            category=MemoryCategory.SESSION,
            key="future_temp",
            value="future_val",
            source=MemorySource.CONVERSATION,
            expires_at=future_iso,
        )
        temp_db.create(active_item)

        purged = temp_db.cleanup_expired()
        assert purged == 1
        assert temp_db.get(expired_item.id) is None
        assert temp_db.get(active_item.id) is not None
