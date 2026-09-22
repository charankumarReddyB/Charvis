"""
In-memory session state management for CHARVIS Memory System (Phase 13).
Maintains ephemeral working memory that exists strictly during the current process runtime.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
from memory.models import MemoryCategory, MemoryItem, MemorySource


class SessionMemory:
    """
    Temporary, process-local memory store.
    Contains short-term context such as the active task, recent tool results,
    and conversational state. Discarded when CHARVIS exits.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = {}

    def set_context(
        self,
        key: str,
        value: Any,
        importance: float = 0.5,
        source: MemorySource = MemorySource.CONVERSATION,
    ) -> None:
        """Store or update a temporary session context item."""
        with self._lock:
            cleaned_key = str(key).strip()
            self._data[cleaned_key] = {
                "key": cleaned_key,
                "value": str(value).strip(),
                "importance": max(0.0, min(1.0, float(importance))),
                "source": source.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_context(self, key: str, default: Any = None) -> Any:
        """Retrieve a session context item by key."""
        with self._lock:
            cleaned_key = str(key).strip()
            entry = self._data.get(cleaned_key)
            return entry["value"] if entry else default

    def list_context(self) -> Dict[str, str]:
        """Return all active session context items as a key-value dictionary."""
        with self._lock:
            return {k: v["value"] for k, v in self._data.items()}

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search session context items matching query in key or value."""
        with self._lock:
            q = query.strip().lower()
            results = []
            for item in self._data.values():
                if q in item["key"].lower() or q in item["value"].lower():
                    results.append(dict(item))
            return results

    def clear(self) -> None:
        """Clear all temporary session memory."""
        with self._lock:
            self._data.clear()

    def count(self) -> int:
        """Return total active session memory items."""
        with self._lock:
            return len(self._data)

    def to_memory_items(self) -> List[MemoryItem]:
        """Convert session context to transient MemoryItems for unified retrieval ranking."""
        with self._lock:
            items: List[MemoryItem] = []
            for entry in self._data.values():
                try:
                    item = MemoryItem(
                        category=MemoryCategory.SESSION,
                        key=entry["key"],
                        value=entry["value"],
                        source=MemorySource(entry["source"]),
                        importance=entry["importance"],
                        confidence=0.8,
                    )
                    items.append(item)
                except Exception:
                    pass
            return items
