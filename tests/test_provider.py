"""
Unit tests for provider abstraction and OpenAIProvider implementation.
All tests use mocking and do not make actual API calls.
"""

from unittest.mock import MagicMock
import pytest
import openai

from core.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
)
from core.providers.openai_provider import OpenAIProvider
from core.providers import get_provider
from config import Settings


def test_base_provider_cannot_be_instantiated():
    """Verify BaseLLMProvider is an ABC and cannot be directly instantiated."""
    with pytest.raises(TypeError):
        BaseLLMProvider()  # pylint: disable=abstract-class-instantiated


def test_llm_message_to_dict():
    """Verify LLMMessage serializes to chat-compatible dictionary."""
    msg = LLMMessage(role="user", content="Hello CHARVIS")
    assert msg.to_dict() == {"role": "user", "content": "Hello CHARVIS"}


def test_llm_response_structure():
    """Verify LLMResponse data container."""
    resp = LLMResponse(
        content="Welcome!",
        model="gpt-4o-mini",
        usage={"total_tokens": 42},
    )
    assert resp.content == "Welcome!"
    assert resp.model == "gpt-4o-mini"
    assert resp.usage == {"total_tokens": 42}


def test_openai_provider_missing_key_raises_auth_error():
    """Verify OpenAIProvider raises ProviderAuthError when no key is configured."""
    with pytest.raises(ProviderAuthError) as exc_info:
        OpenAIProvider(api_key=None)
    assert "OPENAI_API_KEY" in str(exc_info.value)

    with pytest.raises(ProviderAuthError):
        OpenAIProvider(api_key="   ")


def test_openai_provider_generate_response_success():
    """Verify OpenAIProvider correctly processes chat completion with mocked client."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello Charan, how can I assist you today?"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "gpt-4o-mini"
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=8, total_tokens=18)
    mock_client.chat.completions.create.return_value = mock_response

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)
    messages = [
        LLMMessage(role="system", content="You are CHARVIS."),
        LLMMessage(role="user", content="Hello"),
    ]

    result = provider.generate_response(messages)

    assert result.content == "Hello Charan, how can I assist you today?"
    assert result.model == "gpt-4o-mini"
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
    mock_client.chat.completions.create.assert_called_once()


def test_openai_provider_auth_error_handling():
    """Verify openai.AuthenticationError is translated to ProviderAuthError."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
        message="Incorrect API key",
        response=mock_response,
        body=None,
    )

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)
    with pytest.raises(ProviderAuthError):
        provider.generate_response([LLMMessage(role="user", content="Test")])


def test_openai_provider_rate_limit_error_handling():
    """Verify openai.RateLimitError is translated to ProviderRateLimitError."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_client.chat.completions.create.side_effect = openai.RateLimitError(
        message="Quota exceeded",
        response=mock_response,
        body=None,
    )

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)
    with pytest.raises(ProviderRateLimitError):
        provider.generate_response([LLMMessage(role="user", content="Test")])


def test_openai_provider_connection_error_handling():
    """Verify connection errors are translated to ProviderConnectionError."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = openai.APIConnectionError(
        request=MagicMock()
    )

    provider = OpenAIProvider(api_key="sk-mock-key", client=mock_client)
    with pytest.raises(ProviderConnectionError):
        provider.generate_response([LLMMessage(role="user", content="Test")])


def test_get_provider_factory():
    """Verify get_provider creates correct provider from settings."""
    settings = Settings(ai_provider="openai", openai_api_key="sk-test-mock-key")
    provider = get_provider(settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"
    assert provider.model_name == settings.ai_model


def test_get_provider_unsupported_raises():
    """Verify unsupported provider name raises ProviderError."""
    settings = Settings(ai_provider="nonexistent_provider")
    with pytest.raises(ProviderError):
        get_provider(settings)
