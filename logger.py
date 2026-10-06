"""
Logging configuration for CHARVIS.
Provides dual output: formatted console logging and rotating file logging.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config import Settings, get_settings

_LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s]: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_INITIALIZED = False


import re

class SensitiveDataFilter(logging.Filter):
    """
    Sanitizes log records to prevent accidental credential, token, or secret exposure (Phase 17).
    Redacts patterns matching API keys, passwords, bearer tokens, pins, and private keys.
    """
    PATTERNS = [
        (re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|pwd|auth|authorization)\s*[:=]\s*["\']?([^"\'\s,;]+)["\']?'), r'\1="[REDACTED]"'),
        (re.compile(r'(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{10,})'), r'\1[REDACTED]'),
        (re.compile(r'(?i)(session_token)\s*[:=]\s*["\']?([^"\'\s,;]+)["\']?'), r'\1="[REDACTED]"'),
        (re.compile(r'(?i)(cvv|pin|otp)\s*[:=]\s*["\']?(\d+)["\']?'), r'\1="[REDACTED]"'),
        (re.compile(r'\b(sk-[a-zA-Z0-9_\-]{20,})\b'), r'[REDACTED KEY]'),
        (re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----'), r'[REDACTED PRIVATE KEY]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, replacement in self.PATTERNS:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
        return True


def setup_logging(settings: Optional[Settings] = None, force: bool = False) -> logging.Logger:
    """
    Initialize the root logging system for CHARVIS.
    Configures console output and rotating file output.
    """
    global _INITIALIZED
    if _INITIALIZED and not force:
        return logging.getLogger("CHARVIS")

    if settings is None:
        settings = get_settings()

    # Ensure log directory exists
    log_file: Path = settings.log_file_path
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    numeric_level = getattr(logging, settings.log_level, logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers and close existing ones cleanly
    for handler in list(root_logger.handlers):
        handler.close()
    root_logger.handlers.clear()

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    data_filter = SensitiveDataFilter()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(data_filter)
    root_logger.addHandler(console_handler)

    # Rotating File Handler (10MB max size, keeping up to 5 backups)
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(data_filter)
    root_logger.addHandler(file_handler)

    _INITIALIZED = True
    app_logger = logging.getLogger("CHARVIS")
    app_logger.debug("Logging initialized successfully at level %s", settings.log_level)
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance configured for the given component name."""
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
