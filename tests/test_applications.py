"""
Unit tests for Windows application control tools, whitelist registry, and process operations.
All tests use mocking and do not launch or terminate real system applications.
"""

import os
from unittest.mock import MagicMock, call, patch
import pytest

from core.brain import AIBrain
from core.providers.base import BaseLLMProvider, LLMMessage, LLMResponse, ToolCall
from core.safety import RiskLevel, SafetyManager
from main import cli_confirmation_callback
from tools.applications import (
    AppDefinition,
    ApplicationRegistry,
    CloseApplicationTool,
    GetApplicationStatusTool,
    OpenApplicationTool,
    get_application_registry,
    get_protected_pids,
)
from tools.registry import ToolRegistry
from tools.router import ToolRouter
from tools.schemas import ToolSchema


def test_application_registry_whitelist_and_aliases():
    """Verify registry resolves known applications and aliases."""
    reg = ApplicationRegistry()

    # Notepad
    app_np = reg.resolve("notepad")
    assert app_np is not None
    assert app_np.name == "Notepad"
    assert reg.resolve("Notepad") is app_np
    assert reg.resolve("TEXT EDITOR") is app_np
    assert reg.resolve("notepad.exe") is app_np

    # Chrome
    app_chrome = reg.resolve("chrome")
    assert app_chrome is not None
    assert app_chrome.name == "Google Chrome"
    assert reg.resolve("google chrome") is app_chrome

    # VS Code
    app_code = reg.resolve("vscode")
    assert app_code is not None
    assert app_code.name == "Visual Studio Code"
    assert reg.resolve("vs code") is app_code
    assert reg.resolve("code") is app_code

    # Calculator
    app_calc = reg.resolve("calc")
    assert app_calc is not None
    assert app_calc.name == "Calculator"
    assert reg.resolve("calculator") is app_calc


def test_application_registry_rejects_unknown():
    """Verify unknown applications return None."""
    reg = ApplicationRegistry()
    assert reg.resolve("random_game") is None
    assert reg.resolve("unknown_tool_xyz") is None


def test_application_registry_rejects_arbitrary_paths():
    """Verify security rejection of arbitrary paths, drive letters, and traversal."""
    reg = ApplicationRegistry()

    assert reg.resolve(r"C:\Windows\System32\cmd.exe") is None
    assert reg.resolve("/bin/sh") is None
    assert reg.resolve(r"..\..\malicious.exe") is None
    assert reg.resolve("calc:something") is None
    assert reg.resolve("%windir%") is None


def test_open_application_tool_metadata():
    """Verify OpenApplicationTool metadata and schema."""
    tool = OpenApplicationTool()
    assert tool.name == "open_application"
    assert tool.risk_level == RiskLevel.SAFE
    assert len(tool.schema.parameters) == 1
    assert tool.schema.parameters[0].name == "application_name"


def test_open_application_success():
    """Verify successful application launch with mocked launch method."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Notepad"
    mock_app.is_available.return_value = True
    mock_app.launch.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool = OpenApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="notepad")

    assert result["success"] is True
    assert result["application"] == "Notepad"
    assert "launched successfully" in result["message"]
    mock_app.launch.assert_called_once()


def test_open_application_unavailable():
    """Verify behavior when application is not installed on system."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Google Chrome"
    mock_app.is_available.return_value = False
    mock_reg.resolve.return_value = mock_app

    tool = OpenApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="chrome")

    assert result["success"] is False
    assert "not installed or not available" in result["message"]
    mock_app.launch.assert_not_called()


def test_open_application_unrecognized():
    """Verify behavior when application name is not recognized."""
    tool = OpenApplicationTool()
    result = tool.execute(application_name="nonexistent_software")

    assert result["success"] is False
    assert "not in the list of whitelisted applications" in result["message"]


def test_open_application_launch_failure():
    """Verify launch failure returns clean error message."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Paint"
    mock_app.is_available.return_value = True
    mock_app.launch.return_value = False
    mock_reg.resolve.return_value = mock_app

    tool = OpenApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="paint")

    assert result["success"] is False
    assert "Failed to launch" in result["message"]


def test_close_application_tool_metadata():
    """Verify CloseApplicationTool metadata, risk level, and schema."""
    tool = CloseApplicationTool()
    assert tool.name == "close_application"
    assert tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED
    assert len(tool.schema.parameters) == 1


def test_close_application_not_running():
    """Verify close when application is not currently running."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Notepad"
    mock_app.is_running.return_value = False
    mock_reg.resolve.return_value = mock_app

    tool = CloseApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="notepad")

    assert result["success"] is True
    assert "not currently running" in result["message"]
    mock_app.close.assert_not_called()


