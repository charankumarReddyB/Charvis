"""
Unit and integration tests for CHARVIS Filesystem Tools with ToolRouter, SafetyManager, and AIBrain.
Uses temporary directories (tmp_path) to ensure safe execution without modifying user data.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from filesystem.sandbox import FilesystemSandbox
from tools.filesystem import (
    CreateDirectoryTool,
    DeleteDirectoryTool,
    DeleteFileTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from tools.registry import ToolRegistry
from tools.router import ToolRouter


class MockScriptedProvider(BaseLLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)

    @property
    def provider_name(self):
        return "mock_scripted"

    @property
    def model_name(self):
        return "test-model"

    def generate_response(self, messages, tools=None):
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Done", model="test-model")


@pytest.fixture
def sandbox_env(tmp_path):
    """Fixture providing an isolated FilesystemSandbox inside tmp_path."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return FilesystemSandbox(root_dirs=[workspace])


def test_read_file_tool(sandbox_env):
    """Verify ReadFileTool execution, risk level, and error handling."""
    tool = ReadFileTool(sandbox=sandbox_env)
    assert tool.name == "read_file"
    assert tool.risk_level == RiskLevel.SAFE

    # Read existing file
    sandbox_env.write_text("test.txt", "Sample file content")
    res = tool.execute(path="test.txt")
    assert res["success"] is True
    assert res["content"] == "Sample file content"
    assert res["size_bytes"] == len("Sample file content")

    # Read missing file
    res_missing = tool.execute(path="missing.txt")
    assert res_missing["success"] is False
    assert res_missing["error"] == "FileNotFoundError"

    # Read directory as file
    sandbox_env.create_dir("test_dir")
    res_dir = tool.execute(path="test_dir")
    assert res_dir["success"] is False
    assert res_dir["error"] == "IsADirectoryError"


def test_write_file_tool_and_confirmation(sandbox_env):
    """Verify WriteFileTool execution, confirmation preview, and safety policies."""
    tool = WriteFileTool(sandbox=sandbox_env)
    assert tool.name == "write_file"
    assert tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED

    # 1. Check confirmation message for new file
    msg_new = tool.get_confirmation_message({"path": "doc.md", "content": "# Heading\nHello world!"})
    assert "CREATE new file" in msg_new
    assert "'doc.md'" in msg_new
    assert "Heading" in msg_new

    # 2. Write new file
    res_write = tool.execute(path="doc.md", content="# Heading\nHello world!")
    assert res_write["success"] is True
    assert res_write["is_overwrite"] is False

    # 3. Check confirmation message for overwrite
    msg_over = tool.get_confirmation_message({"path": "doc.md", "content": "Overwriting content..."})
    assert "OVERWRITE existing file" in msg_over

    # 4. Overwrite file
    res_over = tool.execute(path="doc.md", content="Overwriting content...")
    assert res_over["success"] is True
    assert res_over["is_overwrite"] is True


def test_list_and_search_tools(sandbox_env):
    """Verify ListDirectoryTool and SearchFilesTool metadata and outputs."""
    sandbox_env.write_text("file_a.txt", "AAA")
    sandbox_env.write_text("file_b.json", "{}")
    sandbox_env.create_dir("archive")

    list_tool = ListDirectoryTool(sandbox=sandbox_env)
    assert list_tool.risk_level == RiskLevel.SAFE
    res_list = list_tool.execute(path=".")
    assert res_list["success"] is True
    assert res_list["count"] == 3

    search_tool = SearchFilesTool(sandbox=sandbox_env)
    assert search_tool.risk_level == RiskLevel.SAFE
    res_search = search_tool.execute(query="file_")
    assert res_search["success"] is True
    assert res_search["count"] == 2
    matched_names = {m["name"] for m in res_search["matches"]}
    assert matched_names == {"file_a.txt", "file_b.json"}


