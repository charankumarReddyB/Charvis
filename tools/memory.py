"""
CHARVIS Memory Tools (Phase 13).
Provides controlled tools for storing, retrieving, updating, and forgetting memories:
- remember: Explicitly store a structured memory item (safeguarded against sensitive data).
- recall: Search relevant memories deterministically by query or category.
- list_memories: List stored memories with category filtering.
- update_memory: Modify an existing memory item.
- forget_memory: Delete memory items by ID, key, or category.
- clear_session_memory: Clear ephemeral session memory.
"""

from typing import Any, Dict, List, Optional
from core.safety import RiskLevel
from logger import get_logger
from memory.manager import MemoryManager
from memory.models import (
    MemoryCategory,
    MemoryConflictError,
    MemoryError,
    MemoryNotFoundError,
    MemorySecurityError,
    MemorySource,
    MemoryValidationError,
)
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema

logger = get_logger("CHARVIS.Tools.Memory")

# Singleton MemoryManager instance for tools
_ACTIVE_MEMORY_MANAGER: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create singleton MemoryManager."""
    global _ACTIVE_MEMORY_MANAGER
    if _ACTIVE_MEMORY_MANAGER is None:
        _ACTIVE_MEMORY_MANAGER = MemoryManager()
    return _ACTIVE_MEMORY_MANAGER


def set_memory_manager(manager: Optional[MemoryManager]) -> None:
    """Set or override singleton MemoryManager (useful for testing)."""
    global _ACTIVE_MEMORY_MANAGER
    _ACTIVE_MEMORY_MANAGER = manager


class RememberTool(BaseTool):
    """Explicitly store a memory item with validation and sensitivity filtering."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "remember"

    @property
    def description(self) -> str:
        return (
            "Store a useful fact, user preference, project detail, or workflow in long-term memory. "
            "Sensitive information (passwords, API keys, tokens, CVVs, card numbers) will be strictly rejected."
        )

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="key",
                    param_type="string",
                    description="Short identifier or topic of the memory (e.g., 'preferred_language', 'project_stack')",
                    required=True,
                ),
                ToolParameter(
                    name="value",
                    param_type="string",
                    description="Detailed memory content to remember (e.g., 'user prefers Python for rapid prototyping')",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Memory category: PREFERENCE, FACT, PROJECT, WORKFLOW, CONTEXT, SESSION (default: PREFERENCE)",
                    required=False,
                ),
                ToolParameter(
                    name="importance",
                    param_type="number",
                    description="Importance weighting from 0.0 (low) to 1.0 (critical, default: 0.5)",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    param_type="array",
                    description="Optional list of search tags (e.g., ['python', 'coding'])",
                    required=False,
                ),
                ToolParameter(
                    name="is_explicit",
                    param_type="boolean",
                    description="Set to true if this was an explicit user instruction (default: true)",
                    required=False,
                ),
            ]
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        # If not explicitly requested by user (e.g. model inference), require confirmation
        is_explicit = arguments.get("is_explicit", True)
        return RiskLevel.SAFE if is_explicit else RiskLevel.CONFIRMATION_REQUIRED

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        category = kwargs.get("category", "PREFERENCE")
        importance = kwargs.get("importance", 0.5)
        tags = kwargs.get("tags")
        is_explicit = kwargs.get("is_explicit", True)

        source = MemorySource.USER_EXPLICIT if is_explicit else MemorySource.CONVERSATION
        confidence = 1.0 if is_explicit else 0.8

        try:
            item = self.manager.remember(
                key=key,
                value=value,
                category=category,
                source=source,
                confidence=confidence,
                importance=importance,
                tags=tags,
            )
            return {
                "status": "success",
                "message": f"Successfully remembered '{item.key}'.",
                "memory": item.to_dict(),
            }
        except MemorySecurityError as e:
            return {
                "status": "error",
                "error_type": "SecurityError",
                "message": f"Cannot remember item: {e}",
            }
        except MemoryConflictError as e:
            return {
                "status": "conflict",
                "error_type": "ConflictError",
                "message": str(e),
            }
        except MemoryValidationError as e:
            return {
                "status": "error",
                "error_type": "ValidationError",
                "message": str(e),
            }
        except Exception as e:
            logger.error("Failed to execute remember tool: %s", e)
            return {
                "status": "error",
                "error_type": "StorageError",
                "message": f"Failed to store memory: {e}",
            }


class RecallTool(BaseTool):
    """Retrieve relevant memories matching a query or category."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "recall"

    @property
    def description(self) -> str:
        return "Search stored memories for relevant information matching a query or category."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="Search query or keyword to find relevant memories",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Optional memory category filter (PREFERENCE, FACT, PROJECT, WORKFLOW, CONTEXT, SESSION)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    param_type="integer",
                    description="Maximum number of memories to return (default: 5)",
                    required=False,
                ),
            ]
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        category = kwargs.get("category")
        limit = kwargs.get("limit", 5)

        try:
            memories = self.manager.recall(
                query=query,
                category=category,
                limit=limit,
            )
            return {
                "status": "success",
                "count": len(memories),
                "memories": [m.to_dict() for m in memories],
            }
        except Exception as e:
            logger.error("Failed to execute recall tool: %s", e)
            return {
                "status": "error",
                "message": f"Failed to recall memories: {e}",
            }


class ListMemoriesTool(BaseTool):
    """List stored memory records with optional category filter."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "list_memories"

    @property
    def description(self) -> str:
        return "List stored memories, optionally filtered by category."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Optional category to filter by (PREFERENCE, FACT, PROJECT, WORKFLOW, CONTEXT, SESSION)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    param_type="integer",
                    description="Maximum number of memories to list (default: 20)",
                    required=False,
                ),
            ]
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        category = kwargs.get("category")
        limit = kwargs.get("limit", 20)

        try:
            memories = self.manager.list_memories(
                category=category,
                limit=limit,
            )
            return {
                "status": "success",
                "count": len(memories),
                "memories": [m.to_dict() for m in memories],
            }
        except Exception as e:
            logger.error("Failed to execute list_memories tool: %s", e)
            return {
                "status": "error",
                "message": f"Failed to list memories: {e}",
            }


