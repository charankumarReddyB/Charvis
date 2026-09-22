"""
Windows Application Management for CHARVIS.
Provides controlled, whitelisted launching, status checking, and closing of Windows applications.
Prevents arbitrary executable execution and enforces confirmation for application termination.
"""

import csv
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set

from core.safety import RiskLevel
from logger import get_logger
from tools.base import BaseTool
from tools.schemas import ToolParameter, ToolSchema

logger = get_logger("CHARVIS.Applications")


def get_protected_pids() -> Set[int]:
    """Return set of PIDs that CHARVIS must never terminate (itself and host terminal shell)."""
    protected = {os.getpid()}
    try:
        ppid = os.getppid()
        if ppid > 0:
            protected.add(ppid)
    except Exception:
        pass
    return protected


@dataclass
class AppDefinition:
    """Metadata and operational handlers for a whitelisted Windows application."""
    name: str
    aliases: Set[str]
    process_names: List[str]
    default_command: str
    search_paths: List[Path] = field(default_factory=list)

    def get_executable_path(self) -> Optional[str]:
        """
        Locate the verified executable path on the Windows system.
        Checks explicit search paths, System32, and PATH.
        """
        # 1. Check specified search paths first
        for path in self.search_paths:
            if path.exists() and path.is_file():
                return str(path)

        # 2. Check system PATH
        resolved = shutil.which(self.default_command)
        if resolved:
            return resolved

        # 3. Check Windows System32 directory explicitly
        system32 = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / self.default_command
        if system32.exists():
            return str(system32)

        return None

    def is_available(self) -> bool:
        """Check whether the application is detected and accessible on this system."""
        return self.get_executable_path() is not None

    def get_running_pids(self) -> List[int]:
        """
        Query Windows tasklist utility safely using shell=False.
        Returns a sorted list of unique active PIDs matching any of this app's process names.
        """
        pids: Set[int] = set()
        for proc in self.process_names:
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    shell=False,
                    check=False,
                )
                output = result.stdout.strip()
                if output and "no tasks are running" not in output.lower():
                    reader = csv.reader(output.splitlines())
                    for row in reader:
                        if len(row) >= 2 and row[0].strip().lower() == proc.lower():
                            try:
                                pid = int(row[1].strip())
                                pids.add(pid)
                            except ValueError:
                                pass
            except Exception as e:
                logger.error("Error detecting process '%s': %s", proc, str(e))
        return sorted(list(pids))

    def is_running(self) -> bool:
        """Check whether the application currently has an active process running."""
        return len(self.get_running_pids()) > 0

    def get_terminatable_pids(self) -> List[int]:
        """
        Return the list of active PIDs for this app excluding protected PIDs
        (CHARVIS itself and the parent terminal shell).
        """
        protected = get_protected_pids()
        return [pid for pid in self.get_running_pids() if pid not in protected]

    def get_close_warning_message(self) -> str:
        """
        Generate an accurate, transparent confirmation message describing the exact impact
        of closing this application, including process counts and multi-process consequences.
        """
        running_pids = self.get_running_pids()
        terminatable = self.get_terminatable_pids()
        count = len(terminatable)
        total_count = len(running_pids)
        protected_count = total_count - count

        if self.name == "Google Chrome":
            return (
                f"Closing Google Chrome will terminate its currently detected {total_count} Chrome "
                f"processes (tabs, extensions, background processes). This will close all Chrome windows."
            )
        elif self.name == "Microsoft Edge":
            return (
                f"Closing Microsoft Edge will terminate its currently detected {total_count} Edge "
                f"processes (tabs, extensions, background processes). This will close all Edge windows."
            )
        elif self.name == "Visual Studio Code":
            return (
                f"Closing Visual Studio Code will terminate its currently detected {total_count} processes. "
                f"This may close all VS Code windows, editor tabs, and background language servers/tasks."
            )
        elif self.name == "File Explorer":
            return (
                "Closing File Explorer may close all open folder windows and restart or interrupt "
                "the Windows Explorer shell (taskbar/desktop)."
            )
        elif self.name in ("PowerShell", "Command Prompt"):
            if protected_count > 0:
                return (
                    f"Closing {self.name} will terminate {count} detected external process(es). "
                    f"Note: CHARVIS will not terminate its own hosting shell process (PID {os.getppid()})."
                )
            else:
                return f"Closing {self.name} will terminate {count} detected process(es)."
        else:
            if count > 1:
                return (
                    f"Closing {self.name} will terminate its currently detected {count} running processes. "
                    f"This operates at the application level and may close all associated windows."
                )
            elif count == 1:
                return f"Closing {self.name} will terminate its 1 detected running process."
            else:
                return f"Closing {self.name} requested, but no terminatable processes were found."

    def launch(self) -> bool:
        """
        Launch the application safely using subprocess.Popen with shell=False.
        Returns True if process started, False otherwise.
        """
        exe_path = self.get_executable_path()
        if not exe_path:
            logger.warning("Cannot launch '%s': executable not found on system.", self.name)
            return False

        try:
            logger.info("Launching '%s' from path: %s", self.name, exe_path)
            subprocess.Popen([exe_path], shell=False)
            return True
        except Exception as e:
            logger.error("Failed to launch '%s': %s", self.name, str(e))
            return False

    def close(self, target_pids: Optional[List[int]] = None) -> bool:
        """
        Gracefully terminate running instances of this application using taskkill with shell=False.
        Targets specific safe PIDs using '/PID <pid>' to prevent terminating protected processes.
        Sends a standard WM_CLOSE signal without /F to allow graceful saving.
        """
        if target_pids is None:
            target_pids = self.get_terminatable_pids()

        if not target_pids:
            logger.info("No terminatable processes found for '%s'.", self.name)
            return True

        closed_any = False
        for pid in target_pids:
            try:
                logger.info("Sending graceful termination signal to PID %d (%s)", pid, self.name)
                res = subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    shell=False,
                    check=False,
                )
                if res.returncode == 0:
                    closed_any = True
                else:
                    logger.warning("taskkill /PID %d returned %d: %s", pid, res.returncode, res.stderr.strip())
            except Exception as e:
                logger.error("Error terminating PID %d (%s): %s", pid, self.name, str(e))

        return closed_any


