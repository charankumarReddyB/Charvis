"""
Filesystem management package for CHARVIS.
Provides secure, sandboxed file and directory operations with strict boundary validation.
"""

from filesystem.sandbox import (
    FilesystemSandbox,
    SandboxSecurityError,
    SUPPORTED_TEXT_EXTENSIONS,
    UnsupportedFileTypeError,
    get_filesystem_sandbox,
)

__all__ = [
    "FilesystemSandbox",
    "SandboxSecurityError",
    "UnsupportedFileTypeError",
    "SUPPORTED_TEXT_EXTENSIONS",
    "get_filesystem_sandbox",
]
