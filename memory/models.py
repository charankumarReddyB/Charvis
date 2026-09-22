"""
Data models, enums, and exception types for the CHARVIS Memory System (Phase 13).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class MemoryCategory(str, Enum):
    """Explicit, controlled categories for stored memories."""
    SESSION = "SESSION"
    PREFERENCE = "PREFERENCE"
    FACT = "FACT"
    PROJECT = "PROJECT"
    WORKFLOW = "WORKFLOW"
    CONTEXT = "CONTEXT"


class MemorySource(str, Enum):
    """Origin of a memory item, indicating trust and certainty level."""
    USER_EXPLICIT = "USER_EXPLICIT"
    CONVERSATION = "CONVERSATION"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


# Source priority weights (higher weight = more trusted)
SOURCE_PRIORITY_WEIGHTS: Dict[MemorySource, float] = {
    MemorySource.USER_EXPLICIT: 1.0,
    MemorySource.SYSTEM: 0.85,
    MemorySource.TOOL: 0.70,
    MemorySource.CONVERSATION: 0.50,
}


# Custom Exception Hierarchy
class MemoryError(Exception):
    """Base exception for all memory operations."""
    pass


class MemoryValidationError(MemoryError):
    """Raised when memory keys, values, or attributes fail schema validation."""
    pass


class MemorySecurityError(MemoryError):
    """Raised when an operation violates memory privacy or security guardrails."""
    pass


class MemoryStorageError(MemoryError):
    """Raised when database reads, writes, or connections fail."""
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when a specified memory item cannot be located."""
    pass


class MemoryConflictError(MemoryError):
    """Raised when a memory update or creation causes an unresolved ambiguity."""
    pass


@dataclass
class MemoryItem:
    """
    Structured, validated memory entity in CHARVIS.
    Can represent either short-term session state or persistent long-term storage.
    """
    category: MemoryCategory
    key: str
    value: str
    source: MemorySource
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 0.9
    importance: float = 0.5
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    sensitive: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate fields and enforce invariant bounds."""
        # Validate Category
        if isinstance(self.category, str):
            try:
                self.category = MemoryCategory(self.category.upper())
            except ValueError:
                valid = ", ".join(c.value for c in MemoryCategory)
                raise MemoryValidationError(
                    f"Invalid memory category '{self.category}'. Must be one of: {valid}"
                )

        # Validate Source
        if isinstance(self.source, str):
            try:
                self.source = MemorySource(self.source.upper())
            except ValueError:
                valid = ", ".join(s.value for s in MemorySource)
                raise MemoryValidationError(
                    f"Invalid memory source '{self.source}'. Must be one of: {valid}"
                )

        # Validate Key
        if not isinstance(self.key, str) or not self.key.strip():
            raise MemoryValidationError("Memory key must be a non-empty string.")
        self.key = self.key.strip()
        if len(self.key) > 200:
            raise MemoryValidationError(
                f"Memory key exceeds maximum allowed length of 200 characters (got {len(self.key)})."
            )

        # Validate Value
        if not isinstance(self.value, str) or not self.value.strip():
            raise MemoryValidationError("Memory value must be a non-empty string.")
        self.value = self.value.strip()
        if len(self.value) > 10000:
            raise MemoryValidationError(
                f"Memory value exceeds maximum allowed length of 10000 characters (got {len(self.value)})."
            )

        # Validate Confidence & Importance bounds
        if not (0.0 <= self.confidence <= 1.0):
            raise MemoryValidationError(
                f"Memory confidence must be between 0.0 and 1.0, got {self.confidence}."
            )
        if not (0.0 <= self.importance <= 1.0):
            raise MemoryValidationError(
                f"Memory importance must be between 0.0 and 1.0, got {self.importance}."
            )

        # Validate Tags
        if not isinstance(self.tags, (list, tuple)):
            raise MemoryValidationError("Memory tags must be a list of strings.")
        cleaned_tags = []
        for t in self.tags:
            if isinstance(t, str) and t.strip():
                tag_str = t.strip()
                if len(tag_str) > 50:
                    tag_str = tag_str[:50]
                if tag_str not in cleaned_tags:
                    cleaned_tags.append(tag_str)
        self.tags = cleaned_tags[:20]

        # Validate expiration timestamp format if supplied
        if self.expires_at is not None:
            try:
                datetime.fromisoformat(self.expires_at)
            except (ValueError, TypeError):
                raise MemoryValidationError(
                    f"Invalid ISO 8601 timestamp for expires_at: '{self.expires_at}'"
                )

    @property
    def is_expired(self) -> bool:
        """Check if memory has passed its expiration timestamp."""
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            # Ensure timezone awareness for comparison
            now = datetime.now(timezone.utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return now >= exp
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory item to dictionary."""
        return {
            "id": self.id,
            "category": self.category.value,
            "key": self.key,
            "value": self.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "tags": list(self.tags),
            "sensitive": self.sensitive,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Construct MemoryItem from dictionary."""
        return cls(
            id=data["id"],
            category=MemoryCategory(data["category"]),
            key=data["key"],
            value=data["value"],
            source=MemorySource(data["source"]),
            confidence=float(data.get("confidence", 0.9)),
            importance=float(data.get("importance", 0.5)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            expires_at=data.get("expires_at"),
            tags=list(data.get("tags", [])),
            sensitive=bool(data.get("sensitive", False)),
            enabled=bool(data.get("enabled", True)),
        )
