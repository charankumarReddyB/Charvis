"""
Tests for memory models, enums, and data integrity (Phase 13).
"""

from datetime import datetime, timedelta, timezone
import pytest
from memory.models import (
    MemoryCategory,
    MemoryItem,
    MemorySource,
    MemoryValidationError,
)


class TestMemoryModels:
    """Test MemoryCategory, MemorySource, and MemoryItem validation."""

    def test_memory_item_creation_defaults(self) -> None:
        item = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="preferred_language",
            value="Python",
            source=MemorySource.USER_EXPLICIT,
        )
        assert item.category == MemoryCategory.PREFERENCE
        assert item.key == "preferred_language"
        assert item.value == "Python"
        assert item.source == MemorySource.USER_EXPLICIT
        assert item.confidence == 0.9
        assert item.importance == 0.5
        assert len(item.id) > 0
        assert item.enabled is True
        assert item.sensitive is False
        assert item.is_expired is False

    def test_category_string_coercion_and_validation(self) -> None:
        item = MemoryItem(
            category="fact",  # type: ignore
            key="os",
            value="Windows 11",
            source=MemorySource.SYSTEM,
        )
        assert item.category == MemoryCategory.FACT

        with pytest.raises(MemoryValidationError) as exc:
            MemoryItem(
                category="INVALID_CATEGORY",  # type: ignore
                key="os",
                value="Windows 11",
                source=MemorySource.SYSTEM,
            )
        assert "Invalid memory category" in str(exc.value)

    def test_source_string_coercion_and_validation(self) -> None:
        item = MemoryItem(
            category=MemoryCategory.WORKFLOW,
            key="git_flow",
            value="feature branch",
            source="user_explicit",  # type: ignore
        )
        assert item.source == MemorySource.USER_EXPLICIT

        with pytest.raises(MemoryValidationError) as exc:
            MemoryItem(
                category=MemoryCategory.WORKFLOW,
                key="git_flow",
                value="feature branch",
                source="UNKNOWN_SOURCE",  # type: ignore
            )
        assert "Invalid memory source" in str(exc.value)

    def test_empty_or_oversized_key_rejected(self) -> None:
        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                key="   ",
                value="val",
                source=MemorySource.USER_EXPLICIT,
            )

        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                key="k" * 201,
                value="val",
                source=MemorySource.USER_EXPLICIT,
            )

    def test_empty_or_oversized_value_rejected(self) -> None:
        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                key="my_key",
                value="   ",
                source=MemorySource.USER_EXPLICIT,
            )

        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                key="my_key",
                value="v" * 10001,
                source=MemorySource.USER_EXPLICIT,
            )

    def test_confidence_and_importance_bounds(self) -> None:
        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.FACT,
                key="k",
                value="v",
                source=MemorySource.SYSTEM,
                confidence=1.5,
            )

        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.FACT,
                key="k",
                value="v",
                source=MemorySource.SYSTEM,
                importance=-0.1,
            )

    def test_tags_sanitization_and_bounds(self) -> None:
        item = MemoryItem(
            category=MemoryCategory.PROJECT,
            key="proj",
            value="CHARVIS",
            source=MemorySource.USER_EXPLICIT,
            tags=["AI", "python", "  AI  ", "a" * 100],
        )
        assert "ai" not in item.tags  # Case preserved in model but deduplicated
        assert len(item.tags) == 3
        # Tag length clamped to 50
        assert len(item.tags[2]) == 50

    def test_expires_at_format_and_is_expired(self) -> None:
        # Invalid format
        with pytest.raises(MemoryValidationError):
            MemoryItem(
                category=MemoryCategory.SESSION,
                key="temp",
                value="val",
                source=MemorySource.CONVERSATION,
                expires_at="not-a-date",
            )

        # Future timestamp
        future_iso = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        future_item = MemoryItem(
            category=MemoryCategory.SESSION,
            key="temp",
            value="val",
            source=MemorySource.CONVERSATION,
            expires_at=future_iso,
        )
        assert future_item.is_expired is False

        # Past timestamp
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        past_item = MemoryItem(
            category=MemoryCategory.SESSION,
            key="temp",
            value="val",
            source=MemorySource.CONVERSATION,
            expires_at=past_iso,
        )
        assert past_item.is_expired is True

    def test_serialization_roundtrip(self) -> None:
        item = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="editor",
            value="VSCode",
            source=MemorySource.USER_EXPLICIT,
            confidence=0.95,
            importance=0.8,
            tags=["tool", "ide"],
        )
        data = item.to_dict()
        assert data["key"] == "editor"
        assert data["category"] == "PREFERENCE"
        assert data["source"] == "USER_EXPLICIT"

        restored = MemoryItem.from_dict(data)
        assert restored.id == item.id
        assert restored.category == item.category
        assert restored.key == item.key
        assert restored.value == item.value
        assert restored.tags == item.tags
