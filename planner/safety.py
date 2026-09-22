"""
Safety, validation, and defense invariants for CHARVIS Task Planner (Phase 14).
Protects against code injection, runaway loops, and unauthorized actions.
"""

import re
from typing import Any, Dict, Set
from planner.models import PlanSecurityError, Task

# Executable code and dangerous injection signatures
CODE_INJECTION_PATTERNS = [
    # Python code injection
    re.compile(r"(?i)\b(eval|exec|__import__|compile)\s*\("),
    re.compile(r"(?i)\b(import\s+(?:os|sys|subprocess|shutil))\b"),
    re.compile(r"(?i)\b(?:os|sys|subprocess)\.(?:system|popen|call|check_call|run)\b"),
    re.compile(r"(?i)\bpython(?:\d+)?\s+-c\b"),
    re.compile(r"(?i)\bopen\s*\(\s*['\"][^'\"]*['\"]\s*,\s*['\"][rwax]"),

    # Shell and system command invocation
    re.compile(r"(?i)\b(powershell(?:\.exe)?|cmd(?:\.exe)?)\b"),
    re.compile(r"(?i)\b(?:/bin/)?(?:bash|sh|zsh)\s+-c\b"),
    re.compile(r"(?i)\b(?:rmdir|del)\s+/[sfaq]\b"),
    re.compile(r"(?i)\bformat\s+[a-z]:\b"),

    # SQL Injection
    re.compile(r"(?i)\b(drop\s+table|delete\s+from|alter\s+table|truncate\s+table)\b"),

    # Script tags and JavaScript
    re.compile(r"(?i)<script\b"),
    re.compile(r"(?i)\bjavascript\s*:"),
]

# Non-retryable tools where automated re-execution is unsafe or destructive
NON_RETRYABLE_TOOLS: Set[str] = {
    "delete_file",
    "delete_directory",
    "shutdown_system",
    "restart_system",
    "lock_workstation",
    "forget_memory",
    "clear_session_memory",
}

# Substrings in arguments indicating external or financial actions that must never be retried
IRREVERSIBLE_ARG_PATTERNS = [
    "buy", "purchase", "checkout", "pay", "payment", "order",
    "subscribe", "transfer", "delete", "remove", "send message", "send email",
]


def is_executable_code(value: Any) -> bool:
    """
    Check if a value (string or nested data) contains executable script or command patterns.
    """
    if isinstance(value, str):
        for pattern in CODE_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        return False
    elif isinstance(value, (list, tuple)):
        return any(is_executable_code(v) for v in value)
    elif isinstance(value, dict):
        return any(is_executable_code(k) or is_executable_code(v) for k, v in value.items())
    return False


def is_non_retryable_action(tool_name: str, arguments: Dict[str, Any]) -> bool:
    """
    Determine whether a failed tool step should be blocked from automatic retry.
    Destructive, financial, or state-altering actions are strictly non-retryable.
    """
    if tool_name in NON_RETRYABLE_TOOLS:
        return True

    # Check arguments for irreversible / financial action markers
    arg_str = " ".join(str(v).lower() for v in arguments.values())
    for pattern in IRREVERSIBLE_ARG_PATTERNS:
        if pattern in arg_str:
            return True

    return False


def validate_no_executable_code(tool_name: str, arguments: Dict[str, Any]) -> None:
    """
    Raise PlanSecurityError if tool_name or any argument contains executable code.
    """
    if is_executable_code(tool_name):
        raise PlanSecurityError(f"Tool name '{tool_name}' contains illegal executable code patterns.")

    if is_executable_code(arguments):
        raise PlanSecurityError(
            f"Arguments for tool '{tool_name}' contain illegal executable code or command injection."
        )


def sanitize_task_logging(task_or_text: Any) -> str:
    """
    Format safe bounded metadata string for diagnostic logging or sanitize text.
    Redacts sensitive credentials, tokens, and credit card numbers.
    """
    if isinstance(task_or_text, Task):
        return (
            f"[Task id={task_or_text.id[:8]}, status={task_or_text.status.value}, "
            f"steps={len(task_or_text.steps)}, current_step={task_or_text.current_step}]"
        )

    raw = str(task_or_text)
    redacted = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", raw)
    redacted = re.sub(r"(?i)(password\s*=\s*)[^\s,]+", r"\1[REDACTED_PASSWORD]", redacted)
    redacted = re.sub(r"\b(?:\d{4}[ -]?){3}\d{4}\b", "[REDACTED_CARD]", redacted)
    return redacted
