"""
Tests for Memory Tools and ToolRouter integration (Phase 13).
"""

from pathlib import Path
from typing import Any, Dict
import pytest

from core.safety import RiskLevel, SafetyManager
from memory.manager import MemoryManager
from memory.storage import SQLiteMemoryStorage
from tools.memory import (
    ClearSessionMemoryTool,
    ForgetMemoryTool,
    ListMemoriesTool,
    RecallTool,
    RememberTool,
    UpdateMemoryTool,
    set_memory_manager,
)
from tools.registry import ToolRegistry
from tools.router import ToolRouter


@pytest.fixture
def test_mgr(tmp_path: Path) -> MemoryManager:
    storage = SQLiteMemoryStorage(tmp_path / "test_tools.db")
    mgr = MemoryManager(storage=storage)
    set_memory_manager(mgr)
    yield mgr
    storage.close()
    set_memory_manager(None)


class TestMemoryTools:
    """Test memory tools execution and schemas."""

    def test_remember_tool_execution(self, test_mgr: MemoryManager) -> None:
        tool = RememberTool(manager=test_mgr)
        result = tool.execute(
            key="preferred_language",
            value="Java",
            category="PREFERENCE",
            is_explicit=True,
        )
        assert result["status"] == "success"
        assert "preferred_language" in result["message"]

        # Re-query
        recalled = test_mgr.get_memory("preferred_language")
        assert recalled is not None
        assert recalled.value == "Java"

    def test_remember_tool_sensitive_rejection(self, test_mgr: MemoryManager) -> None:
        tool = RememberTool(manager=test_mgr)
        result = tool.execute(
            key="api_token",
            value="bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzN_ce",
        )
        assert result["status"] == "error"
        assert result["error_type"] == "SecurityError"

    def test_recall_tool_execution(self, test_mgr: MemoryManager) -> None:
        test_mgr.remember(key="project_name", value="CHARVIS", category="PROJECT")

        tool = RecallTool(manager=test_mgr)
        result = tool.execute(query="CHARVIS")
        assert result["status"] == "success"
        assert result["count"] >= 1
        assert result["memories"][0]["key"] == "project_name"

    def test_list_memories_tool_execution(self, test_mgr: MemoryManager) -> None:
        test_mgr.remember(key="k1", value="v1")
        test_mgr.remember(key="k2", value="v2")

        tool = ListMemoriesTool(manager=test_mgr)
        result = tool.execute(limit=10)
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_update_memory_tool_execution(self, test_mgr: MemoryManager) -> None:
        test_mgr.remember(key="theme", value="light")

        tool = UpdateMemoryTool(manager=test_mgr)
        result = tool.execute(key="theme", value="dark")
        assert result["status"] == "success"
        assert test_mgr.get_memory("theme").value == "dark"

    def test_forget_memory_tool_execution(self, test_mgr: MemoryManager) -> None:
        test_mgr.remember(key="delete_me", value="temp")

        tool = ForgetMemoryTool(manager=test_mgr)
        result = tool.execute(key="delete_me")
        assert result["status"] == "success"
        assert result["deleted_count"] == 1
        assert test_mgr.get_memory("delete_me") is None

    def test_clear_session_memory_tool_execution(self, test_mgr: MemoryManager) -> None:
        test_mgr.session.set_context("active_topic", "pytest")
        assert test_mgr.session.count() == 1

        tool = ClearSessionMemoryTool(manager=test_mgr)
        result = tool.execute()
        assert result["status"] == "success"
        assert test_mgr.session.count() == 0

    def test_tool_risk_levels_and_router_integration(self, test_mgr: MemoryManager) -> None:
        remember_tool = RememberTool(manager=test_mgr)
        recall_tool = RecallTool(manager=test_mgr)
        list_tool = ListMemoriesTool(manager=test_mgr)
        clear_session_tool = ClearSessionMemoryTool(manager=test_mgr)
        forget_tool = ForgetMemoryTool(manager=test_mgr)

        assert recall_tool.risk_level == RiskLevel.SAFE
        assert list_tool.risk_level == RiskLevel.SAFE
        assert clear_session_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
        assert remember_tool.get_risk_level({"is_explicit": True}) == RiskLevel.SAFE
        assert remember_tool.get_risk_level({"is_explicit": False}) == RiskLevel.CONFIRMATION_REQUIRED
        assert forget_tool.get_risk_level({"clear_all": True}) == RiskLevel.CONFIRMATION_REQUIRED

        registry = ToolRegistry()
        registry.register(recall_tool)
        registry.register(clear_session_tool)

        safety = SafetyManager()
        router = ToolRouter(registry, safety)

        # Recall should execute immediately without confirmation
        res = router.execute_tool("recall", {"query": "anything"})
        assert res.success is True

        # Clear session requires confirmation - rejected when callback returns False
        res_blocked = router.execute_tool(
            "clear_session_memory",
            {},
            confirmation_callback=lambda name, args, risk: False,
        )
        assert res_blocked.success is False
        assert "denied" in res_blocked.error.lower() or "rejected" in res_blocked.error.lower()