def test_create_and_delete_tools(sandbox_env):
    """Verify directory creation and deletion tools with destructive warnings."""
    create_dir_tool = CreateDirectoryTool(sandbox=sandbox_env)
    assert create_dir_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    res_cd = create_dir_tool.execute(path="projects/demo")
    assert res_cd["success"] is True

    # Delete file
    sandbox_env.write_text("projects/demo/temp.log", "data")
    del_file_tool = DeleteFileTool(sandbox=sandbox_env)
    assert del_file_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    msg_del_f = del_file_tool.get_confirmation_message({"path": "projects/demo/temp.log"})
    assert "DESTRUCTIVE ACTION" in msg_del_f

    res_del_f = del_file_tool.execute(path="projects/demo/temp.log")
    assert res_del_f["success"] is True

    # Delete directory
    del_dir_tool = DeleteDirectoryTool(sandbox=sandbox_env)
    assert del_dir_tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    msg_del_d = del_dir_tool.get_confirmation_message({"path": "projects/demo"})
    assert "DESTRUCTIVE ACTION" in msg_del_d

    # Delete empty directory
    res_del_d = del_dir_tool.execute(path="projects/demo")
    assert res_del_d["success"] is True


def test_router_enforces_safety_on_file_write_and_delete(sandbox_env):
    """Verify ToolRouter requires confirmation for write_file and delete_file."""
    registry = ToolRegistry()
    safety = SafetyManager()
    router = ToolRouter(registry, safety)

    write_tool = WriteFileTool(sandbox=sandbox_env)
    read_tool = ReadFileTool(sandbox=sandbox_env)
    registry.register(write_tool)
    registry.register(read_tool)

    # 1. Deny write_file
    res_denied = router.execute_tool(
        "write_file",
        {"path": "secret.txt", "content": "data"},
        confirmation_callback=lambda *_: False,
    )
    assert res_denied.success is False
    assert "User did not authorize" in str(res_denied.error)

    # 2. Approve write_file
    res_approved = router.execute_tool(
        "write_file",
        {"path": "secret.txt", "content": "data"},
        confirmation_callback=lambda *_: True,
    )
    assert res_approved.success is True

    # 3. read_file does not require confirmation
    res_read = router.execute_tool("read_file", {"path": "secret.txt"})
    assert res_read.success is True
    assert res_read.data["content"] == "data"


def test_registry_contains_all_eighteen_tools_by_default():
    """Verify that AIBrain initializes with all 18 tools across Phases 3, 4, 5, and 6."""
    brain = AIBrain(provider=MockScriptedProvider([]))
    tools = brain.registry.list_tools()
    tool_names = {t.name for t in tools}

    assert len(tool_names) >= 18
    expected = {
        # Phase 3
        "calculator",
        # Phase 4
        "open_application",
        "close_application",
        "get_application_status",
        # Phase 5
        "type_text",
        "press_key",
        "hotkey",
        "move_mouse",
        "click",
        "double_click",
        "scroll",
        # Phase 6
        "read_file",
        "write_file",
        "list_directory",
        "search_files",
        "create_directory",
        "delete_file",
        "delete_directory",
    }
    assert expected.issubset(tool_names)


def test_brain_end_to_end_filesystem_flow(sandbox_env):
    """Verify cognitive loop for writing a file and reading it back."""
    registry = ToolRegistry()
    registry.register(WriteFileTool(sandbox=sandbox_env))
    registry.register(ReadFileTool(sandbox=sandbox_env))

    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="call_w", name="write_file", arguments={"path": "hello.txt", "content": "Hello World!"})],
            model="test-model",
        ),
        LLMResponse(
            content="File written. Now reading it back.",
            tool_calls=[ToolCall(id="call_r", name="read_file", arguments={"path": "hello.txt"})],
            model="test-model",
        ),
        LLMResponse(content="The file contains: Hello World!", model="test-model"),
    ]

    provider = MockScriptedProvider(responses)
    brain = AIBrain(provider=provider, registry=registry)

    reply = brain.process_user_message(
        "Write Hello World to hello.txt and read it",
        confirmation_callback=lambda *_: True,
    )

    assert reply == "The file contains: Hello World!"
    assert sandbox_env.read_text("hello.txt") == "Hello World!"
