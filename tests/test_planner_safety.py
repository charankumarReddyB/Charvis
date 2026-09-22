"""
Unit tests for CHARVIS Task Planner safety guardrails, code rejection, and sanitization (Phase 14).
"""

import pytest
from planner.models import PlanSecurityError
from planner.safety import (
    is_executable_code,
    is_non_retryable_action,
    sanitize_task_logging,
    validate_no_executable_code,
)


def test_is_executable_code_detects_injections():
    """Verify code injection detection across dangerous language constructs."""
    malicious_inputs = [
        "import os; os.system('calc')",
        "__import__('subprocess').Popen('calc')",
        "eval('2 + 2')",
        "exec('print(123)')",
        "subprocess.run(['cmd.exe', '/c', 'dir'])",
        "powershell -ExecutionPolicy Bypass -Command 'Get-Process'",
        "cmd.exe /c start notepad",
        "/bin/bash -c 'rm -rf /'",
        "python -c 'print(1)'",
        "open('/etc/passwd', 'r')",
    ]
    for code in malicious_inputs:
        assert is_executable_code(code) is True, f"Failed to detect executable code: {code}"


def test_is_executable_code_allows_benign_text():
    """Verify normal benign text, URLs, expressions, and sentences pass."""
    benign_inputs = [
        "2 + 2",
        "10 * 5",
        "https://example.com/search?q=weather",
        "Open Chrome, navigate to google.com, and search for Python docs",
        "What is the system battery status?",
        "my_test_file.txt",
        "User Charan preference for dark mode",
    ]
    for text in benign_inputs:
        assert is_executable_code(text) is False, f"False positive on benign text: {text}"


def test_validate_no_executable_code_raises_security_error():
    """Verify validate_no_executable_code blocks code arguments with PlanSecurityError."""
    with pytest.raises(PlanSecurityError) as exc_info:
        validate_no_executable_code(
            tool_name="type_text",
            arguments={"text": "__import__('os').system('dir')"},
        )
    assert "illegal executable code" in str(exc_info.value).lower()



def test_validate_no_executable_code_passes_safe_arguments():
    """Verify valid arguments pass without raising."""
    validate_no_executable_code(
        tool_name="calculator",
        arguments={"expression": "100 / 4"},
    )
    validate_no_executable_code(
        tool_name="open_browser",
        arguments={"url": "https://example.com"},
    )


def test_is_non_retryable_action():
    """Verify destructive or state-altering tools are flagged as non-retryable."""
    assert is_non_retryable_action("delete_file", {"path": "test.txt"}) is True
    assert is_non_retryable_action("delete_directory", {"path": "sub"}) is True
    assert is_non_retryable_action("shutdown_system", {}) is True
    assert is_non_retryable_action("restart_system", {}) is True
    assert is_non_retryable_action("forget_memory", {"memory_id": "123"}) is True

    # Benign read/perception tools are retryable
    assert is_non_retryable_action("calculator", {"expression": "2+2"}) is False
    assert is_non_retryable_action("read_file", {"path": "test.txt"}) is False
    assert is_non_retryable_action("get_page_info", {}) is False


def test_sanitize_task_logging():
    """Verify sensitive patterns such as tokens, passwords, and cards are redacted."""
    raw_log = "User typed sk-abcdef12345678901234567890 and password=SecretPassword123! with card 4111 2222 3333 4444"
    sanitized = sanitize_task_logging(raw_log)

    assert "sk-abcdef12345678901234567890" not in sanitized
    assert "SecretPassword123!" not in sanitized
    assert "4111 2222 3333 4444" not in sanitized
    assert "[REDACTED" in sanitized