def test_close_application_running_and_closed():
    """Verify successful close when application is running."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Notepad"
    mock_app.is_running.return_value = True
    mock_app.close.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool = CloseApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="notepad")

    assert result["success"] is True
    assert "was closed successfully" in result["message"]
    mock_app.close.assert_called_once()


def test_get_application_status_running():
    """Verify status reports correctly when running."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Calculator"
    mock_app.is_running.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool = GetApplicationStatusTool(registry=mock_reg)
    result = tool.execute(application_name="calc")

    assert result["success"] is True
    assert result["running"] is True
    assert "is currently running" in result["message"]


def test_get_application_status_not_running():
    """Verify status reports correctly when not running."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Calculator"
    mock_app.is_running.return_value = False
    mock_reg.resolve.return_value = mock_app

    tool = GetApplicationStatusTool(registry=mock_reg)
    result = tool.execute(application_name="calc")

    assert result["success"] is True
    assert result["running"] is False
    assert "is currently not running" in result["message"]


def test_tool_router_open_and_close_integration():
    """Verify ToolRouter enforces safety policies on open vs close application."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Notepad"
    mock_app.is_available.return_value = True
    mock_app.launch.return_value = True
    mock_app.is_running.return_value = True
    mock_app.close.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool_registry = ToolRegistry()
    tool_registry.register(OpenApplicationTool(registry=mock_reg))
    tool_registry.register(CloseApplicationTool(registry=mock_reg))

    router = ToolRouter(tool_registry, SafetyManager())

    # 1. Open application is SAFE: executes without callback
    open_res = router.execute_tool("open_application", {"application_name": "notepad"})
    assert open_res.success is True
    assert "launched successfully" in str(open_res.data)

    # 2. Close application requires CONFIRMATION: fails without callback
    close_denied_res = router.execute_tool("close_application", {"application_name": "notepad"})
    assert close_denied_res.success is False
    assert "User did not authorize" in close_denied_res.error

    # 3. Close application with approval callback succeeds
    close_approved_res = router.execute_tool(
        "close_application",
        {"application_name": "notepad"},
        confirmation_callback=lambda name, args, risk: True,
    )
    assert close_approved_res.success is True
    assert "was closed successfully" in str(close_approved_res.data)


class ScriptedAppProvider(BaseLLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)

    @property
    def provider_name(self):
        return "scripted_app"

    @property
    def model_name(self):
        return "test-model"

    def generate_response(self, messages, tools=None):
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Done", model="test-model")


def test_brain_open_application_tool_call_flow():
    """Verify full end-to-end cognitive loop for open_application."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "Notepad"
    mock_app.is_available.return_value = True
    mock_app.launch.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool_registry = ToolRegistry()
    tool_registry.register(OpenApplicationTool(registry=mock_reg))

    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="call_open_1", name="open_application", arguments={"application_name": "notepad"})],
            model="test-model",
        ),
        LLMResponse(content="Notepad is now open for you.", model="test-model"),
    ]
    provider = ScriptedAppProvider(responses)
    brain = AIBrain(provider=provider, registry=tool_registry)

    reply = brain.process_user_message("Open Notepad")
    assert reply == "Notepad is now open for you."
    mock_app.launch.assert_called_once()


def test_get_protected_pids():
    """Verify that current process and parent process are included in protected PIDs."""
    pids = get_protected_pids()
    assert os.getpid() in pids
    if hasattr(os, "getppid") and os.getppid() > 0:
        assert os.getppid() in pids


def test_close_warning_messages_multi_process():
    """Verify descriptive warnings for multi-process apps (Chrome, VS Code, Explorer, PowerShell)."""
    reg = ApplicationRegistry()

    # Chrome
    chrome = reg.resolve("chrome")
    assert chrome is not None
    with patch.object(chrome, "get_running_pids", return_value=[101, 102, 103, 104, 105, 106]):
        msg = chrome.get_close_warning_message()
        assert "Google Chrome" in msg
        assert "6 Chrome processes" in msg
        assert "close all Chrome windows" in msg

    # VS Code
    vscode = reg.resolve("vscode")
    assert vscode is not None
    with patch.object(vscode, "get_running_pids", return_value=[201, 202, 203]):
        msg = vscode.get_close_warning_message()
        assert "Visual Studio Code" in msg
        assert "3 processes" in msg
        assert "all VS Code windows" in msg

    # File Explorer
    explorer = reg.resolve("explorer")
    assert explorer is not None
    msg_exp = explorer.get_close_warning_message()
    assert "File Explorer" in msg_exp
    assert "Windows Explorer shell" in msg_exp

    # PowerShell with protected host PID
    powershell = reg.resolve("powershell")
    assert powershell is not None
    host_pid = os.getppid()
    with patch.object(powershell, "get_running_pids", return_value=[host_pid, 401]):
        msg_ps = powershell.get_close_warning_message()
        assert "PowerShell" in msg_ps
        assert "1 detected external process" in msg_ps
        assert "will not terminate its own hosting shell" in msg_ps


def test_close_application_refuses_self_termination():
    """Verify CHARVIS refuses to terminate when the only running process is its own shell."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "PowerShell"
    mock_app.is_running.return_value = True
    mock_app.get_running_pids.return_value = [os.getppid()]
    mock_app.get_terminatable_pids.return_value = []
    mock_reg.resolve.return_value = mock_app

    tool = CloseApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="powershell")

    assert result["success"] is False
    assert "protected from self-termination" in result["message"]
    mock_app.close.assert_not_called()


