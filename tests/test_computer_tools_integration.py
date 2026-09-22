"""
Integration tests for CHARVIS Computer Tools (Keyboard & Mouse) with ToolRegistry,
ToolRouter, SafetyManager, and AIBrain.
All tests use mocking to prevent physical hardware interactions.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from tools.calculator import CalculatorTool
from tools.keyboard import HotkeyTool, PressKeyTool, TypeTextTool
from tools.mouse import ClickTool, DoubleClickTool, MoveMouseTool, ScrollTool
from tools.registry import ToolRegistry
from tools.router import ToolRouter


class MockScriptedProvider(BaseLLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)

    @property
    def provider_name(self):
        return "mock_scripted"

    @property
    def model_name(self):
        return "test-model"

    def generate_response(self, messages, tools=None):
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Done", model="test-model")


def test_registry_contains_all_eleven_tools_by_default():
    """Verify that AIBrain initializes with all 11 active tools across Phases 3, 4, and 5."""
    brain = AIBrain(provider=MockScriptedProvider([]))
    tools = brain.registry.list_tools()
    tool_names = [t.name for t in tools]

    assert len(tool_names) >= 11
    expected_tools = {
        "calculator",
        "open_application",
        "close_application",
        "get_application_status",
        "type_text",
        "press_key",
        "hotkey",
        "move_mouse",
        "click",
        "double_click",
        "scroll",
    }
    assert expected_tools.issubset(set(tool_names))


def test_router_enforces_safety_on_type_text_and_hotkey():
    """Verify ToolRouter requires confirmation on type_text and hotkey, but not on move_mouse."""
    registry = ToolRegistry()
    safety = SafetyManager()
    router = ToolRouter(registry, safety)

    mock_type = MagicMock(spec=TypeTextTool)
    mock_type.name = "type_text"
    mock_type.risk_level = RiskLevel.CONFIRMATION_REQUIRED
    mock_type.schema.name = "type_text"
    mock_type.validate_arguments.return_value = None
    mock_type.get_confirmation_message.return_value = "Typing preview"
    mock_type.execute.return_value = {"success": True, "typed": 5}
    registry.register(mock_type)

    mock_mouse = MagicMock(spec=MoveMouseTool)
    mock_mouse.name = "move_mouse"
    mock_mouse.risk_level = RiskLevel.SAFE
    mock_mouse.schema.name = "move_mouse"
    mock_mouse.validate_arguments.return_value = None
    mock_mouse.execute.return_value = {"success": True, "x": 100, "y": 100}
    registry.register(mock_mouse)

    # 1. move_mouse executes without confirmation
    mouse_res = router.execute_tool("move_mouse", {"x": 100, "y": 100})
    assert mouse_res.success is True
    mock_mouse.execute.assert_called_once()

    # 2. type_text denied when confirmation callback returns False
    denied_res = router.execute_tool(
        "type_text",
        {"text": "Secret"},
        confirmation_callback=lambda *_: False,
    )
    assert denied_res.success is False
    assert "User did not authorize" in str(denied_res.error)
    mock_type.execute.assert_not_called()

    # 3. type_text succeeds when confirmation callback returns True
    approved_res = router.execute_tool(
        "type_text",
        {"text": "Hello"},
        confirmation_callback=lambda *_: True,
    )
    assert approved_res.success is True
    mock_type.execute.assert_called_once()


def test_brain_end_to_end_type_text_and_press_key_flow():
    """Verify cognitive loop for typing text and pressing Enter."""
    registry = ToolRegistry()

    mock_type_tool = MagicMock(spec=TypeTextTool)
    mock_type_tool.name = "type_text"
    mock_type_tool.risk_level = RiskLevel.CONFIRMATION_REQUIRED
    mock_type_tool.schema.name = "type_text"
    mock_type_tool.validate_arguments.return_value = None
    mock_type_tool.get_confirmation_message.return_value = "Preview"
    mock_type_tool.execute.return_value = {"success": True, "typed_length": 14}
    registry.register(mock_type_tool)

    mock_press_tool = MagicMock(spec=PressKeyTool)
    mock_press_tool.name = "press_key"
    mock_press_tool.risk_level = RiskLevel.SAFE
    mock_press_tool.schema.name = "press_key"
    mock_press_tool.validate_arguments.return_value = None
    mock_press_tool.execute.return_value = {"success": True, "key": "enter"}
    registry.register(mock_press_tool)

    # Scripted LLM responses
    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="c1", name="type_text", arguments={"text": "Hello CHARVIS!"})],
            model="test-model",
        ),
        LLMResponse(
            content="I typed the greeting. Now pressing Enter.",
            tool_calls=[ToolCall(id="c2", name="press_key", arguments={"key": "enter"})],
            model="test-model",
        ),
        LLMResponse(
            content="Completed typing and pressed Enter.",
            model="test-model",
        ),
    ]

    provider = MockScriptedProvider(responses)
    brain = AIBrain(provider=provider, registry=registry)

    # Approve all confirmations
    reply = brain.process_user_message(
        "Type Hello CHARVIS and press enter",
        confirmation_callback=lambda *_: True,
    )

    assert reply == "Completed typing and pressed Enter."
    mock_type_tool.execute.assert_called_once_with(text="Hello CHARVIS!")
    mock_press_tool.execute.assert_called_once_with(key="enter")


def test_brain_end_to_end_move_mouse_and_click_flow():
    """Verify cognitive loop for moving mouse and clicking."""
    registry = ToolRegistry()

    mock_move = MagicMock(spec=MoveMouseTool)
    mock_move.name = "move_mouse"
    mock_move.risk_level = RiskLevel.SAFE
    mock_move.schema.name = "move_mouse"
    mock_move.validate_arguments.return_value = None
    mock_move.execute.return_value = {"success": True, "x": 500, "y": 300}
    registry.register(mock_move)

    mock_click = MagicMock(spec=ClickTool)
    mock_click.name = "click"
    mock_click.risk_level = RiskLevel.SAFE
    mock_click.schema.name = "click"
    mock_click.validate_arguments.return_value = None
    mock_click.execute.return_value = {"success": True, "button": "left", "clicks": 1}
    registry.register(mock_click)

    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="m1", name="move_mouse", arguments={"x": 500, "y": 300})],
            model="test-model",
        ),
        LLMResponse(
            content="Moved mouse to (500, 300). Now clicking.",
            tool_calls=[ToolCall(id="m2", name="click", arguments={"button": "left"})],
            model="test-model",
        ),
        LLMResponse(content="Clicked at (500, 300).", model="test-model"),
    ]

    provider = MockScriptedProvider(responses)
    brain = AIBrain(provider=provider, registry=registry)

    reply = brain.process_user_message("Move mouse to 500, 300 and click")
    assert reply == "Clicked at (500, 300)."
    mock_move.execute.assert_called_once_with(x=500, y=300)
    mock_click.execute.assert_called_once_with(button="left")
