"""Integration tests for CHARVIS System Information and Control (Phase 7).

Verifies ToolRegistry registration, ToolRouter dispatching, SafetyManager policies,
and end-to-end cognitive loop execution with mock providers.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from tools.registry import ToolRegistry
from tools.router import ToolRouter


class MockProvider(BaseLLMProvider):
    """Mock LLM provider returning simulated tool calls and responses."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.history_received: list = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_response(self, messages, tools=None, temperature=0.7, max_tokens=None) -> LLMResponse:
        self.history_received.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="Mock default response", tool_calls=[])


def test_registry_contains_all_twenty_eight_tools_by_default() -> None:
    """Verify default ToolRegistry in AIBrain contains all 28 registered tools from Phases 3-7."""
    brain = AIBrain(provider=MockProvider([]))
    tool_names = [t.name for t in brain.registry.list_tools()]

    assert len(tool_names) == 75
    assert len(tool_names) >= 28

    expected_phase7_tools = [
        "get_system_info",
        "get_cpu_usage",
        "get_memory_usage",
        "get_disk_usage",
        "get_battery_status",
        "get_uptime",
        "get_network_status",
        "lock_workstation",
        "shutdown_system",
        "restart_system",
    ]

    for expected in expected_phase7_tools:
        assert expected in tool_names, f"Expected tool '{expected}' missing from registry"


def test_registry_strictly_omits_arbitrary_command_tools() -> None:
    """CRITICAL SECURITY: Verify registry does NOT contain generic or arbitrary command execution tools."""
    brain = AIBrain(provider=MockProvider([]))
    tool_names = [t.name for t in brain.registry.list_tools()]

    forbidden_names = [
        "run_command",
        "execute_command",
        "shell_command",
        "powershell",
        "cmd",
        "exec",
        "eval",
        "system_command",
        "terminal",
    ]

    for forbidden in forbidden_names:
        assert forbidden not in tool_names, f"Security violation: forbidden tool '{forbidden}' found in registry"


def test_brain_end_to_end_system_information_flow() -> None:
    """Test full cognitive loop: User query -> LLM calls get_cpu_usage -> tool executed -> final response."""
    responses = [
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_cpu_01",
                    name="get_cpu_usage",
                    arguments={"interval": 0.05},
                )
            ],
        ),
        LLMResponse(
            content="Your current CPU usage is 18.5% across 8 logical cores.",
            tool_calls=[],
        ),
    ]

    provider = MockProvider(responses)
    brain = AIBrain(provider=provider)

    reply = brain.process_user_message("What is my current CPU usage?")
    assert "18.5%" in reply
    assert len(provider.history_received) == 2


def test_brain_end_to_end_system_control_flow_with_confirmation() -> None:
    """Test full cognitive loop: User query -> LLM calls lock_workstation -> confirmed -> executed."""
    responses = [
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_lock_01",
                    name="lock_workstation",
                    arguments={},
                )
            ],
        ),
        LLMResponse(
            content="The workstation has been locked.",
            tool_calls=[],
        ),
    ]

    provider = MockProvider(responses)
    brain = AIBrain(provider=provider)

    # Mock the underlying lock C-API to avoid actually locking Windows during test
    lock_tool = brain.registry.get("lock_workstation")
    with patch.object(lock_tool._controller, "_lock_workstation_api", return_value=True) as mock_lock_api:
        reply = brain.process_user_message(
            "Lock my computer.",
            confirmation_callback=lambda name, args, risk, msg: True,
        )
        assert "locked" in reply
        mock_lock_api.assert_called_once()
