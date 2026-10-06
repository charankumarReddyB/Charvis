"""
User-level Windows Startup integration for CHARVIS (Phase 16).
Provides transparent, user-controlled startup via the Windows Startup folder.
Strictly avoids registry hacks, services, scheduled tasks, and hidden persistence.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Optional

from config import BASE_DIR, get_settings
from logger import get_logger
from startup.models import StartupStatus

logger = get_logger("CHARVIS.Startup.Windows")


class WindowsStartupManager:
    """
    Manages optional user-controlled startup of CHARVIS with Windows.
    Uses a transparent batch launcher located in the user's Startup folder.
    """

    ENTRY_FILENAME = "CHARVIS_Startup.bat"

    def __init__(self, startup_dir: Optional[Path] = None) -> None:
        self.settings = get_settings()
        if startup_dir is not None:
            self.startup_dir = Path(startup_dir)
        else:
            self.startup_dir = self._resolve_default_startup_dir()

        self.startup_entry_path = self.startup_dir / self.ENTRY_FILENAME

    def _resolve_default_startup_dir(self) -> Path:
        """Locate user Windows Startup directory safely."""
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def get_status(self) -> StartupStatus:
        """Check whether Windows startup is currently configured and enabled."""
        if not self.startup_entry_path.exists():
            return StartupStatus(
                enabled=False,
                method="startup_folder",
                command=None,
                created_at=None,
                path=str(self.startup_entry_path),
            )

        created_at = None
        command_snippet = None
        try:
            stat = self.startup_entry_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
            content = self.startup_entry_path.read_text(encoding="utf-8", errors="replace")
            # Extract launch line safely
            for line in content.splitlines():
                if "main.py" in line:
                    command_snippet = line.strip()
                    break
        except Exception as e:
            logger.warning("Error reading startup entry: %s", e)

        return StartupStatus(
            enabled=True,
            method="startup_folder",
            command=command_snippet or "CHARVIS --background",
            created_at=created_at,
            path=str(self.startup_entry_path),
        )

    def enable(self, extra_args: str = "--background") -> bool:
        """
        Create the startup entry in the Windows Startup directory.
        Strictly requires explicit user authorization.
        """
        try:
            self.startup_dir.mkdir(parents=True, exist_ok=True)
            python_exe = Path(sys.executable).resolve()
            main_script = (BASE_DIR / "main.py").resolve()

            # Ensure arguments are clean static args
            safe_args = "--background"
            if "--tray" in extra_args and "--gui" in extra_args:
                safe_args = "--gui --tray --background"
            elif "--gui" in extra_args:
                safe_args = "--gui --background"
            elif "--tray" in extra_args:
                safe_args = "--tray --background"

            # Create clean, readable batch startup script
            script_lines = [
                "@echo off",
                f'rem CHARVIS Automatic Background Startup (v{self.settings.app_version})',
                f'rem This file was created with explicit user permission in CHARVIS Settings.',
                f'start "" "{python_exe}" "{main_script}" {safe_args}',
                "exit",
            ]
            script_content = "\r\n".join(script_lines) + "\r\n"

            self.startup_entry_path.write_text(script_content, encoding="utf-8")
            logger.info("Enabled CHARVIS Windows startup: %s", self.startup_entry_path)
            return True
        except Exception as e:
            logger.error("Failed to enable Windows startup: %s", e)
            return False

    def disable(self) -> bool:
        """
        Remove the startup entry from the Windows Startup directory.
        Strictly requires explicit user authorization.
        """
        try:
            if self.startup_entry_path.exists():
                self.startup_entry_path.unlink()
                logger.info("Disabled CHARVIS Windows startup (removed %s).", self.startup_entry_path)
            else:
                logger.debug("Windows startup already disabled (entry does not exist).")
            return True
        except Exception as e:
            logger.error("Failed to disable Windows startup: %s", e)
            return False
