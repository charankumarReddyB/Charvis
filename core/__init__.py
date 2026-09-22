"""
CHARVIS Core Package.
Contains the central AI Brain, provider abstractions, and architectural core.
"""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "AIBrain":
        from core.brain import AIBrain
        return AIBrain
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["AIBrain"]
