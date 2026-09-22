"""
Base interface and data models for AI LLM providers in CHARVIS.
Allows pluggable providers (OpenAI, Anthropic, local, etc.) without altering the Brain.
Includes support for tool calling and function schemas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional

from tools.schemas import ToolSchema


class ProviderError(Exception):
    """Base exception for all AI provider errors."""
    pass


class ProviderAuthError(ProviderError):
    """Raised when authentication fails (missing or invalid API key)."""
    pass


class ProviderConnectionError(ProviderError):
    """Raised when network, connection, or timeout issues occur."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when rate limit or quota is exceeded."""
    pass


@dataclass
class ToolCall:
    """Represents a request by the LLM to call a specific tool."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMMessage:
    """Represents a single message in a conversation, including tool requests and tool responses."""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary compatible with chat APIs."""
        msg: Dict[str, Any] = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content
        elif self.role != "assistant" or not self.tool_calls:
            msg["content"] = ""

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.name and self.role == "tool":
            msg["name"] = self.name

        return msg


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: Optional[str] = None
    model: str = ""
    usage: Optional[Dict[str, Any]] = field(default=None)
    tool_calls: Optional[List[ToolCall]] = field(default=None)

    @property
    def has_tool_calls(self) -> bool:
        """Check if the response contains any requested tool calls."""
        return bool(self.tool_calls and len(self.tool_calls) > 0)


class BaseLLMProvider(ABC):
    """Abstract base class for all AI LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier name of the provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the active model name used by this provider."""
        pass

    @abstractmethod
    def generate_response(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolSchema]] = None,
    ) -> LLMResponse:
        """
        Generate a text response or tool calls from the LLM given messages and available tools.

        :param messages: List of LLMMessage objects representing conversation context.
        :param tools: Optional list of ToolSchema instances available to the LLM.
        :return: LLMResponse containing text output, tool calls, and metadata.
        :raises ProviderError: On provider, connection, or API failures.
        """
        pass
