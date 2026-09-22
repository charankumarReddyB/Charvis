"""CHARVIS Windows System Control Layer.

Provides strictly controlled workstation locking, shutdown, and restart
actions using narrow Windows C-APIs (user32 / advapi32 via ctypes).
Arbitrary command execution, subprocesses, and shell commands are strictly prohibited.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import platform
from typing import Any, Dict

from logger import get_logger

logger = get_logger(__name__)

# Windows API Constants
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
EWX_LOGOFF = 0x00000000
EWX_SHUTDOWN = 0x00000001
EWX_REBOOT = 0x00000002
EWX_FORCEIFHUNG = 0x00000010
SHTDN_REASON_FLAG_PLANNED = 0x40000000
SHTDN_REASON_MAJOR_OTHER = 0x00000000
SHTDN_REASON_MINOR_OTHER = 0x00000000


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


class SystemController:
    """Safely controls Windows workstation lock, shutdown, and restart actions.

    All destructive actions use direct Win32 APIs without shell or subprocess execution.
    """

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def _ensure_windows(self) -> None:
        """Verify operating system is Windows."""
        if not self._is_windows:
            raise OSError("System control operations are only supported on Windows operating systems.")

    def _enable_shutdown_privilege(self) -> None:
        """Enable SeShutdownPrivilege on current process token to permit shutdown/restart."""
        self._ensure_windows()
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32

        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        advapi32.OpenProcessToken.restype = wintypes.BOOL

        advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
        advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL

        advapi32.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(TOKEN_PRIVILEGES),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

        h_token = wintypes.HANDLE()
        proc = kernel32.GetCurrentProcess()

        if not advapi32.OpenProcessToken(proc, TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(h_token)):
            err = ctypes.GetLastError()
            logger.error("Failed to open process token for shutdown privilege (error: %d)", err)
            raise PermissionError(f"Failed to open process token for shutdown privilege (error {err})")

        try:
            luid = LUID()
            if not advapi32.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
                err = ctypes.GetLastError()
                logger.error("Failed to lookup SeShutdownPrivilege (error: %d)", err)
                raise PermissionError(f"Failed to lookup SeShutdownPrivilege (error {err})")

            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

            if not advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None):
                err = ctypes.GetLastError()
                logger.error("Failed to adjust token privileges for shutdown (error: %d)", err)
                raise PermissionError(f"Failed to adjust token privileges for shutdown (error {err})")

            err = ctypes.GetLastError()
            if err != 0:
                logger.warning("Token privilege adjustment returned non-zero status: %d", err)
        finally:
            kernel32.CloseHandle(h_token)

    def _lock_workstation_api(self) -> bool:
        """Call Windows LockWorkStation API."""
        user32 = ctypes.windll.user32
        user32.LockWorkStation.argtypes = []
        user32.LockWorkStation.restype = wintypes.BOOL
        return bool(user32.LockWorkStation())

    def _shutdown_system_api(self) -> bool:
        """Call Windows ExitWindowsEx or InitiateSystemShutdownExW API for shutdown."""
        user32 = ctypes.windll.user32
        user32.ExitWindowsEx.argtypes = [wintypes.UINT, wintypes.DWORD]
        user32.ExitWindowsEx.restype = wintypes.BOOL
        reason = SHTDN_REASON_FLAG_PLANNED | SHTDN_REASON_MAJOR_OTHER | SHTDN_REASON_MINOR_OTHER
        return bool(user32.ExitWindowsEx(EWX_SHUTDOWN | EWX_FORCEIFHUNG, reason))

    def _restart_system_api(self) -> bool:
        """Call Windows ExitWindowsEx API for restart."""
        user32 = ctypes.windll.user32
        user32.ExitWindowsEx.argtypes = [wintypes.UINT, wintypes.DWORD]
        user32.ExitWindowsEx.restype = wintypes.BOOL
        reason = SHTDN_REASON_FLAG_PLANNED | SHTDN_REASON_MAJOR_OTHER | SHTDN_REASON_MINOR_OTHER
        return bool(user32.ExitWindowsEx(EWX_REBOOT | EWX_FORCEIFHUNG, reason))

    def lock_workstation(self) -> Dict[str, Any]:
        """Lock the active Windows workstation."""
        self._ensure_windows()
        logger.info("Executing workstation lock")
        success = self._lock_workstation_api()
        if not success:
            err = ctypes.GetLastError()
            logger.error("LockWorkStation failed with error code: %d", err)
            raise RuntimeError(f"LockWorkStation failed with error code: {err}")
        return {
            "status": "locked",
            "message": "Windows workstation has been locked successfully.",
        }

    def shutdown_system(self) -> Dict[str, Any]:
        """Initiate immediate Windows system shutdown."""
        self._ensure_windows()
        logger.warning("Initiating system shutdown sequence")
        self._enable_shutdown_privilege()
        success = self._shutdown_system_api()
        if not success:
            err = ctypes.GetLastError()
            logger.error("ExitWindowsEx shutdown failed with error code: %d", err)
            raise RuntimeError(f"Windows shutdown failed with error code: {err}")
        return {
            "status": "shutting_down",
            "message": "Windows system shutdown has been initiated.",
        }

    def restart_system(self) -> Dict[str, Any]:
        """Initiate immediate Windows system restart."""
        self._ensure_windows()
        logger.warning("Initiating system restart sequence")
        self._enable_shutdown_privilege()
        success = self._restart_system_api()
        if not success:
            err = ctypes.GetLastError()
            logger.error("ExitWindowsEx restart failed with error code: %d", err)
            raise RuntimeError(f"Windows restart failed with error code: {err}")
        return {
            "status": "restarting",
            "message": "Windows system restart has been initiated.",
        }
