"""
Unit tests for background runtime shutdown order, idempotency, and resource release (Phase 17).
"""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock
import pytest
from runtime.controller import RuntimeController
from runtime.state import RuntimeState


def test_runtime_shutdown_idempotency():
    """Verify runtime stop() is completely idempotent when called multiple times."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_brain = MagicMock()
        mock_brain.memory_manager = MagicMock()

        controller = RuntimeController(
            brain=mock_brain,
            runtime_dir=Path(tmp_dir),
        )

        controller.start(block=False)
        assert controller.state == RuntimeState.RUNNING

        # 1st stop
        controller.stop()
        assert controller.state == RuntimeState.STOPPED

        # 2nd stop (idempotent)
        controller.stop()
        assert controller.state == RuntimeState.STOPPED


def test_runtime_shutdown_releases_lock():
    """Verify runtime shutdown removes lock and metadata files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_brain = MagicMock()
        controller = RuntimeController(
            brain=mock_brain,
            runtime_dir=Path(tmp_dir),
        )

        controller.start(block=False)
        assert controller.runtime_lock.lock_file.exists()
        assert controller.runtime_lock.meta_file.exists()

        controller.stop()
        assert not controller.runtime_lock.lock_file.exists()
        assert not controller.runtime_lock.meta_file.exists()