class UpdateMemoryTool(BaseTool):
    """Update an existing memory item."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "update_memory"

    @property
    def description(self) -> str:
        return "Update an existing memory value, importance, or tags."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="key",
                    param_type="string",
                    description="Key of the memory to update",
                    required=True,
                ),
                ToolParameter(
                    name="value",
                    param_type="string",
                    description="New value content to update",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Category of the memory (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="importance",
                    param_type="number",
                    description="Updated importance (0.0 to 1.0)",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    param_type="array",
                    description="Updated tags list",
                    required=False,
                ),
                ToolParameter(
                    name="is_explicit",
                    param_type="boolean",
                    description="True if directly commanded by user (default: false)",
                    required=False,
                ),
            ]
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        is_explicit = arguments.get("is_explicit", False)
        return RiskLevel.SAFE if is_explicit else RiskLevel.CONFIRMATION_REQUIRED

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        category = kwargs.get("category")
        importance = kwargs.get("importance")
        tags = kwargs.get("tags")

        try:
            updated = self.manager.update_memory(
                key=key,
                value=value,
                category=category,
                importance=importance,
                tags=tags,
            )
            return {
                "status": "success",
                "message": f"Successfully updated memory '{key}'.",
                "memory": updated.to_dict(),
            }
        except MemorySecurityError as e:
            return {
                "status": "error",
                "error_type": "SecurityError",
                "message": str(e),
            }
        except MemoryNotFoundError as e:
            return {
                "status": "not_found",
                "message": str(e),
            }
        except Exception as e:
            logger.error("Failed to execute update_memory tool: %s", e)
            return {
                "status": "error",
                "message": f"Failed to update memory: {e}",
            }


class ForgetMemoryTool(BaseTool):
    """Delete a memory item by key, ID, or category."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "forget_memory"

    @property
    def description(self) -> str:
        return "Delete a specific memory by key or ID, or clear memories in a category."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="key",
                    param_type="string",
                    description="Key of memory to delete",
                    required=False,
                ),
                ToolParameter(
                    name="memory_id",
                    param_type="string",
                    description="Unique ID of memory to delete",
                    required=False,
                ),
                ToolParameter(
                    name="category",
                    param_type="string",
                    description="Category of memory (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="clear_all",
                    param_type="boolean",
                    description="If true, deletes all memories in the specified category (requires confirmation)",
                    required=False,
                ),
                ToolParameter(
                    name="is_explicit",
                    param_type="boolean",
                    description="True if directly commanded by user (default: false)",
                    required=False,
                ),
            ]
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    def get_risk_level(self, arguments: Dict[str, Any]) -> RiskLevel:
        # Broad deletion requires human confirmation
        if arguments.get("clear_all", False):
            return RiskLevel.CONFIRMATION_REQUIRED
        is_explicit = arguments.get("is_explicit", False)
        return RiskLevel.SAFE if is_explicit else RiskLevel.CONFIRMATION_REQUIRED

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        key = kwargs.get("key")
        memory_id = kwargs.get("memory_id")
        category = kwargs.get("category")
        clear_all = kwargs.get("clear_all", False)

        try:
            deleted_count = self.manager.forget_memory(
                key=key,
                memory_id=memory_id,
                category=category,
                clear_all=clear_all,
            )
            if deleted_count > 0:
                return {
                    "status": "success",
                    "deleted_count": deleted_count,
                    "message": f"Successfully deleted {deleted_count} memory item(s).",
                }
            return {
                "status": "not_found",
                "deleted_count": 0,
                "message": "No matching memory items found to delete.",
            }
        except MemoryValidationError as e:
            return {
                "status": "error",
                "error_type": "ValidationError",
                "message": str(e),
            }
        except Exception as e:
            logger.error("Failed to execute forget_memory tool: %s", e)
            return {
                "status": "error",
                "message": f"Failed to delete memory: {e}",
            }


class ClearSessionMemoryTool(BaseTool):
    """Clear ephemeral session memory (does not delete long-term memories)."""

    def __init__(self, manager: Optional[MemoryManager] = None) -> None:
        self._manager = manager

    @property
    def manager(self) -> MemoryManager:
        return self._manager or get_memory_manager()

    @property
    def name(self) -> str:
        return "clear_session_memory"

    @property
    def description(self) -> str:
        return "Clear short-term temporary session memory for the current conversation without affecting long-term persistent memory."

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[],
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        try:
            self.manager.clear_session_memory()
            return {
                "status": "success",
                "message": "Ephemeral session memory has been cleared.",
            }
        except Exception as e:
            logger.error("Failed to clear session memory: %s", e)
            return {
                "status": "error",
                "message": f"Failed to clear session memory: {e}",
            }
