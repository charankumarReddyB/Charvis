"""
Unit tests for CHARVIS AI Brain, session memory, and conversation flow.
"""

from typing import Optional
from unittest.mock import MagicMock
import pytest

from core.brain import AIBrain, DEFAULT_SYSTEM_PROMPT
from core.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRateLimitError,
)


class MockProvider(BaseLLMProvider):
    """Test double for BaseLLMProvider."""

    def __init__(self, response_text: str = "Mock response") -> None:
        self.response_text = response_text
        self.call_count = 0
        self.last_messages = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate_response(self, messages: list[LLMMessage], tools: Optional[list] = None) -> LLMResponse:
        self.call_count += 1
        self.last_messages = list(messages)
        return LLMResponse(content=self.response_text, model="mock-model")


def test_brain_initialization():
    """Verify brain initializes with system prompt in history."""
    provider = MockProvider()
    brain = AIBrain(provider=provider)

    assert brain.provider_name == "mock"
    history = brain.get_history()
    assert len(history) == 1
    assert history[0].role == "system"
    assert "CHARVIS" in history[0].content
    assert "PHASE" in history[0].content.upper()


def test_brain_custom_system_prompt():
    """Verify custom system prompt is set correctly."""
    provider = MockProvider()
    brain = AIBrain(provider=provider, system_prompt="Custom prompt instructions.")
    history = brain.get_history()
    assert history[0].content == "Custom prompt instructions."


def test_empty_user_message():
    """Verify empty or whitespace-only messages are rejected without calling provider."""
    provider = MockProvider()
    brain = AIBrain(provider=provider)

    resp = brain.process_user_message("   ")
    assert "Please type a question" in resp
    assert provider.call_count == 0
    assert len(brain.get_history()) == 1


def test_single_turn_conversation():
    """Verify single turn interaction updates history with user and assistant messages."""
    provider = MockProvider(response_text="Polymorphism allows objects to take many forms.")
    brain = AIBrain(provider=provider)

    response = brain.process_user_message("What is polymorphism?")
    assert response == "Polymorphism allows objects to take many forms."

    history = brain.get_history()
    assert len(history) == 3
    assert history[1].role == "user"
    assert history[1].content == "What is polymorphism?"
    assert history[2].role == "assistant"
    assert history[2].content == "Polymorphism allows objects to take many forms."


def test_multi_turn_session_memory():
    """Verify multi-turn session remembers previous context within the session."""
    provider = MockProvider()
    brain = AIBrain(provider=provider)

    # Turn 1
    provider.response_text = "Nice to meet you, Charan!"
    resp1 = brain.process_user_message("My name is Charan.")
    assert resp1 == "Nice to meet you, Charan!"

    # Turn 2
    provider.response_text = "Your name is Charan."
    resp2 = brain.process_user_message("What is my name?")
    assert resp2 == "Your name is Charan."

    history = brain.get_history()
    assert len(history) == 5  # System + User1 + Assistant1 + User2 + Assistant2
    assert history[1].content == "My name is Charan."
    assert history[3].content == "What is my name." or history[3].content == "What is my name?"

    # Verify that the provider received the full accumulated history on turn 2
    assert len(provider.last_messages) == 4  # System + User1 + Assistant1 + User2


def test_session_reset():
    """Verify reset_session clears conversation history back to system prompt."""
    provider = MockProvider(response_text="Acknowledged.")
    brain = AIBrain(provider=provider)

    brain.process_user_message("Remember this temporary message.")
    assert len(brain.get_history()) == 3

    brain.reset_session()
    history = brain.get_history()
    assert len(history) == 1
    assert history[0].role == "system"


def test_brain_auth_error_graceful_handling():
    """Verify ProviderAuthError returns a clear configuration message without crashing."""
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.provider_name = "mock"
    mock_provider.generate_response.side_effect = ProviderAuthError("Missing key")

    brain = AIBrain(provider=mock_provider)
    response = brain.process_user_message("Hello")

    assert "OPENAI_API_KEY" in response or "Authentication failed" in response
    # Verify failed user message is removed so history remains clean
    assert len(brain.get_history()) == 1


def test_brain_connection_error_graceful_handling():
    """Verify ProviderConnectionError returns connection advice without crashing."""
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.provider_name = "mock"
    mock_provider.generate_response.side_effect = ProviderConnectionError("Unreachable host")

    brain = AIBrain(provider=mock_provider)
    response = brain.process_user_message("Hello")

    assert "couldn't reach the AI service" in response
    assert len(brain.get_history()) == 1


def test_brain_rate_limit_error_graceful_handling():
    """Verify ProviderRateLimitError returns quota advice without crashing."""
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.provider_name = "mock"
    mock_provider.generate_response.side_effect = ProviderRateLimitError("Quota limit")

    brain = AIBrain(provider=mock_provider)
    response = brain.process_user_message("Hello")

    assert "quota" in response.lower() or "rate limit" in response.lower()
    assert len(brain.get_history()) == 1
