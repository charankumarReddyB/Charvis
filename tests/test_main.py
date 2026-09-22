"""
Unit tests for CHARVIS entry point and logging initialization.
"""

import logging
from pathlib import Path
import pytest
from main import main, print_banner
from logger import setup_logging, get_logger
from config import Settings


def test_print_banner(capsys):
    """Verify banner output includes key details."""
    print_banner("CHARVIS", "0.1.0", "development")
    captured = capsys.readouterr()
    assert "CHARVIS" in captured.out
    assert "0.1.0" in captured.out
    assert "development" in captured.out


def test_main_execution(tmp_path, monkeypatch):
    """Verify main() executes and completes successfully with exit code 0."""
    test_log_file = tmp_path / "test_main.log"
    settings = Settings(log_file_path=test_log_file, environment="testing")
    setup_logging(settings, force=True)

    # Simulate user typing exit immediately
    monkeypatch.setattr("builtins.input", lambda _: "exit")

    exit_code = main()
    assert exit_code == 0


def test_logger_file_creation(tmp_path):
    """Verify logger writes entries to the designated log file."""
    test_log = tmp_path / "test_run.log"
    settings = Settings(log_file_path=test_log, log_level="DEBUG")
    logger = setup_logging(settings, force=True)

    logger.info("Test message for file output verification")

    # Flush all handlers to disk
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert test_log.exists()
    content = test_log.read_text(encoding="utf-8")
    assert "Test message for file output verification" in content

