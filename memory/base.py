"""
Abstract storage interface for CHARVIS Memory System (Phase 13).
Decouples cognitive brain and memory manager from underlying database implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from memory.models import MemoryCategory, MemoryItem


class BaseMemoryStorage(ABC):
    """
    Abstract persistent storage backend for memory items.
    Enforces atomic operations, structured indexing, and thread-safe querying.
    """

    @abstractmethod
    def create(self, item: MemoryItem) -> MemoryItem:
        """
        Store a new memory item.
        Raises MemoryStorageError on database failure.
        """
        pass

    @abstractmethod
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by its unique ID."""
        pass

    @abstractmethod
    def get_by_key(
        self, key: str, category: Optional[MemoryCategory] = None
    ) -> Optional[MemoryItem]:
        """Retrieve a memory item by its key, optionally filtered by category."""
        pass

    @abstractmethod
    def update(self, item: MemoryItem) -> MemoryItem:
        """
        Update an existing memory item.
        Preserves ID and updates updated_at timestamp.
        """
        pass

    @abstractmethod
    def delete(self, item_id: str) -> bool:
        """Delete a memory item by its unique ID. Returns True if deleted."""
        pass

    @abstractmethod
    def delete_by_key(
        self, key: str, category: Optional[MemoryCategory] = None
    ) -> int:
        """Delete memory items matching key and optional category. Returns count deleted."""
        pass

    @abstractmethod
    def list(
        self,
        category: Optional[MemoryCategory] = None,
        limit: int = 50,
        include_disabled: bool = False,
    ) -> List[MemoryItem]:
        """List stored memory items with optional category filtering."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """Search memory items matching query in key, value, or tags."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove or disable records whose expiration timestamp has passed. Returns count."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close storage connections and release resources."""
        pass
