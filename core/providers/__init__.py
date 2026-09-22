"""
Providers package for CHARVIS.
Provides provider factory and unified exports.
"""

from typing import Optional

from config import Settings, get_settings
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


def get_provider(settings: Optional[Settings] = None) -> BaseLLMProvider:
    """
    Factory function to instantiate the configured LLM provider.
    """
    if settings is None:
        settings = get_settings()

    provider_type = settings.ai_provider.strip().lower()

    if provider_type == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.ai_model,
            base_url=settings.openai_base_url,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.request_timeout,
        )

    raise ProviderError(f"Unsupported AI provider: '{settings.ai_provider}'")


__all__ = [
    "BaseLLMProvider",
    "LLMMessage",
    "LLMResponse",
    "ProviderError",
    "ProviderAuthError",
    "ProviderConnectionError",
    "ProviderRateLimitError",
    "OpenAIProvider",
    "get_provider",
]
