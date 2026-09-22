"""
Unit tests for CHARVIS FilesystemSandbox and path containment security.
All tests use temporary directories (tmp_path) to ensure isolated, safe execution.
"""

from pathlib import Path
import pytest

from filesystem.sandbox import (
    FilesystemSandbox,
    SandboxSecurityError,
    UnsupportedFileTypeError,
)


def test_sandbox_path_validation_inside_sandbox(tmp_path):
    """Verify that relative and absolute paths inside sandbox are accepted."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir])

    # Simple relative path
    p1 = sandbox.validate_path("notes.txt")
    assert p1 == (sandbox_dir / "notes.txt").resolve()

    # Nested relative path
    p2 = sandbox.validate_path("docs/project/report.md")
    assert p2 == (sandbox_dir / "docs/project/report.md").resolve()

    # Absolute path directly inside sandbox
    abs_inside = (sandbox_dir / "data.json").resolve()
    p3 = sandbox.validate_path(abs_inside)
    assert p3 == abs_inside


def test_sandbox_path_validation_rejects_parent_traversal(tmp_path):
    """Verify that ../ attempts escaping sandbox root are rejected."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir])

    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path("../outside.txt")

    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path("sub/../../escape.txt")

    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path("../../../../../Windows/System32/cmd.exe")


def test_sandbox_path_validation_rejects_absolute_paths_outside(tmp_path):
    """Verify that absolute paths outside sandbox are rejected."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    outside_dir = tmp_path / "secret_system"
    outside_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir])

    # Pointing to outside_dir
    outside_file = outside_dir / "passwords.txt"
    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path(outside_file)

    # Windows root / system path
    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path(r"C:\Windows\System32\notepad.exe")


def test_sandbox_path_validation_rejects_null_byte_and_empty(tmp_path):
    """Verify null byte attacks and empty strings are rejected."""
    sandbox = FilesystemSandbox(root_dirs=[tmp_path])

    with pytest.raises(ValueError, match="cannot be empty"):
        sandbox.validate_path("")

    with pytest.raises(ValueError, match="cannot be empty"):
        sandbox.validate_path("   ")

    with pytest.raises(SandboxSecurityError, match="Null byte detected"):
        sandbox.validate_path("notes\0.txt")


def test_sandbox_symlink_escape_rejection(tmp_path):
    """Verify that symlinks pointing outside the sandbox are rejected."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    outside_target = tmp_path / "external_target.txt"
    outside_target.write_text("outside data", encoding="utf-8")

    link_path = sandbox_dir / "evil_symlink.txt"
    try:
        link_path.symlink_to(outside_target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not permitted in current OS user privilege context.")

    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir])

    with pytest.raises(SandboxSecurityError, match="outside the allowed sandbox"):
        sandbox.validate_path("evil_symlink.txt", must_exist=True)


def test_is_text_file(tmp_path):
    """Verify text file extension whitelist."""
    sandbox = FilesystemSandbox(root_dirs=[tmp_path])

    # Valid extensions
    for ext in [".txt", ".md", ".csv", ".json", ".log", ".py", ".html", ".css", ".js", ".yaml"]:
        assert sandbox.is_text_file(Path(f"file{ext}")) is True
        assert sandbox.is_text_file(Path(f"FILE{ext.upper()}")) is True

    # Invalid / binary extensions
    for ext in [".exe", ".bin", ".png", ".jpg", ".zip", ".tar", ".dll", ".so", ""]:
        assert sandbox.is_text_file(Path(f"file{ext}")) is False


