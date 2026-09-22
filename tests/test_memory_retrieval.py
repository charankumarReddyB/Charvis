"""
Tests for deterministic memory retrieval and relevance scoring (Phase 13).
"""

from datetime import datetime, timedelta, timezone
from memory.models import (
    MemoryCategory,
    MemoryItem,
    MemorySource,
)
from memory.retrieval import MemoryRetrieval


class TestMemoryRetrieval:
    """Test deterministic scoring and ranking."""

    def test_exact_key_match_ranks_highest(self) -> None:
        retrieval = MemoryRetrieval(min_confidence=0.3)

        item1 = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="preferred_language",
            value="Python",
            source=MemorySource.USER_EXPLICIT,
            confidence=1.0,
            importance=0.8,
        )
        item2 = MemoryItem(
            category=MemoryCategory.FACT,
            key="general_notes",
            value="The user speaks about language and preferences",
            source=MemorySource.CONVERSATION,
            confidence=0.8,
            importance=0.5,
        )

        score1 = retrieval.calculate_score("preferred_language", item1)
        score2 = retrieval.calculate_score("preferred_language", item2)
        assert score1 > score2

    def test_tag_match_boosts_score(self) -> None:
        retrieval = MemoryRetrieval()

        item_with_tag = MemoryItem(
            category=MemoryCategory.PROJECT,
            key="food_app",
            value="Mobile application",
            source=MemorySource.USER_EXPLICIT,
            tags=["firebase", "react"],
        )
        item_no_tag = MemoryItem(
            category=MemoryCategory.PROJECT,
            key="food_app_2",
            value="Mobile application",
            source=MemorySource.USER_EXPLICIT,
            tags=["django"],
        )

        score_tag = retrieval.calculate_score("firebase", item_with_tag)
        score_no_tag = retrieval.calculate_score("firebase", item_no_tag)
        assert score_tag > score_no_tag
        assert score_no_tag == 0.0

    def test_target_category_bonus(self) -> None:
        retrieval = MemoryRetrieval()

        item_pref = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="theme",
            value="dark mode",
            source=MemorySource.USER_EXPLICIT,
        )
        item_fact = MemoryItem(
            category=MemoryCategory.FACT,
            key="theme",
            value="dark mode",
            source=MemorySource.USER_EXPLICIT,
        )

        score_pref = retrieval.calculate_score("theme", item_pref, target_category=MemoryCategory.PREFERENCE)
        score_fact = retrieval.calculate_score("theme", item_fact, target_category=MemoryCategory.PREFERENCE)
        assert score_pref > score_fact

    def test_expired_or_disabled_item_ignored(self) -> None:
        retrieval = MemoryRetrieval()

        past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        expired_item = MemoryItem(
            category=MemoryCategory.SESSION,
            key="task",
            value="writing tests",
            source=MemorySource.CONVERSATION,
            expires_at=past_iso,
        )
        assert retrieval.calculate_score("task", expired_item) == 0.0

        disabled_item = MemoryItem(
            category=MemoryCategory.PREFERENCE,
            key="task",
            value="writing tests",
            source=MemorySource.CONVERSATION,
            enabled=False,
        )
        assert retrieval.calculate_score("task", disabled_item) == 0.0

    def test_rank_ordering_and_limit(self) -> None:
        retrieval = MemoryRetrieval()

        candidates = [
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                key="theme",
                value="dark mode",
                source=MemorySource.USER_EXPLICIT,
                importance=0.9,
            ),
            MemoryItem(
                category=MemoryCategory.PROJECT,
                key="database",
                value="SQLite",
                source=MemorySource.SYSTEM,
                importance=0.5,
            ),
            MemoryItem(
                category=MemoryCategory.FACT,
                key="random",
                value="unrelated fact",
                source=MemorySource.CONVERSATION,
                importance=0.1,
            ),
        ]

        ranked = retrieval.rank("theme", candidates, limit=1)
        assert len(ranked) == 1
        assert ranked[0][1].key == "theme"
