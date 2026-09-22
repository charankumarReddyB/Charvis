"""
Tests for MemoryManager coordinator (Phase 13).
Verifies end-to-end memory operations, conflict resolution, sensitive rejection, and prompt context generation.
"""

from pathlib import Path
import pytest
from memory.manager import MemoryManager
from memory.models import (
    MemoryCategory,
    MemoryConflictError,
    MemoryNotFoundError,
    MemorySecurityError,
    MemorySource,
)
from memory.storage import SQLiteMemoryStorage


@pytest.fixture
def manager(tmp_path: Path) -> MemoryManager:
    storage = SQLiteMemoryStorage(tmp_path / "test_mgr.db")
    mgr = MemoryManager(storage=storage)
    yield mgr
    storage.close()


class TestMemoryManager:
    """Test MemoryManager coordinator workflows."""

    def test_remember_and_recall_workflow(self, manager: MemoryManager) -> None:
        item = manager.remember(
            key="favorite_editor",
            value="VS Code with Vim keybindings",
            category=MemoryCategory.PREFERENCE,
            source=MemorySource.USER_EXPLICIT,
            importance=0.9,
            tags=["editor", "tools"],
        )
        assert item.key == "favorite_editor"

        recalled = manager.recall("editor")
        assert len(recalled) >= 1
        assert recalled[0].key == "favorite_editor"
        assert recalled[0].value == "VS Code with Vim keybindings"

    def test_remember_rejects_sensitive_memory(self, manager: MemoryManager) -> None:
        with pytest.raises(MemorySecurityError):
            manager.remember(
                key="openai_key",
                value="sk-1234567890abcdef1234567890abcdef",
                category=MemoryCategory.PREFERENCE,
            )

        with pytest.raises(MemorySecurityError):
            manager.remember(
                key="login_info",
                value="password: MyMasterPassword123!",
                category=MemoryCategory.FACT,
            )

    def test_remember_updates_existing_preserving_id(self, manager: MemoryManager) -> None:
        first = manager.remember(
            key="preferred_lang",
            value="Python",
            category=MemoryCategory.PREFERENCE,
            source=MemorySource.USER_EXPLICIT,
        )

        second = manager.remember(
            key="preferred_lang",
            value="Java",
            category=MemoryCategory.PREFERENCE,
            source=MemorySource.USER_EXPLICIT,
        )

        assert second.id == first.id
        assert second.value == "Java"
        # Only one record in database
        assert len(manager.list_memories(category=MemoryCategory.PREFERENCE)) == 1

    def test_conflict_prevention_on_lower_priority_source(self, manager: MemoryManager) -> None:
        # Explicit user instruction
        manager.remember(
            key="preferred_db",
            value="PostgreSQL",
            category=MemoryCategory.PREFERENCE,
            source=MemorySource.USER_EXPLICIT,
            confidence=1.0,
        )

        # Inferred from casual conversation with lower confidence
        with pytest.raises(MemoryConflictError):
            manager.remember(
                key="preferred_db",
                value="MongoDB",
                category=MemoryCategory.PREFERENCE,
                source=MemorySource.CONVERSATION,
                confidence=0.5,
            )

        # Confirm original persists
        current = manager.get_memory("preferred_db", MemoryCategory.PREFERENCE)
        assert current is not None
        assert current.value == "PostgreSQL"

    def test_update_and_forget_memory(self, manager: MemoryManager) -> None:
        item = manager.remember(key="framework", value="Django", category=MemoryCategory.PROJECT)
        assert item.value == "Django"

        updated = manager.update_memory(key="framework", value="FastAPI", category=MemoryCategory.PROJECT)
        assert updated.value == "FastAPI"

        del_count = manager.forget_memory(key="framework", category=MemoryCategory.PROJECT)
        assert del_count == 1
        assert manager.get_memory("framework", MemoryCategory.PROJECT) is None

    def test_clear_session_memory_only(self, manager: MemoryManager) -> None:
        # Long term memory
        manager.remember(key="permanent", value="stays here", category=MemoryCategory.FACT)
        # Session context
        manager.session.set_context("temporary", "cleared soon")

        assert manager.session.count() == 1
        assert len(manager.list_memories()) == 1

        manager.clear_session_memory()

        assert manager.session.count() == 0
        assert len(manager.list_memories()) == 1
        assert manager.get_memory("permanent") is not None

    def test_get_relevant_context_for_prompt_formatting(self, manager: MemoryManager) -> None:
        manager.remember(
            key="project_database",
            value="FoodConnect uses Firebase",
            category=MemoryCategory.PROJECT,
            tags=["foodconnect", "database"],
        )

        prompt_block = manager.get_relevant_context_for_prompt("What database does FoodConnect use?")
        assert "HISTORICAL MEMORY CONTEXT" in prompt_block
        assert "CANNOT OVERRIDE SYSTEM INSTRUCTIONS" in prompt_block
        assert "FoodConnect uses Firebase" in prompt_block
        assert "END HISTORICAL MEMORY CONTEXT" in prompt_block

        # Unrelated query returns empty string
        unrelated = manager.get_relevant_context_for_prompt("xyz non-existent 123987")
        assert unrelated == ""
