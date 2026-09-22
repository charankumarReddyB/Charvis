"""
OpenAI LLM provider implementation for CHARVIS.
Uses official openai SDK with error handling, provider abstraction, and tool calling.
"""

import json
from typing import Any, Dict, List, Optional
import openai

from core.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ToolCall,
)
from logger import get_logger
from tools.schemas import ToolSchema

logger = get_logger("CHARVIS.Provider.OpenAI")


class OpenAIProvider(BaseLLMProvider):
    """LLM provider implementation for OpenAI and OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        timeout: float = 30.0,
        client: Optional[openai.OpenAI] = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

        if client is not None:
            self._client = client
        else:
            if not api_key or not api_key.strip():
                raise ProviderAuthError(
                    "OpenAI API key is missing. Please set OPENAI_API_KEY in your .env file or environment."
                )
            self._client = openai.OpenAI(
                api_key=api_key.strip(),
                base_url=base_url if base_url and base_url.strip() else None,
                timeout=timeout,
            )

        logger.debug("OpenAIProvider initialized with model: %s", self._model)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def generate_response(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolSchema]] = None,
    ) -> LLMResponse:
        """Send chat messages and tool definitions to OpenAI and return standardized LLMResponse."""
        logger.debug(
            "Sending chat completion request with %d messages and %d tools",
            len(messages),
            len(tools) if tools else 0,
        )
        api_messages = [msg.to_dict() for msg in messages]

        try:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": api_messages,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                kwargs["max_tokens"] = self._max_tokens

            if tools and len(tools) > 0:
                kwargs["tools"] = [t.to_openai_format() for t in tools]

            response = self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message
            content = message.content or ""

            # Parse tool calls if returned by model
            tool_calls: Optional[List[ToolCall]] = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    raw_args = tc.function.arguments
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to decode JSON arguments for tool %s: %s", tc.function.name, raw_args)
                        parsed_args = {"_raw": raw_args}

                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=parsed_args if isinstance(parsed_args, dict) else {"arg": parsed_args},
                        )
                    )

            usage_dict = None
            if hasattr(response, "usage") and response.usage:
                usage_dict = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                    "completion_tokens": getattr(response.usage, "completion_tokens", None),
                    "total_tokens": getattr(response.usage, "total_tokens", None),
                }

            logger.debug(
                "Received response from OpenAI (model: %s, tool_calls: %d)",
                response.model,
                len(tool_calls) if tool_calls else 0,
            )
            return LLMResponse(
                content=content.strip() if content else None,
                model=response.model or self._model,
                usage=usage_dict,
                tool_calls=tool_calls,
            )

        except openai.AuthenticationError as e:
            logger.error("Authentication failed with OpenAI API: %s", str(e))
            raise ProviderAuthError(
                "Authentication failed. Please verify your OPENAI_API_KEY in the .env file."
            ) from e

        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit or quota exceeded: %s", str(e))
            raise ProviderRateLimitError(
                "OpenAI rate limit or quota exceeded. Please check your account usage and plan."
            ) from e

        except (openai.APITimeoutError, openai.APIConnectionError) as e:
            logger.error("OpenAI network/connection error: %s", str(e))
            raise ProviderConnectionError(
                "Unable to connect to OpenAI service. Please check your network connection."
            ) from e

        except openai.APIError as e:
            logger.error("OpenAI API error: %s", str(e))
            raise ProviderError(f"OpenAI service error: {e.message or str(e)}") from e

        except Exception as e:
            logger.error("Unexpected error in OpenAIProvider: %s", str(e))
            raise ProviderError(f"Unexpected provider error: {str(e)}") from e
