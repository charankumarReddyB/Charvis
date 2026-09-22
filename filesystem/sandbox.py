"""
Centralized Filesystem Sandbox for CHARVIS.
Enforces strict directory containment, prevents traversal / escape attacks,
validates file extensions, and provides bounded operations.
"""

from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from config import get_settings
from logger import get_logger

logger = get_logger("CHARVIS.Filesystem.Sandbox")


class SandboxSecurityError(Exception):
    """Raised when a requested path violates the sandbox security policy."""
    pass


class UnsupportedFileTypeError(Exception):
    """Raised when an operation targets a binary or unsupported file format."""
    pass


# Explicit whitelist of allowed text file extensions
SUPPORTED_TEXT_EXTENSIONS: Set[str] = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
    ".py",
    ".java",
    ".html",
    ".css",
    ".js",
    ".xml",
    ".yaml",
    ".yml",
}


class FilesystemSandbox:
    """
    Centralized filesystem sandbox manager.
    Guarantees that all filesystem operations remain confined to allowed root directories.
    """

    def __init__(
        self,
        root_dirs: Optional[List[Union[str, Path]]] = None,
        max_file_read_size: Optional[int] = None,
        max_file_write_size: Optional[int] = None,
        max_search_results: Optional[int] = None,
        max_directory_entries: Optional[int] = None,
    ) -> None:
        settings = get_settings()

        if root_dirs:
            self.roots = [Path(r).resolve() for r in root_dirs]
        else:
            default_workspace = settings.filesystem_workspace.resolve()
            default_workspace.mkdir(parents=True, exist_ok=True)
            self.roots = [default_workspace]

        self.primary_root: Path = self.roots[0]
        self.max_file_read_size = (
            max_file_read_size if max_file_read_size is not None else settings.max_file_read_size
        )
        self.max_file_write_size = (
            max_file_write_size if max_file_write_size is not None else settings.max_file_write_size
        )
        self.max_search_results = (
            max_search_results if max_search_results is not None else settings.max_search_results
        )
        self.max_directory_entries = (
            max_directory_entries if max_directory_entries is not None else settings.max_directory_entries
        )

        logger.debug(
            "FilesystemSandbox initialized with roots=%s (read_limit=%d, write_limit=%d)",
            [str(r) for r in self.roots],
            self.max_file_read_size,
            self.max_file_write_size,
        )

    def validate_path(
        self,
        target_path: Union[str, Path],
        must_exist: bool = False,
        require_parent_in_sandbox: bool = True,
    ) -> Path:
        """
        Validate and resolve an input path against the sandbox boundaries.
        Returns the canonical, resolved Path inside an allowed sandbox root.
        Raises SandboxSecurityError or FileNotFoundError on validation failures.
        """
        if isinstance(target_path, str):
            clean_str = target_path.strip()
            if not clean_str:
                raise ValueError("Target path cannot be empty.")
            if "\0" in clean_str:
                raise SandboxSecurityError("Null byte detected in path.")
            p = Path(clean_str)
        elif isinstance(target_path, Path):
            p = target_path
        else:
            raise ValueError(f"Path must be a string or Path object, got {type(target_path).__name__}.")

        # If relative, anchor to the primary sandbox root
        if not p.is_absolute():
            resolved = (self.primary_root / p).resolve(strict=False)
        else:
            resolved = p.resolve(strict=False)

        # Enforce containment: resolved path must be within one of the allowed roots
        is_contained = any(self._is_within_root(resolved, root) for root in self.roots)
        if not is_contained:
            logger.warning("Sandbox traversal attempt blocked: '%s' resolved to '%s'", target_path, resolved)
            raise SandboxSecurityError(
                f"Access denied: Path '{target_path}' resolves to '{resolved}', which is outside the allowed sandbox."
            )

        # Ensure parent is within sandbox (especially for new files or directories)
        # Sandbox roots themselves are permitted even though their parent is outside the sandbox
        if require_parent_in_sandbox and not any(resolved == root for root in self.roots):
            parent_contained = any(self._is_within_root(resolved.parent, root) for root in self.roots)
            if not parent_contained:
                raise SandboxSecurityError(
                    f"Access denied: Parent directory of '{target_path}' is outside the sandbox."
                )

        # Check symlink destination if the path already exists
        if resolved.is_symlink():
            target_of_symlink = resolved.resolve(strict=True)
            if not any(self._is_within_root(target_of_symlink, root) for root in self.roots):
                raise SandboxSecurityError("Access denied: Symlink points outside the sandbox.")

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path does not exist: '{target_path}'")

        return resolved

    def _is_within_root(self, path: Path, root: Path) -> bool:
        """Helper to reliably check if path is equal to or a child of root."""
        try:
            return path == root or path.is_relative_to(root)
        except AttributeError:
            # Fallback for older python if needed (though we have Python 3.14)
            return path == root or root in path.parents

    def is_text_file(self, path: Path) -> bool:
        """Check if the given path has a supported text file extension."""
        suffix = path.suffix.lower()
        return suffix in SUPPORTED_TEXT_EXTENSIONS

    def read_text(self, target_path: Union[str, Path]) -> str:
        """
        Read text file contents safely from the sandbox.
        Validates path, file type, and byte size.
        """
        safe_path = self.validate_path(target_path, must_exist=True, require_parent_in_sandbox=False)

        if safe_path.is_dir():
            raise IsADirectoryError(f"Expected a file, but found a directory: '{target_path}'")

        if not self.is_text_file(safe_path):
            valid_exts = ", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS))
            raise UnsupportedFileTypeError(
                f"Unsupported file extension '{safe_path.suffix}'. Supported text formats: {valid_exts}"
            )

        file_size = safe_path.stat().st_size
        if file_size > self.max_file_read_size:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum read limit of {self.max_file_read_size} bytes."
            )

        try:
            logger.info("Reading file: %s (%d bytes)", safe_path, file_size)
            return safe_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            logger.warning("Unicode decode error reading '%s': %s", safe_path, str(e))
            raise UnsupportedFileTypeError(
                f"File '{safe_path.name}' is not a valid UTF-8 text file."
            )

    def write_text(self, target_path: Union[str, Path], content: str) -> Tuple[int, bool]:
        """
        Write or overwrite a UTF-8 text file in the sandbox.
        Returns (bytes_written, is_overwrite).
        """
        if not isinstance(content, str):
            raise ValueError(f"Content must be a string, got {type(content).__name__}.")

        safe_path = self.validate_path(target_path, must_exist=False, require_parent_in_sandbox=True)

        if safe_path.exists() and safe_path.is_dir():
            raise IsADirectoryError(f"Cannot overwrite directory with a file: '{target_path}'")

        if not self.is_text_file(safe_path):
            valid_exts = ", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS))
            raise UnsupportedFileTypeError(
                f"Unsupported file extension '{safe_path.suffix}'. Supported text formats: {valid_exts}"
            )

        encoded_data = content.encode("utf-8")
        byte_length = len(encoded_data)

        if byte_length > self.max_file_write_size:
            raise ValueError(
                f"Content size ({byte_length} bytes) exceeds maximum write limit of {self.max_file_write_size} bytes."
            )

        is_overwrite = safe_path.exists()

        # Ensure intermediate directories inside the sandbox are created
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "%s file: %s (%d bytes)",
            "Overwriting" if is_overwrite else "Writing new",
            safe_path,
            byte_length,
        )
        safe_path.write_bytes(encoded_data)
        return byte_length, is_overwrite

    def list_dir(self, target_path: Union[str, Path] = ".") -> List[Dict[str, Any]]:
        """
        List files and directories in the target sandbox directory.
        Returns structured metadata for each entry.
        """
        safe_path = self.validate_path(target_path, must_exist=True, require_parent_in_sandbox=False)

        if not safe_path.is_dir():
            raise NotADirectoryError(f"Expected a directory, but found a file: '{target_path}'")

        entries: List[Dict[str, Any]] = []
        try:
            raw_entries = sorted(safe_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for item in raw_entries[: self.max_directory_entries]:
                is_directory = item.is_dir()
                size_bytes = 0 if is_directory else item.stat().st_size
                rel_path = str(item.relative_to(self.primary_root)).replace("\\", "/")
                entries.append({
                    "name": item.name,
                    "type": "directory" if is_directory else "file",
                    "size_bytes": size_bytes,
                    "relative_path": rel_path,
                })
            logger.info("Listed %d entries from '%s'", len(entries), safe_path)
            return entries
        except PermissionError as e:
            logger.error("Permission denied listing directory '%s': %s", safe_path, str(e))
            raise

    def search(self, query: str, target_path: Union[str, Path] = ".") -> List[Dict[str, Any]]:
        """
        Search for files matching query string within the sandbox directory tree.
        """
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Search query cannot be empty.")

        # Reject path separators in query to prevent directory traversal
        if any(sep in clean_query for sep in ("/", "\\", "..")):
            raise SandboxSecurityError("Search query must be a filename pattern without directory separators.")

        safe_start = self.validate_path(target_path, must_exist=True, require_parent_in_sandbox=False)
        if not safe_start.is_dir():
            raise NotADirectoryError(f"Search root must be a directory: '{target_path}'")

        q_lower = clean_query.lower()
        results: List[Dict[str, Any]] = []

        for root_dir, dirs, files in os.walk(safe_start):
            root_path = Path(root_dir)
            # Verify root remains inside sandbox during walk
            if not any(self._is_within_root(root_path, r) for r in self.roots):
                continue

            for name in sorted(dirs + files):
                if q_lower in name.lower():
                    item_path = root_path / name
                    is_dir = item_path.is_dir()
                    try:
                        size_bytes = 0 if is_dir else item_path.stat().st_size
                        rel_path = str(item_path.relative_to(self.primary_root)).replace("\\", "/")
                        results.append({
                            "name": name,
                            "type": "directory" if is_dir else "file",
                            "size_bytes": size_bytes,
                            "relative_path": rel_path,
                        })
                        if len(results) >= self.max_search_results:
                            logger.info("Search reached maximum limit of %d results", self.max_search_results)
                            return results
                    except Exception as e:
                        logger.debug("Error querying item '%s': %s", item_path, str(e))

        logger.info("Found %d matching items for query '%s'", len(results), clean_query)
        return results

    def create_dir(self, target_path: Union[str, Path]) -> Path:
        """
        Create a directory inside the sandbox.
        """
        safe_path = self.validate_path(target_path, must_exist=False, require_parent_in_sandbox=True)

        if safe_path.exists() and safe_path.is_file():
            raise FileExistsError(f"A file already exists at this path: '{target_path}'")

        safe_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created directory: %s", safe_path)
        return safe_path

    def delete_file(self, target_path: Union[str, Path]) -> None:
        """
        Delete a single file from the sandbox.
        Refuses directories.
        """
        safe_path = self.validate_path(target_path, must_exist=True, require_parent_in_sandbox=False)

        if safe_path.is_dir():
            raise IsADirectoryError(
                f"Cannot delete directory using delete_file. Use delete_directory instead: '{target_path}'"
            )

        safe_path.unlink()
        logger.info("Deleted file: %s", safe_path)

    def delete_dir(self, target_path: Union[str, Path]) -> None:
        """
        Delete an empty directory from the sandbox.
        Refuses files, non-empty directories, and sandbox roots.
        """
        safe_path = self.validate_path(target_path, must_exist=True, require_parent_in_sandbox=False)

        if safe_path.is_file():
            raise NotADirectoryError(
                f"Cannot delete file using delete_directory. Use delete_file instead: '{target_path}'"
            )

        if any(safe_path == r for r in self.roots):
            raise SandboxSecurityError("Cannot delete sandbox root directory.")

        # Check if empty
        has_children = any(safe_path.iterdir())
        if has_children:
            raise OSError(
                f"Directory '{target_path}' is not empty. Recursive deletion is strictly prohibited."
            )

        safe_path.rmdir()
        logger.info("Deleted empty directory: %s", safe_path)


@lru_cache(maxsize=1)
def get_filesystem_sandbox() -> FilesystemSandbox:
    """Return singleton instance of FilesystemSandbox."""
    return FilesystemSandbox()