class ApplicationRegistry:
    """Registry of verified, whitelisted Windows applications."""

    def __init__(self) -> None:
        self._apps: Dict[str, AppDefinition] = {}
        self._alias_map: Dict[str, str] = {}
        self._initialize_whitelist()

    def _initialize_whitelist(self) -> None:
        """Populate the registry with common, trusted Windows applications."""
        prog_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        prog_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        local_appdata = Path(os.environ.get("LocalAppData", "C:\\Users\\Default\\AppData\\Local"))

        standard_apps = [
            AppDefinition(
                name="Notepad",
                aliases={"notepad", "text editor", "notes"},
                process_names=["notepad.exe", "Notepad.exe"],
                default_command="notepad.exe",
            ),
            AppDefinition(
                name="Calculator",
                aliases={"calculator", "calc"},
                process_names=["calc.exe", "CalculatorApp.exe"],
                default_command="calc.exe",
            ),
            AppDefinition(
                name="Paint",
                aliases={"paint", "mspaint"},
                process_names=["mspaint.exe"],
                default_command="mspaint.exe",
            ),
            AppDefinition(
                name="File Explorer",
                aliases={"explorer", "file explorer", "windows explorer", "my computer"},
                process_names=["explorer.exe"],
                default_command="explorer.exe",
            ),
            AppDefinition(
                name="Command Prompt",
                aliases={"cmd", "command prompt", "terminal"},
                process_names=["cmd.exe"],
                default_command="cmd.exe",
            ),
            AppDefinition(
                name="PowerShell",
                aliases={"powershell", "windows powershell"},
                process_names=["powershell.exe"],
                default_command="powershell.exe",
            ),
            AppDefinition(
                name="Microsoft Edge",
                aliases={"edge", "microsoft edge", "msedge"},
                process_names=["msedge.exe"],
                default_command="msedge.exe",
                search_paths=[
                    prog_files / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                    prog_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                ],
            ),
            AppDefinition(
                name="Google Chrome",
                aliases={"chrome", "google chrome"},
                process_names=["chrome.exe"],
                default_command="chrome.exe",
                search_paths=[
                    prog_files / "Google" / "Chrome" / "Application" / "chrome.exe",
                    prog_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
                    local_appdata / "Google" / "Chrome" / "Application" / "chrome.exe",
                ],
            ),
            AppDefinition(
                name="Visual Studio Code",
                aliases={"vscode", "vs code", "code", "visual studio code"},
                process_names=["Code.exe", "code.exe"],
                default_command="code.exe",
                search_paths=[
                    local_appdata / "Programs" / "Microsoft VS Code" / "Code.exe",
                    prog_files / "Microsoft VS Code" / "Code.exe",
                ],
            ),
        ]

        for app in standard_apps:
            key = app.name.lower()
            self._apps[key] = app
            self._alias_map[key] = key
            for alias in app.aliases:
                self._alias_map[alias.lower()] = key

    def resolve(self, query: str) -> Optional[AppDefinition]:
        """
        Resolve an application name or alias to its AppDefinition.
        Strictly rejects arbitrary file paths or malicious patterns.
        """
        cleaned = query.strip().lower()

        # Security check: Disallow paths, drive letters, extensions, or directory traversal
        if any(char in cleaned for char in ("/", "\\", ":", "%", "..", "$")):
            logger.warning("Rejected unsafe application query with path syntax: %s", query)
            return None

        # Remove trailing .exe if passed
        if cleaned.endswith(".exe"):
            cleaned = cleaned[:-4].strip()

        app_key = self._alias_map.get(cleaned)
        if app_key:
            return self._apps.get(app_key)

        return None

    def list_supported_apps(self) -> List[str]:
        """Return a sorted list of all whitelisted application display names."""
        return sorted(app.name for app in self._apps.values())


# Global shared instance of the application registry
_APP_REGISTRY = ApplicationRegistry()


def get_application_registry() -> ApplicationRegistry:
    """Return the singleton ApplicationRegistry instance."""
    return _APP_REGISTRY


