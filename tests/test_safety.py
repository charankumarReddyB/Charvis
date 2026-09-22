"""
Unit tests for SafetyManager, RiskLevel classification, and confirmation workflow.
"""

import pytest
from core.safety import RiskLevel, SafetyManager
from tools.base import BaseTool
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.schemas import ToolSchema


class SafeActionTool(BaseTool):
    @property
    def name(self) -> str:
        return "safe_action"

    @property
    def description(self) -> str:
        return "A safe tool."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs):
        return "safe executed"


class SensitiveActionTool(BaseTool):
    @property
    def name(self) -> str:
        return "sensitive_action"

    @property
    def description(self) -> str:
        return "A tool that modifies settings."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs):
        return "sensitive executed"


class DangerousActionTool(BaseTool):
    @property
    def name(self) -> str:
        return "dangerous_action"

    @property
    def description(self) -> str:
        return "A high-risk tool."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH_RISK

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=[])

    def execute(self, **kwargs):
        return "dangerous executed"


def test_safety_risk_level_requirements():
    """Verify which risk levels mandate confirmation."""
    sm = SafetyManager()
    assert sm.requires_confirmation(RiskLevel.SAFE) is False
    assert sm.requires_confirmation(RiskLevel.CONFIRMATION_REQUIRED) is True
    assert sm.requires_confirmation(RiskLevel.HIGH_RISK) is True


def test_safe_tool_executes_without_confirmation():
    """Verify SAFE tools execute directly through router without prompting."""
    registry = ToolRegistry()
    registry.register(SafeActionTool())
    router = ToolRouter(registry)

    # No callback passed
    result = router.execute_tool("safe_action", {})
    assert result.success is True
    assert result.data == "safe executed"


def test_confirmation_required_tool_denied_without_callback():
    """Verify confirmation-required tool defaults to denial when no callback exists."""
    registry = ToolRegistry()
    registry.register(SensitiveActionTool())
    router = ToolRouter(registry)

    result = router.execute_tool("sensitive_action", {})
    assert result.success is False
    assert "User did not authorize" in result.error


def test_confirmation_required_tool_denied_by_user():
    """Verify user rejecting confirmation aborts execution."""
    registry = ToolRegistry()
    registry.register(SensitiveActionTool())
    router = ToolRouter(registry)

    # User answers False / No
    deny_callback = lambda tool, args, risk: False
    result = router.execute_tool("sensitive_action", {}, confirmation_callback=deny_callback)

    assert result.success is False
    assert "User did not authorize" in result.error


def test_confirmation_required_tool_approved_by_user():
    """Verify user approving confirmation allows execution."""
    registry = ToolRegistry()
    registry.register(SensitiveActionTool())
    router = ToolRouter(registry)

    # User answers True / Yes
    approve_callback = lambda tool, args, risk: True
    result = router.execute_tool("sensitive_action", {}, confirmation_callback=approve_callback)

    assert result.success is True
    assert result.data == "sensitive executed"


def test_confirmation_prompt_formatting():
    """Verify prompt formatting contains essential transparency details."""
    sm = SafetyManager()
    prompt = sm.format_confirmation_prompt(
        tool_name="delete_temp_file",
        arguments={"path": "temp.txt"},
        risk_level=RiskLevel.HIGH_RISK,
    )
    assert "delete_temp_file" in prompt
    assert "temp.txt" in prompt
    assert "HIGH_RISK" in prompt
    assert "Proceed? [y/N]" in prompt


def test_confirmation_callback_exception_fails_safely():
    """Verify exception in confirmation callback defaults to denial."""
    sm = SafetyManager()

    def buggy_callback(tool, args, risk):
        raise RuntimeError("Keyboard disconnected")

    authorized = sm.verify_action(
        tool_name="test",
        arguments={},
        risk_level=RiskLevel.HIGH_RISK,
        confirmation_callback=buggy_callback,
    )
    assert authorized is False
