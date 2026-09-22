"""
Unit tests for AI Brain cognitive tool loop, multi-step calling, and safeguards.
"""

from typing import List, Optional
from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMMessage, LLMResponse, ToolCall
from tools.calculator import CalculatorTool
from tools.registry import ToolRegistry
from tools.schemas import ToolSchema


class ScriptedProvider(BaseLLMProvider):
    """Mock provider that returns a predetermined sequence of LLMResponses."""

    def __init__(self, responses: List[LLMResponse]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.received_messages_history = []
        self.received_tools = None

    @property
    def provider_name(self) -> str:
        return "scripted_mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_response(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolSchema]] = None,
    ) -> LLMResponse:
        self.call_count += 1
        self.received_messages_history.append(list(messages))
        self.received_tools = tools

        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Default response", model="mock-model")


def test_brain_normal_response_without_tools():
    """Verify brain handles standard conversational responses without tool calls."""
    mock_provider = ScriptedProvider(
        [LLMResponse(content="Hello! How can I help you today?", model="mock-model")]
    )
    brain = AIBrain(provider=mock_provider)

    result = brain.process_user_message("Hello")
    assert result == "Hello! How can I help you today?"
    assert mock_provider.call_count == 1
    # Check that tools were passed to provider
    assert mock_provider.received_tools is not None
    assert len(mock_provider.received_tools) >= 1


def test_brain_executes_tool_call_and_returns_final_response():
    """Verify complete tool loop: User -> LLM tool call -> Router execution -> LLM final answer."""
    tool_call = ToolCall(id="call_calc_01", name="calculator", arguments={"expression": "25 * 18"})
    responses = [
        # 1. LLM requests calculator tool execution
        LLMResponse(content=None, tool_calls=[tool_call], model="mock-model"),
        # 2. LLM responds with answer after receiving tool result 450
        LLMResponse(content="25 multiplied by 18 is 450.", model="mock-model"),
    ]
    mock_provider = ScriptedProvider(responses)
    brain = AIBrain(provider=mock_provider)

    result = brain.process_user_message("What is 25 * 18?")

    assert result == "25 multiplied by 18 is 450."
    assert mock_provider.call_count == 2

    # Check conversation history contains tool execution
    history = brain.get_history()
    # Expect: [System, User, Assistant (tool_calls), Tool (result), Assistant (final)]
    assert len(history) == 5
    assert history[1].role == "user"
    assert history[2].role == "assistant"
    assert history[2].tool_calls == [tool_call]
    assert history[3].role == "tool"
    assert history[3].content == "450"
    assert history[4].role == "assistant"
    assert history[4].content == "25 multiplied by 18 is 450."


def test_brain_handles_unrecognized_tool_gracefully():
    """Verify requesting an unknown tool returns error to LLM, which explains it to the user."""
    tool_call = ToolCall(id="call_bad_01", name="open_chrome", arguments={})
    responses = [
        LLMResponse(content=None, tool_calls=[tool_call], model="mock-model"),
        LLMResponse(content="I do not have application control tools available yet.", model="mock-model"),
    ]
    mock_provider = ScriptedProvider(responses)
    brain = AIBrain(provider=mock_provider)

    result = brain.process_user_message("Open Chrome.")
    assert "application control tools" in result
    assert mock_provider.call_count == 2

    # Verify tool result recorded tool failure
    history = brain.get_history()
    assert history[3].role == "tool"
    assert "not recognized" in history[3].content


def test_brain_max_iteration_safeguard():
    """Verify tool loop terminates if LLM loops indefinitely on tool calls."""
    infinite_tool_call = ToolCall(id="call_loop", name="calculator", arguments={"expression": "1 + 1"})
    # Always return tool calls
    responses = [
        LLMResponse(content=None, tool_calls=[infinite_tool_call], model="mock-model")
        for _ in range(10)
    ]
    mock_provider = ScriptedProvider(responses)
    brain = AIBrain(provider=mock_provider, max_tool_iterations=3)

    result = brain.process_user_message("Loop forever")
    assert "maximum tool execution step limit" in result
    assert mock_provider.call_count == 3