# ==============================================================================
# TOOLS IMPLEMENTATION
# ==============================================================================

class OpenApplicationTool(BaseTool):
    """Tool to launch a whitelisted Windows application."""

    def __init__(self, registry: Optional[ApplicationRegistry] = None) -> None:
        self._registry = registry or get_application_registry()

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        supported = ", ".join(self._registry.list_supported_apps())
        return (
            f"Launch a whitelisted Windows application by name or alias. "
            f"Supported applications: {supported}. "
            f"Example: open_application(application_name='notepad')"
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
                    name="application_name",
                    param_type="string",
                    description="Name or alias of the application to open (e.g. 'notepad', 'chrome', 'calculator')",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        raw_name = str(kwargs.get("application_name", "")).strip()

        if not raw_name:
            raise ValueError("application_name cannot be empty.")

        app = self._registry.resolve(raw_name)
        if not app:
            supported = ", ".join(self._registry.list_supported_apps())
            return {
                "success": False,
                "message": (
                    f"'{raw_name}' is not in the list of whitelisted applications. "
                    f"Available applications: {supported}."
                ),
            }

        if not app.is_available():
            return {
                "success": False,
                "application": app.name,
                "message": f"{app.name} is not installed or not available on this system.",
            }

        launched = app.launch()
        if launched:
            return {
                "success": True,
                "application": app.name,
                "message": f"{app.name} launched successfully.",
            }
        else:
            return {
                "success": False,
                "application": app.name,
                "message": f"Failed to launch {app.name}. An internal system error occurred.",
            }


class CloseApplicationTool(BaseTool):
    """Tool to gracefully close a running whitelisted Windows application."""

    def __init__(self, registry: Optional[ApplicationRegistry] = None) -> None:
        self._registry = registry or get_application_registry()

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return (
            "Safely terminate a running whitelisted Windows application by name. "
            "Requires user confirmation before execution. "
            "Example: close_application(application_name='notepad')"
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
                    name="application_name",
                    param_type="string",
                    description="Name or alias of the application to close (e.g. 'notepad', 'chrome')",
                    required=True,
                )
            ],
        )

    def get_confirmation_message(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Produce an accurate, transparent confirmation warning for closing the target application."""
        raw_name = str(arguments.get("application_name", "")).strip()
        if not raw_name:
            return None
        app = self._registry.resolve(raw_name)
        if not app:
            return None
        return app.get_close_warning_message()

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        raw_name = str(kwargs.get("application_name", "")).strip()

        if not raw_name:
            raise ValueError("application_name cannot be empty.")

        app = self._registry.resolve(raw_name)
        if not app:
            supported = ", ".join(self._registry.list_supported_apps())
            return {
                "success": False,
                "message": f"'{raw_name}' is not recognized. Whitelisted applications: {supported}.",
            }

        if not app.is_running():
            return {
                "success": True,
                "application": app.name,
                "message": f"{app.name} is not currently running.",
            }

        # Retrieve running and terminatable PIDs
        running_pids = app.get_running_pids() if hasattr(app, "get_running_pids") else []
        terminatable_pids = app.get_terminatable_pids() if hasattr(app, "get_terminatable_pids") else []

        if isinstance(running_pids, list) and isinstance(terminatable_pids, list):
            if running_pids and not terminatable_pids:
                return {
                    "success": False,
                    "application": app.name,
                    "message": (
                        f"Cannot close {app.name}: the only running instance is the active shell "
                        f"hosting CHARVIS. CHARVIS is protected from self-termination."
                    ),
                }
            closed = app.close(terminatable_pids)
        else:
            closed = app.close()

        if closed:
            return {
                "success": True,
                "application": app.name,
                "message": f"{app.name} was closed successfully.",
            }
        else:
            return {
                "success": False,
                "application": app.name,
                "message": f"Failed to close {app.name}. You may need to close it manually.",
            }


class GetApplicationStatusTool(BaseTool):
    """Tool to check whether a whitelisted Windows application is currently running."""

    def __init__(self, registry: Optional[ApplicationRegistry] = None) -> None:
        self._registry = registry or get_application_registry()

    @property
    def name(self) -> str:
        return "get_application_status"

    @property
    def description(self) -> str:
        return (
            "Check if a whitelisted Windows application is currently running. "
            "Example: get_application_status(application_name='notepad')"
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
                    name="application_name",
                    param_type="string",
                    description="Name or alias of the application to check (e.g. 'notepad', 'chrome')",
                    required=True,
                )
            ],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        self.validate_arguments(kwargs)
        raw_name = str(kwargs.get("application_name", "")).strip()

        if not raw_name:
            raise ValueError("application_name cannot be empty.")

        app = self._registry.resolve(raw_name)
        if not app:
            supported = ", ".join(self._registry.list_supported_apps())
            return {
                "success": False,
                "message": f"'{raw_name}' is not recognized. Whitelisted applications: {supported}.",
            }

        running = app.is_running()
        status_text = "running" if running else "not running"
        return {
            "success": True,
            "application": app.name,
            "running": running,
            "message": f"{app.name} is currently {status_text}.",
        }
