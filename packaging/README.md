# CHARVIS Packaging & Desktop Distribution Foundation

This directory contains packaging specifications, runtime manifests, and environment guidelines for distributing **CHARVIS** (Charan's AI Virtual Intelligent System) on Windows desktop platforms.

---

## 1. Architecture & Packaging Strategy

CHARVIS follows a decoupled, single-instance desktop architecture:
1. **Background Runtime Core**: Authoritative orchestration layer executing AI reasoning, tool routing, safety gating, memory persistence, and local IPC.
2. **System Tray Integration**: Persistent desktop presence providing fast status indicators, activation toggles, and safe lifecycle shutdown.
3. **Desktop GUI Shell**: High-contrast, responsive Tkinter desktop interface that connects via local IPC, minimizing to system tray on window close.

### Portability & Path Independence
All file system paths, databases, workspace sandboxes, and browser profiles resolve through the centralized project-relative path resolver (`core/paths.py`).
- **No hard-coded developer paths** (e.g., `C:\Charan\Charvis`) exist in runtime logic.
- All directories adapt dynamically based on `CHARVIS_PROJECT_ROOT` or application installation location.
- Sandboxed data structures reside under `%CHARVIS_ROOT%/data` or the user's localized AppData profile.

---

## 2. System & Runtime Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit, Build 19041+) | Windows 11 (64-bit) |
| **Python Runtime** | Python 3.11+ (64-bit) | Python 3.12+ (64-bit) |
| **Memory (RAM)** | 4 GB | 8 GB+ |
| **Storage** | 2 GB available space | SSD with 5 GB+ available |
| **Network** | Local loopback (127.0.0.1) | HTTPS access for AI API providers |
| **Audio Hardware** | Microphone & Speakers (for voice) | Noise-cancelling microphone |

---

## 3. Directory Structure & Data Locations

CHARVIS organizes state into isolated, transparent, user-auditable directories:

```
%CHARVIS_ROOT%/
├── config.py              # Centralized pydantic-settings configuration
├── main.py                # Unified CLI, GUI, and daemon entry point
├── core/
│   ├── paths.py           # Project-relative path resolver & environment discovery
│   └── notifications.py   # Redacted desktop notifications service
├── gui/
│   ├── app.py             # Desktop GUI shell (Tkinter)
│   └── tray.py            # Windows System Tray manager (pystray)
├── activation/
│   ├── manager.py         # User activation state machine & voice bridge
│   └── hotkey.py          # Windows RegisterHotKey foundation (Ctrl+Alt+Space)
├── startup/
│   └── windows.py         # User-controlled Startup folder batch launcher
└── data/
    ├── logs/              # Sanitized application audit logs (charvis.log)
    ├── memory/            # SQLite persistent memory database (charvis_memory.db)
    ├── workspace/         # Filesystem sandbox root
    ├── runtime/           # Process lock and IPC metadata (charvis_runtime.lock)
    ├── browser/           # Playwright/Chromium isolated user data profile
    └── screenshots/       # Vision capture cache (temporary)
```

---

## 4. Execution Modes & CLI Entry Points

CHARVIS is launched via `main.py` with explicit operational flags:

```powershell
# 1. Standard Interactive CLI Mode
python main.py

# 2. Desktop System Tray Mode (connects to existing runtime or starts local core)
python main.py --tray

# 3. Desktop GUI with System Tray Integration
python main.py --gui --tray

# 4. Pure Background Runtime Daemon
python main.py --background

# 5. Runtime Health & Status Query
python main.py --status
```

---

## 5. Security & Safety Invariants

- **Authoritative Gating**: All tool execution is mediated by `SafetyManager` and `ToolRouter`. Neither the System Tray nor global hotkeys can invoke tools directly.
- **Zero Keylogging**: The global hotkey subsystem strictly uses the Windows OS `RegisterHotKey` API for `MOD_CONTROL | MOD_ALT | VK_SPACE`. No arbitrary keystrokes are intercepted.
- **Data Redaction**: Notifications and status tooltips filter API keys, tokens, passwords, and sensitive system parameters via `SensitiveDataFilter`.
- **User-Controlled Startup**: No Windows services, scheduled tasks, or registry run keys are installed. Startup uses an explicit batch script in the user's Startup folder.
