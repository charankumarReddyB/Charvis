"""
Deterministic local relevance scoring and retrieval for CHARVIS Memory System (Phase 13).
Zero external ML/vector DB dependencies; uses keyword, key, tag, confidence, and recency scoring.
"""

from datetime import datetime, timezone
import re
from typing import List, Optional, Tuple

from config import get_settings
from memory.models import (
    SOURCE_PRIORITY_WEIGHTS,
    MemoryCategory,
    MemoryItem,
)


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words, splitting on spaces and underscores."""
    return re.findall(r"[A-Za-z0-9]+", text.lower())


class MemoryRetrieval:
    """
    Deterministic relevance scoring engine for memory items.
    Ranks candidate memories based on exact keys, word overlap, categories, tags,
    source trustworthiness, importance, and recency.
    """

    def __init__(self, min_confidence: Optional[float] = None) -> None:
        settings = get_settings()
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else settings.min_retrieval_confidence
        )

    def calculate_score(
        self,
        query: str,
        item: MemoryItem,
        target_category: Optional[MemoryCategory] = None,
    ) -> float:
        """
        Compute deterministic relevance score for a MemoryItem against a search query.
        Returns a float score (higher = more relevant).
        """
        if not item.enabled or item.is_expired:
            return 0.0

        if item.confidence < self.min_confidence:
            return 0.0

        cleaned_query = query.strip().lower()
        query_tokens = set(_tokenize(cleaned_query))
        if not query_tokens:
            return 0.0

        score = 0.0
        item_key_lower = item.key.lower()
        key_tokens = set(_tokenize(item_key_lower))
        value_tokens = set(_tokenize(item.value.lower()))
        tag_tokens = {t.lower() for t in item.tags}

        # 1. Exact Key Match
        if cleaned_query == item_key_lower:
            score += 1.0
        elif cleaned_query in item_key_lower:
            score += 0.7
        else:
            # Token overlap in key
            key_overlap = query_tokens.intersection(key_tokens)
            if key_overlap:
                score += 0.5 * (len(key_overlap) / max(len(query_tokens), 1))

        # 2. Token overlap in value
        value_overlap = query_tokens.intersection(value_tokens)
        if value_overlap:
            score += 0.35 * (len(value_overlap) / max(len(query_tokens), 1))

        # 3. Tag match
        tag_overlap = query_tokens.intersection(tag_tokens)
        if tag_overlap:
            score += 0.25 * min(len(tag_overlap), 3)

        # 4. Target Category bonus
        if target_category is not None and item.category == target_category:
            score += 0.2

        # If there is zero text relevance, score is zero
        if score <= 0.0:
            return 0.0

        # 5. Source Priority Multiplier
        source_weight = SOURCE_PRIORITY_WEIGHTS.get(item.source, 0.5)
        score *= (0.6 + 0.4 * source_weight)

        # 6. Importance and Confidence Multipliers
        score *= (0.5 + 0.5 * item.confidence)
        score *= (0.7 + 0.3 * item.importance)

        # 7. Recency Bonus (small boost for recently updated items up to 30 days)
        try:
            updated = datetime.fromisoformat(item.updated_at)
            now = datetime.now(timezone.utc)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            days_old = max(0.0, (now - updated).total_seconds() / 86400.0)
            if days_old < 30.0:
                recency_boost = 0.15 * (1.0 - (days_old / 30.0))
                score += recency_boost
        except Exception:
            pass

        return round(score, 4)

    def rank(
        self,
        query: str,
        candidates: List[MemoryItem],
        target_category: Optional[MemoryCategory] = None,
        limit: int = 10,
    ) -> List[Tuple[float, MemoryItem]]:
        """
        Rank a collection of candidate memory items against the query.
        Returns top scored (score, item) pairs, descending.
        """
        scored_items: List[Tuple[float, MemoryItem]] = []

        for item in candidates:
            score = self.calculate_score(query, item, target_category)
            if score > 0.0:
                scored_items.append((score, item))

        # Sort descending by score; if tied, newer updated_at first
        scored_items.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)
        return scored_items[:limit]
