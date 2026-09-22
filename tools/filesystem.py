"""
Filesystem Tools for CHARVIS.
Provides safe, sandboxed file and directory operations with human confirmation
for destructive or state-modifying actions.
"""

from typing import Any, Dict, List, Optional
from core.safety import RiskLevel
from filesystem.sandbox import (
    FilesystemSandbox,
    SandboxSecurityError,
    UnsupportedFileTypeError,
    get_filesystem_sandbox,
)
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema


class ReadFileTool(BaseTool):
    """Tool to read a UTF-8 text file from the sandbox."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a text file inside the CHARVIS sandbox workspace. "
            "Example: read_file(path='notes.txt') or read_file(path='docs/readme.md')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative or absolute path inside the workspace to the text file",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", "")).strip()
        try:
            content = self._sandbox.read_text(path_str)
            return {
                "success": True,
                "path": path_str,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
            }
        except (SandboxSecurityError, UnsupportedFileTypeError, FileNotFoundError, IsADirectoryError, ValueError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to read file '{path_str}': {e}",
            }


class WriteFileTool(BaseTool):
    """Tool to create or overwrite a UTF-8 text file in the sandbox."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Create or overwrite a text file in the CHARVIS sandbox workspace. "
            "Requires user confirmation. "
            "Example: write_file(path='notes.txt', content='Meeting notes...')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative or absolute path inside the workspace to the text file",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    param_type="string",
                    description="Text content to write to the file",
                    required=True,
                ),
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        path_str = str(arguments.get("path", "")).strip()
        content = str(arguments.get("content", ""))
        preview = content[:60].replace("\n", " ") + ("..." if len(content) > 60 else "")

        try:
            resolved = self._sandbox.validate_path(path_str, must_exist=False)
            status = "OVERWRITE existing file" if resolved.exists() else "CREATE new file"
            return (
                f"Action: {status} at '{path_str}'. "
                f"Size: {len(content.encode('utf-8'))} bytes. Content preview: '{preview}'."
            )
        except Exception:
            return f"Action: Write file at '{path_str}' ({len(content)} chars)."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", "")).strip()
        content = str(kwargs.get("content", ""))

        try:
            bytes_written, is_overwrite = self._sandbox.write_text(path_str, content)
            action_desc = "overwritten" if is_overwrite else "created"
            return {
                "success": True,
                "path": path_str,
                "bytes_written": bytes_written,
                "is_overwrite": is_overwrite,
                "message": f"File '{path_str}' {action_desc} successfully ({bytes_written} bytes).",
            }
        except (SandboxSecurityError, UnsupportedFileTypeError, IsADirectoryError, ValueError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to write file '{path_str}': {e}",
            }


class ListDirectoryTool(BaseTool):
    """Tool to list files and folders in a sandbox directory."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return (
            "List files and directories inside a specified folder in the sandbox workspace. "
            "Example: list_directory(path='.') or list_directory(path='subfolder')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative path inside the workspace to list (default '.')",
                    required=False,
                    default=".",
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", ".")).strip() or "."
        try:
            entries = self._sandbox.list_dir(path_str)
            return {
                "success": True,
                "path": path_str,
                "count": len(entries),
                "entries": entries,
            }
        except (SandboxSecurityError, FileNotFoundError, NotADirectoryError, PermissionError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to list directory '{path_str}': {e}",
            }


class SearchFilesTool(BaseTool):
    """Tool to search for files by name within the sandbox workspace."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Search for files and directories matching a query name within the sandbox workspace. "
            "Example: search_files(query='notes') or search_files(query='.json', path='data')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="Filename search query or substring (case-insensitive)",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Starting directory within workspace to search (default '.')",
                    required=False,
                    default=".",
                ),
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        query = str(kwargs.get("query", "")).strip()
        path_str = str(kwargs.get("path", ".")).strip() or "."

        try:
            matches = self._sandbox.search(query=query, target_path=path_str)
            return {
                "success": True,
                "query": query,
                "search_root": path_str,
                "count": len(matches),
                "matches": matches,
            }
        except (SandboxSecurityError, FileNotFoundError, NotADirectoryError, ValueError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Search failed: {e}",
            }


class CreateDirectoryTool(BaseTool):
    """Tool to create a new directory inside the sandbox."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def description(self) -> str:
        return (
            "Create a new directory inside the CHARVIS sandbox workspace. "
            "Requires user confirmation. "
            "Example: create_directory(path='reports/2026')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative path of the new directory to create",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        path_str = str(arguments.get("path", "")).strip()
        return f"Will create new directory at '{path_str}' in sandbox workspace."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", "")).strip()

        try:
            created_path = self._sandbox.create_dir(path_str)
            return {
                "success": True,
                "path": path_str,
                "message": f"Directory '{path_str}' created successfully.",
            }
        except (SandboxSecurityError, FileExistsError, ValueError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to create directory '{path_str}': {e}",
            }


class DeleteFileTool(BaseTool):
    """Tool to permanently delete a file from the sandbox."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return (
            "Permanently delete a file from the CHARVIS sandbox workspace. "
            "Requires user confirmation. "
            "Example: delete_file(path='temp.txt')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative path of the file to delete",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        path_str = str(arguments.get("path", "")).strip()
        return f"[DESTRUCTIVE ACTION] Will permanently delete file '{path_str}'."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", "")).strip()

        try:
            self._sandbox.delete_file(path_str)
            return {
                "success": True,
                "path": path_str,
                "message": f"File '{path_str}' deleted successfully.",
            }
        except (SandboxSecurityError, FileNotFoundError, IsADirectoryError, PermissionError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to delete file '{path_str}': {e}",
            }


class DeleteDirectoryTool(BaseTool):
    """Tool to delete an empty directory from the sandbox."""

    def __init__(self, sandbox: Optional[FilesystemSandbox] = None) -> None:
        self._sandbox = sandbox or get_filesystem_sandbox()

    @property
    def name(self) -> str:
        return "delete_directory"

    @property
    def description(self) -> str:
        return (
            "Delete an EMPTY directory from the sandbox workspace. "
            "Requires user confirmation. Non-empty directories are refused. "
            "Example: delete_directory(path='empty_folder')"
        )

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.CONFIRMATION_REQUIRED

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="Relative path of the empty directory to delete",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        path_str = str(arguments.get("path", "")).strip()
        return f"[DESTRUCTIVE ACTION] Will delete empty directory '{path_str}'."

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        path_str = str(kwargs.get("path", "")).strip()

        try:
            self._sandbox.delete_dir(path_str)
            return {
                "success": True,
                "path": path_str,
                "message": f"Directory '{path_str}' deleted successfully.",
            }
        except (SandboxSecurityError, FileNotFoundError, NotADirectoryError, OSError, PermissionError) as e:
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "UnexpectedError",
                "message": f"Failed to delete directory '{path_str}': {e}",
            }
