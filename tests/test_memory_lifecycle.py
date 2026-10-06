"""
Unit tests for memory subsystem resource lifecycle and bounded retrieval (Phase 17).
"""

from pathlib import Path
import tempfile
import pytest
from memory.manager import MemoryManager
from memory.storage import SQLiteMemoryStorage


def test_sqlite_memory_storage_lifecycle():
    """Verify SQLiteMemoryStorage initializes, operates, and closes cleanly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_memory.db"
        storage = SQLiteMemoryStorage(db_path=db_path)

        assert db_path.exists()

        # Insert test item
        storage.save(
            key="test_key",
            value="test_value",
            category="user_preference",
            confidence=0.9,
        )

        item = storage.get("test_key")
        assert item is not None
        assert item.value == "test_value"

        # Close cleanly
        storage.close()


def test_memory_storage_idempotent_close():
    """Verify calling close() multiple times on storage is safe and idempotent."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_memory.db"
        storage = SQLiteMemoryStorage(db_path=db_path)
        storage.close()
        storage.close()


def test_memory_bounded_retrieval():
    """Verify retrieval respects bounded limits."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_memory.db"
        storage = SQLiteMemoryStorage(db_path=db_path)

        for i in range(15):
            storage.save(key=f"k_{i}", value=f"v_{i}", category="facts", confidence=0.8)

        # Query with limit 5
        results = storage.list(limit=5)
        assert len(results) == 5

        storage.close()