def test_close_application_filters_protected_pids_and_closes_external():
    """Verify external instances are terminated while protected parent shell is preserved."""
    mock_reg = MagicMock(spec=ApplicationRegistry)
    mock_app = MagicMock(spec=AppDefinition)
    mock_app.name = "PowerShell"
    mock_app.is_running.return_value = True
    mock_app.get_running_pids.return_value = [os.getppid(), 5555]
    mock_app.get_terminatable_pids.return_value = [5555]
    mock_app.close.return_value = True
    mock_reg.resolve.return_value = mock_app

    tool = CloseApplicationTool(registry=mock_reg)
    result = tool.execute(application_name="powershell")

    assert result["success"] is True
    assert "was closed successfully" in result["message"]
    mock_app.close.assert_called_once_with([5555])


def test_app_definition_close_targets_pids_not_im():
    """Verify AppDefinition.close issues 'taskkill /PID <pid>' and NOT 'taskkill /IM'."""
    app = AppDefinition(
        name="MockApp",
        aliases={"mock"},
        process_names=["mockapp.exe"],
        default_command="mockapp.exe",
    )

    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = MagicMock(returncode=0)
        success = app.close(target_pids=[1234, 5678])

        assert success is True
        assert mock_subproc.call_count == 2
        calls = [
            call(["taskkill", "/PID", "1234"], capture_output=True, text=True, shell=False, check=False),
            call(["taskkill", "/PID", "5678"], capture_output=True, text=True, shell=False, check=False),
        ]
        mock_subproc.assert_has_calls(calls)


def test_app_definition_get_running_pids_csv_parsing():
    """Verify AppDefinition.get_running_pids parses CSV output from tasklist correctly."""
    app = AppDefinition(
        name="TestCalc",
        aliases={"calc"},
        process_names=["calc.exe"],
        default_command="calc.exe",
    )

    fake_csv = '"calc.exe","4321","Console","1","14,200 K"\n"calc.exe","8765","Console","1","12,100 K"\n'
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = MagicMock(stdout=fake_csv)
        pids = app.get_running_pids()

        assert pids == [4321, 8765]


def test_router_passes_custom_confirmation_message():
    """Verify ToolRouter extracts custom confirmation message from tool and passes to callback."""
    tool_registry = ToolRegistry()
    safety_manager = SafetyManager()
    router = ToolRouter(registry=tool_registry, safety_manager=safety_manager)

    reg = ApplicationRegistry()
    chrome = reg.resolve("chrome")
    tool = CloseApplicationTool(registry=reg)
    tool_registry.register(tool)

    received_custom_messages = []

    def mock_callback(tool_name, arguments, risk_level, custom_message=None):
        received_custom_messages.append(custom_message)
        return True

    with patch.object(chrome, "get_running_pids", return_value=[111, 222]):
        with patch.object(chrome, "close", return_value=True):
            res = router.execute_tool(
                "close_application",
                {"application_name": "chrome"},
                confirmation_callback=mock_callback,
            )
            assert res.success is True
            assert len(received_custom_messages) == 1
            assert "Google Chrome" in received_custom_messages[0]
            assert "2 Chrome processes" in received_custom_messages[0]


def test_cli_confirmation_callback_displays_custom_message():
    """Verify cli_confirmation_callback displays Notice when custom_message is provided."""
    with patch("builtins.input", return_value="y") as mock_input:
        confirmed = cli_confirmation_callback(
            tool_name="close_application",
            arguments={"application_name": "chrome"},
            risk_level=RiskLevel.CONFIRMATION_REQUIRED,
            custom_message="Closing Google Chrome will terminate 5 processes.",
        )
        assert confirmed is True
        prompt_shown = mock_input.call_args[0][0]
        assert "Notice    : Closing Google Chrome will terminate 5 processes." in prompt_shown

