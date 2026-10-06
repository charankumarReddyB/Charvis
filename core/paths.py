"""
Centralized path resolution for CHARVIS (Phase 18).
Ensures resource and configuration paths resolve reliably regardless of the current
working directory (e.g. launched from Antigravity, terminal, or Windows Startup folder).
"""

from pathlib import Path
from typing import Union

# Project root directory determined from this module location
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def get_project_root() -> Path:
    """Return the absolute Path to the CHARVIS project root directory."""
    return PROJECT_ROOT


def resolve_path(path: Union[str, Path]) -> Path:
    """
    Resolve a path relative to the project root directory if it is not absolute.
    Always returns an absolute Path.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def get_data_dir() -> Path:
    """Return the data directory, creating it if necessary."""
    path = PROJECT_ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    """Return the logs directory under data/logs."""
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_runtime_dir() -> Path:
    """Return the runtime state and metadata directory under data/runtime."""
    path = get_data_dir() / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_memory_dir() -> Path:
    """Return the memory database directory under data/memory."""
    path = get_data_dir() / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_workspace_dir() -> Path:
    """Return the sandboxed user workspace directory under data/workspace."""
    path = get_data_dir() / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_browser_profile_dir() -> Path:
    """Return the isolated browser profile directory under data/browser_profile."""
    path = get_data_dir() / "browser_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_memory_db_path() -> Path:
    """Return the default SQLite database path for persistent memory."""
    return get_memory_dir() / "charvis_memory.db"
