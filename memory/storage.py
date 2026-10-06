"""
SQLite persistent storage implementation for CHARVIS Memory System (Phase 13).
Uses parameterized SQL queries, local file sandboxing, and thread-safe operations.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Union

from config import get_settings
from logger import get_logger
from memory.base import BaseMemoryStorage
from memory.models import (
    MemoryCategory,
    MemoryItem,
    MemorySource,
    MemoryStorageError,
)

logger = get_logger("CHARVIS.MemoryStorage")


class SQLiteMemoryStorage(BaseMemoryStorage):
    """
    Persistent SQLite storage implementation for CHARVIS long-term memory.
    All SQL operations are strictly parameterized to eliminate SQL injection risks.
    """

    def __init__(self, db_path: Optional[Union[Path, str]] = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            self.db_path = get_settings().memory_db_path

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Return or create active SQLite connection with row factory."""
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,
                    timeout=10.0,
                )
                self._conn.row_factory = sqlite3.Row
                # Optimize SQLite concurrency
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
            except Exception as e:
                logger.error("Failed to connect to SQLite memory database: %s", e)
                raise MemoryStorageError(f"Database connection error: {e}") from e
        return self._conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS memories (
                            id TEXT PRIMARY KEY,
                            category TEXT NOT NULL,
                            key TEXT NOT NULL,
                            value TEXT NOT NULL,
                            source TEXT NOT NULL,
                            confidence REAL NOT NULL DEFAULT 1.0,
                            importance REAL NOT NULL DEFAULT 0.5,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            expires_at TEXT,
                            tags TEXT NOT NULL DEFAULT '[]',
                            sensitive INTEGER NOT NULL DEFAULT 0,
                            enabled INTEGER NOT NULL DEFAULT 1
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_memories_category_key
                        ON memories (category, key);
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_memories_enabled_expires
                        ON memories (enabled, expires_at);
                        """
                    )
                logger.debug("SQLite memory storage initialized at %s", self.db_path)
            except Exception as e:
                logger.error("Failed to initialize SQLite memory tables: %s", e)
                raise MemoryStorageError(f"Schema initialization failed: {e}") from e

    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        """Deserialize a database row into a MemoryItem instance."""
        tags_raw = row["tags"]
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = []

        return MemoryItem(
            id=row["id"],
            category=MemoryCategory(row["category"]),
            key=row["key"],
            value=row["value"],
            source=MemorySource(row["source"]),
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            tags=tags,
            sensitive=bool(row["sensitive"]),
            enabled=bool(row["enabled"]),
        )

    def create(self, item: MemoryItem) -> MemoryItem:
        """Store a new memory item."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO memories (
                            id, category, key, value, source,
                            confidence, importance, created_at, updated_at,
                            expires_at, tags, sensitive, enabled
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            item.id,
                            item.category.value,
                            item.key,
                            item.value,
                            item.source.value,
                            item.confidence,
                            item.importance,
                            item.created_at,
                            item.updated_at,
                            item.expires_at,
                            json.dumps(item.tags),
                            1 if item.sensitive else 0,
                            1 if item.enabled else 0,
                        ),
                    )
                logger.debug("Created memory record id=%s, key=%s", item.id, item.key)
                return item
            except sqlite3.IntegrityError as e:
                raise MemoryStorageError(f"Memory item ID '{item.id}' already exists.") from e
            except Exception as e:
                logger.error("Error creating memory item: %s", e)
                raise MemoryStorageError(f"Failed to create memory: {e}") from e

    def save(
        self,
        key: str,
        value: str,
        category: Union[str, MemoryCategory] = MemoryCategory.FACT,
        confidence: float = 1.0,
        source: Union[str, MemorySource] = MemorySource.USER_EXPLICIT,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryItem:
        """Convenience method to save or update a memory item by key."""
        if isinstance(category, str):
            c_upper = category.upper()
            if c_upper in ("FACT", "FACTS"):
                category = MemoryCategory.FACT
            elif c_upper in ("PREFERENCE", "USER_PREFERENCE"):
                category = MemoryCategory.PREFERENCE
            elif c_upper in ("PROJECT", "PROJECTS"):
                category = MemoryCategory.PROJECT
            elif c_upper in ("WORKFLOW", "WORKFLOWS"):
                category = MemoryCategory.WORKFLOW
            elif c_upper in ("CONTEXT", "CONTEXTS"):
                category = MemoryCategory.CONTEXT
            else:
                try:
                    category = MemoryCategory(category)
                except ValueError:
                    category = MemoryCategory.FACT
        if isinstance(source, str):
            try:
                source = MemorySource(source)
            except ValueError:
                source = MemorySource.USER_EXPLICIT

        existing = self.get_by_key(key, category=category)
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.importance = importance
            if tags:
                existing.tags = list(set(existing.tags + tags))
            return self.update(existing)
        else:
            item = MemoryItem(
                key=key,
                value=value,
                category=category,
                source=source,
                confidence=confidence,
                importance=importance,
                tags=tags or [],
            )
            return self.create(item)

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by ID, or fallback to key lookup if not found."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT * FROM memories WHERE id = ?;",
                    (item_id,),
                )
                row = cur.fetchone()
                if row:
                    return self._row_to_item(row)
                return self.get_by_key(item_id)
            except Exception as e:
                logger.error("Error getting memory by ID %s: %s", item_id, e)
                raise MemoryStorageError(f"Failed to get memory: {e}") from e

    def get_by_key(
        self, key: str, category: Optional[MemoryCategory] = None
    ) -> Optional[MemoryItem]:
        """Retrieve a memory item by key, optionally filtered by category."""
        with self._lock:
            conn = self._get_connection()
            try:
                if category is not None:
                    cur = conn.execute(
                        """
                        SELECT * FROM memories
                        WHERE key = ? AND category = ? AND enabled = 1
                        ORDER BY updated_at DESC LIMIT 1;
                        """,
                        (key, category.value),
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT * FROM memories
                        WHERE key = ? AND enabled = 1
                        ORDER BY updated_at DESC LIMIT 1;
                        """,
                        (key,),
                    )
                row = cur.fetchone()
                return self._row_to_item(row) if row else None
            except Exception as e:
                logger.error("Error getting memory by key %s: %s", key, e)
                raise MemoryStorageError(f"Failed to get memory by key: {e}") from e

    def update(self, item: MemoryItem) -> MemoryItem:
        """Update an existing memory item."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute(
                        """
                        UPDATE memories SET
                            category = ?,
                            key = ?,
                            value = ?,
                            source = ?,
                            confidence = ?,
                            importance = ?,
                            updated_at = ?,
                            expires_at = ?,
                            tags = ?,
                            sensitive = ?,
                            enabled = ?
                        WHERE id = ?;
                        """,
                        (
                            item.category.value,
                            item.key,
                            item.value,
                            item.source.value,
                            item.confidence,
                            item.importance,
                            item.updated_at,
                            item.expires_at,
                            json.dumps(item.tags),
                            1 if item.sensitive else 0,
                            1 if item.enabled else 0,
                            item.id,
                        ),
                    )
                    if cur.rowcount == 0:
                        raise MemoryStorageError(f"Memory with ID '{item.id}' not found for update.")
                logger.debug("Updated memory record id=%s, key=%s", item.id, item.key)
                return item
            except MemoryStorageError:
                raise
            except Exception as e:
                logger.error("Error updating memory item %s: %s", item.id, e)
                raise MemoryStorageError(f"Failed to update memory: {e}") from e

    def delete(self, item_id: str) -> bool:
        """Delete a memory item by ID."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute(
                        "DELETE FROM memories WHERE id = ?;",
                        (item_id,),
                    )
                    deleted = cur.rowcount > 0
                if deleted:
                    logger.debug("Deleted memory record id=%s", item_id)
                return deleted
            except Exception as e:
                logger.error("Error deleting memory %s: %s", item_id, e)
                raise MemoryStorageError(f"Failed to delete memory: {e}") from e

    def delete_by_key(
        self, key: str, category: Optional[MemoryCategory] = None
    ) -> int:
        """Delete memory items matching key and optional category."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    if category is not None:
                        cur = conn.execute(
                            "DELETE FROM memories WHERE key = ? AND category = ?;",
                            (key, category.value),
                        )
                    else:
                        cur = conn.execute(
                            "DELETE FROM memories WHERE key = ?;",
                            (key,),
                        )
                    count = cur.rowcount
                logger.debug("Deleted %d memory records for key=%s", count, key)
                return count
            except Exception as e:
                logger.error("Error deleting memories for key %s: %s", key, e)
                raise MemoryStorageError(f"Failed to delete memory by key: {e}") from e

    def list(
        self,
        category: Optional[MemoryCategory] = None,
        limit: int = 50,
        include_disabled: bool = False,
    ) -> List[MemoryItem]:
        """List stored memory items with optional category filter."""
        with self._lock:
            conn = self._get_connection()
            try:
                clauses = []
                params: List[Any] = []

                if not include_disabled:
                    clauses.append("enabled = 1")
                if category is not None:
                    clauses.append("category = ?")
                    params.append(category.value)

                where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                sql = f"SELECT * FROM memories {where_sql} ORDER BY updated_at DESC LIMIT ?;"
                params.append(limit)

                cur = conn.execute(sql, tuple(params))
                rows = cur.fetchall()
                return [self._row_to_item(row) for row in rows]
            except Exception as e:
                logger.error("Error listing memories: %s", e)
                raise MemoryStorageError(f"Failed to list memories: {e}") from e

    def search(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """Search memory items matching query in key, value, or tags."""
        with self._lock:
            conn = self._get_connection()
            try:
                search_term = f"%{query.strip()}%"
                if category is not None:
                    sql = """
                        SELECT * FROM memories
                        WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?)
                          AND category = ?
                          AND enabled = 1
                        ORDER BY updated_at DESC LIMIT ?;
                    """
                    params = (search_term, search_term, search_term, category.value, limit)
                else:
                    sql = """
                        SELECT * FROM memories
                        WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?)
                          AND enabled = 1
                        ORDER BY updated_at DESC LIMIT ?;
                    """
                    params = (search_term, search_term, search_term, limit)

                cur = conn.execute(sql, params)
                rows = cur.fetchall()
                return [self._row_to_item(row) for row in rows]
            except Exception as e:
                logger.error("Error searching memories: %s", e)
                raise MemoryStorageError(f"Failed to search memories: {e}") from e

    def cleanup_expired(self) -> int:
        """Remove memory records whose expiration timestamp has elapsed."""
        with self._lock:
            conn = self._get_connection()
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                with conn:
                    cur = conn.execute(
                        """
                        DELETE FROM memories
                        WHERE expires_at IS NOT NULL AND expires_at <= ?;
                        """,
                        (now_iso,),
                    )
                    count = cur.rowcount
                if count > 0:
                    logger.info("Purged %d expired memories from database", count)
                return count
            except Exception as e:
                logger.error("Error cleaning up expired memories: %s", e)
                raise MemoryStorageError(f"Failed to clean up expired memories: {e}") from e

    def close(self) -> None:
        """Close SQLite database connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
                logger.debug("Closed SQLite memory storage connection")
