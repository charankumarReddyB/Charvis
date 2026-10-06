"""
Unit tests for Centralized Project Path Resolution (Phase 18).
Ensures paths resolve reliably from any working directory without hardcoded developer paths.
"""

import os
from pathlib import Path
import pytest

from core.paths import (
    get_data_dir,
    get_logs_dir,
    get_memory_db_path,
    get_project_root,
    get_runtime_dir,
    get_workspace_dir,
    resolve_path,
)


def test_get_project_root_exists():
    """Verify get_project_root resolves to a valid existing directory containing main.py."""
    root = get_project_root()
    assert root.exists()
    assert (root / "main.py").exists()
    assert (root / "config.py").exists()


def test_resolve_path_relative_and_absolute():
    """Verify relative paths resolve from project root and absolute paths are preserved."""
    root = get_project_root()

    rel = resolve_path("data/logs")
    assert rel == (root / "data" / "logs").resolve()

    abs_path = Path("C:/Windows/Temp").resolve()
    assert resolve_path(abs_path) == abs_path


def test_path_resolution_independent_of_cwd(tmp_path):
    """Verify path resolution does not change when working directory changes."""
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Working directory is now temporary sandbox
        assert Path.cwd() == tmp_path.resolve()

        root = get_project_root()
        assert (root / "main.py").exists()

        log_dir = get_logs_dir()
        assert log_dir == (root / "data" / "logs").resolve()
    finally:
        os.chdir(original_cwd)


def test_data_directories_resolution():
    """Verify all standardized data directories resolve to children of project data dir."""
    root = get_project_root()
    data_dir = get_data_dir()

    assert data_dir == (root / "data").resolve()
    assert get_logs_dir() == (data_dir / "logs").resolve()
    assert get_workspace_dir() == (data_dir / "workspace").resolve()
    assert get_runtime_dir() == (data_dir / "runtime").resolve()
    assert get_memory_db_path() == (data_dir / "memory" / "charvis_memory.db").resolve()
