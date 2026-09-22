"""
Tests for ephemeral session memory (Phase 13).
Verifies in-process state storage, search, clearing, and independence from SQLite storage.
"""

from memory.models import MemoryCategory, MemorySource
from memory.session import SessionMemory


class TestSessionMemory:
    """Test ephemeral SessionMemory operations."""

    def test_set_and_get_context(self) -> None:
        session = SessionMemory()
        session.set_context("current_task", "implementing phase 13", importance=0.8)
        assert session.get_context("current_task") == "implementing phase 13"
        assert session.get_context("nonexistent", default="default_val") == "default_val"

    def test_list_context(self) -> None:
        session = SessionMemory()
        session.set_context("k1", "v1")
        session.set_context("k2", "v2")
        all_ctx = session.list_context()
        assert all_ctx == {"k1": "v1", "k2": "v2"}

    def test_search_session(self) -> None:
        session = SessionMemory()
        session.set_context("topic", "memory system architecture")
        session.set_context("status", "in progress")

        results = session.search("architecture")
        assert len(results) == 1
        assert results[0]["key"] == "topic"

    def test_clear_session(self) -> None:
        session = SessionMemory()
        session.set_context("temp", "value")
        assert session.count() == 1
        session.clear()
        assert session.count() == 0
        assert session.get_context("temp") is None

    def test_to_memory_items(self) -> None:
        session = SessionMemory()
        session.set_context("active_project", "CHARVIS", importance=0.9, source=MemorySource.CONVERSATION)

        items = session.to_memory_items()
        assert len(items) == 1
        assert items[0].category == MemoryCategory.SESSION
        assert items[0].key == "active_project"
        assert items[0].value == "CHARVIS"
        assert items[0].importance == 0.9