def test_read_text_success_and_failures(tmp_path):
    """Verify reading text files within sandbox, including edge cases."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir], max_file_read_size=50)

    # Valid file read
    test_file = sandbox_dir / "notes.txt"
    test_file.write_text("Hello CHARVIS", encoding="utf-8")
    content = sandbox.read_text("notes.txt")
    assert content == "Hello CHARVIS"

    # Missing file
    with pytest.raises(FileNotFoundError):
        sandbox.read_text("nonexistent.txt")

    # Directory target rejected
    sub_dir = sandbox_dir / "subfolder"
    sub_dir.mkdir()
    with pytest.raises(IsADirectoryError):
        sandbox.read_text("subfolder")

    # Unsupported file type rejected
    bin_file = sandbox_dir / "image.png"
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedFileTypeError, match="Unsupported file extension"):
        sandbox.read_text("image.png")

    # Size limit exceeded
    big_file = sandbox_dir / "big.txt"
    big_file.write_text("A" * 100, encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds maximum read limit"):
        sandbox.read_text("big.txt")


def test_write_text_success_and_failures(tmp_path):
    """Verify creating and overwriting text files within sandbox."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir], max_file_write_size=100)

    # 1. Create new file
    bytes_written, is_overwrite = sandbox.write_text("new_note.md", "# CHARVIS Notes")
    assert bytes_written > 0
    assert is_overwrite is False
    assert (sandbox_dir / "new_note.md").read_text(encoding="utf-8") == "# CHARVIS Notes"

    # 2. Overwrite file
    bytes_written2, is_overwrite2 = sandbox.write_text("new_note.md", "# Updated Notes")
    assert is_overwrite2 is True
    assert (sandbox_dir / "new_note.md").read_text(encoding="utf-8") == "# Updated Notes"

    # 3. Create file in subfolder (auto parent creation)
    bytes_written3, is_overwrite3 = sandbox.write_text("docs/sub/report.json", '{"status": "ok"}')
    assert is_overwrite3 is False
    assert (sandbox_dir / "docs" / "sub" / "report.json").exists()

    # 4. Overwrite directory rejected
    sub_dir = sandbox_dir / "demo_folder"
    sub_dir.mkdir()
    with pytest.raises(IsADirectoryError):
        sandbox.write_text("demo_folder", "content")

    # 5. Unsupported extension rejected
    with pytest.raises(UnsupportedFileTypeError):
        sandbox.write_text("bad.exe", "content")

    # 6. Content size exceeded
    with pytest.raises(ValueError, match="exceeds maximum write limit"):
        sandbox.write_text("toolarge.txt", "X" * 150)


def test_list_dir(tmp_path):
    """Verify directory listing with structured output."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    (sandbox_dir / "file1.txt").write_text("file 1", encoding="utf-8")
    (sandbox_dir / "file2.json").write_text("{}", encoding="utf-8")
    (sandbox_dir / "folderA").mkdir()
    (sandbox_dir / "folderB").mkdir()

    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir], max_directory_entries=10)
    entries = sandbox.list_dir(".")

    assert len(entries) == 4
    types = {e["name"]: e["type"] for e in entries}
    assert types["folderA"] == "directory"
    assert types["folderB"] == "directory"
    assert types["file1.txt"] == "file"
    assert types["file2.json"] == "file"

    # List file as directory rejected
    with pytest.raises(NotADirectoryError):
        sandbox.list_dir("file1.txt")


def test_search_files(tmp_path):
    """Verify recursive file searching within sandbox."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    (sandbox_dir / "test_a.txt").write_text("a", encoding="utf-8")
    sub = sandbox_dir / "sub"
    sub.mkdir()
    (sub / "test_b.md").write_text("b", encoding="utf-8")
    (sub / "other.log").write_text("c", encoding="utf-8")

    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir], max_search_results=10)

    # Search substring "test"
    matches = sandbox.search("test")
    names = [m["name"] for m in matches]
    assert "test_a.txt" in names
    assert "test_b.md" in names
    assert "other.log" not in names

    # Traversal characters in search query rejected
    with pytest.raises(SandboxSecurityError, match="Search query must be a filename pattern"):
        sandbox.search("../secret")


def test_create_and_delete_directory(tmp_path):
    """Verify creating and deleting directories, including empty checks."""
    sandbox_dir = tmp_path / "workspace"
    sandbox_dir.mkdir()
    sandbox = FilesystemSandbox(root_dirs=[sandbox_dir])

    # Create directory
    dir_path = sandbox.create_dir("reports/2026")
    assert dir_path.exists() and dir_path.is_dir()

    # Deleting sandbox root rejected
    with pytest.raises(SandboxSecurityError, match="Cannot delete sandbox root directory"):
        sandbox.delete_dir(".")

    # Deleting non-empty directory rejected
    (dir_path / "dummy.txt").write_text("hello", encoding="utf-8")
    with pytest.raises(OSError, match="not empty"):
        sandbox.delete_dir("reports/2026")

    # Delete file first, then delete empty directory
    sandbox.delete_file("reports/2026/dummy.txt")
    assert not (dir_path / "dummy.txt").exists()

    sandbox.delete_dir("reports/2026")
    assert not dir_path.exists()
