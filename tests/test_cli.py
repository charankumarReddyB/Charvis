"""
Unit tests for the CHARVIS interactive CLI terminal loop.
"""

from unittest.mock import MagicMock, patch
import pytest

from config import Settings
from core.brain import AIBrain
from main import interactive_loop


def test_cli_exit_command(capsys):
    """Verify typing 'exit' exits the loop cleanly and prints goodbye."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=["exit"]):
        interactive_loop(mock_brain, settings)

    captured = capsys.readouterr()
    assert "Goodbye!" in captured.out
    mock_brain.process_user_message.assert_not_called()


def test_cli_quit_command(capsys):
    """Verify typing 'quit' exits the loop cleanly."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=["quit"]):
        interactive_loop(mock_brain, settings)

    captured = capsys.readouterr()
    assert "Goodbye!" in captured.out


def test_cli_empty_input_then_exit(capsys):
    """Verify empty input is skipped without calling the brain."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=["", "   ", "exit"]):
        interactive_loop(mock_brain, settings)

    mock_brain.process_user_message.assert_not_called()


def test_cli_message_exchange(capsys):
    """Verify user message is sent to brain and response printed to terminal."""
    mock_brain = MagicMock(spec=AIBrain)
    mock_brain.process_user_message.return_value = "Machine learning is a field of AI."
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=["Explain machine learning", "exit"]):
        interactive_loop(mock_brain, settings)

    assert mock_brain.process_user_message.called
    called_args, called_kwargs = mock_brain.process_user_message.call_args
    passed_input = called_kwargs.get("user_input") if "user_input" in called_kwargs else called_args[0]
    assert passed_input == "Explain machine learning"
    captured = capsys.readouterr()
    assert "Machine learning is a field of AI." in captured.out


def test_cli_reset_command(capsys):
    """Verify /reset triggers brain.reset_session()."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=["/reset", "exit"]):
        interactive_loop(mock_brain, settings)

    mock_brain.reset_session.assert_called_once()
    captured = capsys.readouterr()
    assert "Session memory has been reset" in captured.out


def test_cli_keyboard_interrupt_handling(capsys):
    """Verify KeyboardInterrupt is handled gracefully without crashing."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        interactive_loop(mock_brain, settings)

    captured = capsys.readouterr()
    assert "Session interrupted" in captured.out


def test_cli_eof_handling(capsys):
    """Verify EOFError (Ctrl+D) is handled gracefully without crashing."""
    mock_brain = MagicMock(spec=AIBrain)
    settings = Settings(openai_api_key="sk-test")

    with patch("builtins.input", side_effect=EOFError):
        interactive_loop(mock_brain, settings)

    captured = capsys.readouterr()
    assert "Session interrupted" in captured.out
