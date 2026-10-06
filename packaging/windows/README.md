# CHARVIS Windows Distribution & Deployment Guide

This document outlines the Windows-specific packaging strategy, startup mechanisms, and deployment preparation for **CHARVIS** (Version 0.18.0).

---

## 1. Windows Startup Integration Details

CHARVIS provides an explicit, transparent, user-controlled startup mechanism:
- **Location**: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CHARVIS_Startup.bat`
- **Methodology**: Plaintext Windows batch script created only upon explicit user invocation.
- **Strict Invariants**:
  - No Windows Services (`services.msc`).
  - No Registry `Run` / `RunOnce` keys (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
  - No Windows Task Scheduler jobs (`schtasks`).
  - No Administrator privilege escalation (`UAC`).
  - Idempotent enable/disable operations.

### Sample Generated Startup Script (`CHARVIS_Startup.bat`)
```bat
@echo off
rem CHARVIS Automatic Background Startup (v0.18.0)
rem This file was created with explicit user permission in CHARVIS Settings.
start "" "C:\Python312\python.exe" "C:\Users\username\AppData\Local\Programs\Charvis\main.py" --tray --background
exit
```

---

## 2. Resource & Path Independence

When CHARVIS is executed via Windows Startup, the current working directory (`%CD%`) is set to `C:\Windows\System32` or the user's home directory.

To ensure stability across all launch environments:
1. `core/paths.py` establishes the project root dynamically from `Path(__file__).resolve().parent.parent` or the environment variable `CHARVIS_PROJECT_ROOT`.
2. All file lookups (logs, sqlite databases, workspace sandbox, icons) resolve against this normalized base directory.
3. Path lookups are validated to exist, creating directory trees automatically if missing.

---

## 3. Single-Instance Architecture & IPC Discovery

Multiple desktop triggers (Startup folder, Start Menu shortcut, Tray clicks) must never produce competing runtimes or orphaned processes.

1. **Instance Lock File**:
   - Location: `%CHARVIS_ROOT%/data/runtime/charvis_runtime.lock`
   - Content: JSON metadata containing PID, allocated local port, host, timestamp, and session token.
   - Validation: `RuntimeLock.is_another_instance_running()` queries `psutil` / Windows API to verify PID liveness and validates local socket ping before declaring an active instance.
2. **Second Launch Handling**:
   - If the runtime is already alive, subsequent invocations of `main.py --tray` or `main.py --gui` connect to the running instance via `RuntimeClient` without re-initializing the core.
   - Closing the GUI window minimizes the application to the Windows system tray.

---

## 4. Packaging Roadmap (Future Phase 19+)

The packaging foundation in Phase 18 structures the codebase for eventual production packaging:

1. **PyInstaller / Nuitka Specification**:
   - Standalone executable generation bundling Python runtime and native DLLs.
   - Hidden imports: `pystray`, `PIL`, `pyaudio`, `playwright`, `sqlite3`.
   - Manifest: Requests `asInvoker` execution level (standard non-elevated user token).
2. **Windows Installer (Inno Setup / WiX Toolset)**:
   - User-level installation into `%LOCALAPPDATA%\Programs\CHARVIS`.
   - Optional desktop and Start Menu shortcuts.
   - Clean uninstaller ensuring complete removal of runtime locks and startup entries.
