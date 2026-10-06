# CHARVIS (Charan's AI Virtual Intelligent System)

CHARVIS is a personal AI computer assistant built for Windows. The vision is an advanced, Jarvis-like autonomous assistant capable of natural conversation, computer automation, vision comprehension, file management, system control, and multi-step task execution with strict safety guardrails.

---

## Current Status: Phase 19 (Activation Experience & Assistant UI)
Version: 0.19.0 | Tool Count: 75

- [x] **Phase 1: Project foundation and configuration** *(Complete)*
- [x] **Phase 2: Text-based AI assistant** *(Complete)*
- [x] **Phase 3: Tool-calling architecture** *(Complete)*
- [x] **Phase 4: Basic Windows application control** *(Complete)*
- [x] **Phase 4.1: Safety review & PID hardening** *(Complete)*
- [x] **Phase 5: Keyboard and mouse control** *(Complete)*
- [x] **Phase 6: File and folder management** *(Complete)*
- [x] **Phase 7: System information and controls** *(Complete)*
- [x] **Phase 8: Voice input and output** *(Complete)*
- [x] **Phase 9: Wake-word support** *(Complete)*
- [x] **Phase 10: Browser automation (Playwright)** *(Complete)*
- [x] **Phase 11: Screenshot and OCR** *(Complete)*
- [x] **Phase 12: Vision-based screen understanding** *(Complete)*
- [x] **Phase 13: Memory system** *(Complete)*
- [x] **Phase 14: Multi-step task planning and execution** *(Complete)*
- [x] **Phase 15: Desktop GUI (Tkinter + ttk)** *(Complete)*
- [x] **Phase 16: Background Runtime & Windows Startup** *(Complete)*
- [x] **Phase 17: Hardening, Reliability & Performance** *(Complete)*
- [x] **Phase 18: Packaging, System Tray & Startup UX** *(Complete)*
- [x] **Phase 19: Activation Experience & Assistant UI** *(Complete)*


---

## System Architecture

```
User Voice / Text CLI / Desktop GUI / Windows Startup
       │
       ▼
 [gui/app.py: CharvisApp] ──► [runtime/client.py: RuntimeClient]
                                    │ (Localhost TCP IPC: 127.0.0.1)
                                    ▼
                     [runtime/ipc.py: IPCServer]
                                    │
                                    ▼
                     [runtime/controller.py: RuntimeController]
                                    │
       ┌────────────────────────────┴───────────────────────────┐
       ▼                                                        ▼
 [voice/audio.py] ──► [voice/stt.py]                   [core/brain.py: AIBrain]
                                                                │ (75 Registered Tools)
                                              ┌─────────────────┴─────────────────┐
                                              ▼                                   ▼
                                       Cloud/Local LLM               [tools/router.py: ToolRouter]
                                                                                  │
                                                                                  ├─► [core/safety.py: SafetyManager]
                                                                                  ├─► Tools: Calculator, Apps, Keyboard,
                                                                                  │   Mouse, Filesystem, System Control,
                                                                                  │   Voice I/O, Wake Word, Browser,
                                                                                  │   Vision/OCR, Memory, Task Planner,
                                                                                  │   and Runtime/Startup Lifecycle
                                                                                  ▼
                                                                     Authoritative Execution
       │
       ▼
 [voice/tts.py: TTSProvider] ──► Speaker Output
```

---

## Phase 8: Voice Input & Output

### 1. Speech-to-Text (STT) Subsystem
- **On-Demand Capture**: The microphone is accessed strictly during an explicit `listen()` action or in active `voice` mode.
- **Provider Abstraction (`BaseSTTProvider`)**:
  - `GoogleWebSTTProvider`: Out-of-the-box, free speech recognition via Google Web Speech API.
  - `OpenAISTTProvider`: Cloud Whisper API (`whisper-1`) when OpenAI API key is configured.
  - `MockSTTProvider`: Offline in-memory mock for deterministic automated tests.
- **Controlled Audio Capture (`AudioCapture`)**:
  - Validates hardware device presence.
  - Records single bounded 16kHz mono audio snippets.
  - Immediately releases the microphone stream and hardware handles. Zero background listeners.

### 2. Text-to-Speech (TTS) Subsystem
- **Provider Abstraction (`BaseTTSProvider`)**:
  - `Pyttsx3TTSProvider`: Offline local Windows SAPI5 synthesizer. Works without internet or API keys.
  - `OpenAITTSProvider`: High-definition cloud voice generation via OpenAI Audio Speech API.
  - `MockTTSProvider`: In-memory recording mock for automated tests.
- **Secret Redaction & Safety**:
  - Automatically sanitizes API keys (`sk-...`), passwords, tokens, and raw Python tracebacks before vocalization.
  - Enforces text length bounds (`max_tts_length = 1000`) to prevent runaway audio generation.

### 3. Voice Tools
- **`listen(duration=5.0)`** *(Risk: `SAFE`)*: Captures a single spoken utterance and returns its transcription.
- **`speak(text)`** *(Risk: `SAFE`)*: Vocalizes text using the active TTS provider.

### 4. Interactive Voice Mode
- Users can type `voice` in the CLI to enter interactive voice conversation mode.
- CHARVIS listens on-demand, transcribes speech, processes requests through the cognitive loop, prints the response to the terminal, and speaks the answer aloud.
- Say `"exit voice mode"`, `"exit"`, `"stop listening"`, or press `Ctrl+C` to return immediately to standard text CLI mode.

---

## Privacy Guardrails & Explicit Scope

> [!IMPORTANT]
> **Privacy and Audio Policy:**
> - **No Background Listening**: CHARVIS never records in the background, never monitors ambient audio, and never opens the microphone on startup.
> - **No Wake-Word**: Wake-word detection is intentionally excluded from Phase 8 (scheduled for Phase 9).
> - **No Permanent Audio Storage**: Audio recordings are processed in-memory or ephemeral buffers and discarded immediately.
> - **API Credentials**: Cloud STT/TTS credentials must be supplied via secure configuration (`.env`); keys are never hard-coded or logged.

---

## Running CHARVIS

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run CHARVIS
python main.py
```

### Example Session (Voice Mode)

```text
============================================================
  CHARVIS - AI Virtual Intelligent System (v0.13.0)
  Phase 13    : Memory System
  Environment : development
  Provider    : OPENAI (gpt-4o-mini)
  API Key     : Configured
  Tools       : 61 active (calc, apps, keyboard, mouse, fs, system, voice, wakeword, browser, vision, memory)
  Platform    : Windows 11 (AMD64)
  Commands    : Type 'voice' for voice mode, 'wakeword' for standby, 'exit' to quit
============================================================

You: voice

============================================================
CHARVIS Voice Mode Enabled.
Speak into your microphone when 'Listening...' appears.
Say 'exit voice mode', 'stop listening', or press Ctrl+C to quit.
============================================================

Listening... (Speak now)
You said: What is my CPU usage?

CHARVIS: Your CPU utilization is currently 12.4% across 16 logical cores.
[TTS plays answer aloud through speaker]

Listening... (Speak now)
You said: exit voice mode

CHARVIS: Exiting voice mode. Returning to text interface.

You: 
```

---

## Phase 9: Wake-Word Standby Mode

Phase 9 introduces a local, offline wake-word activation layer that allows CHARVIS to wait in standby until summoned by voice.

### 1. Standby & Activation Architecture

```
STANDBY
   │ (local short-frame evaluation, 0 disk storage, 0 cloud streaming)
   ▼
Wake Word Detection ("Hey CHARVIS")
   │
   ▼
LISTENING (Activation cue: "Yes?")
   │ (normal Phase 8 STT records bounded command)
   ▼
PROCESSING (Wake phrase stripped from command)
   │
   ├──► AIBrain
   │       └──► ToolRouter (33 tools registered)
   │               └──► SafetyManager (confirmation enforced)
   ▼
SPEAKING (Assistant response via TTS)
   │
   ▼
STANDBY (Resumes monitoring for wake phrase)
```

### 2. Supported State Machine
The `WakeWordEngine` enforces an explicit, deterministic state machine:
- `STOPPED`: Engine is inactive; no audio is captured.
- `STANDBY`: Engine monitors short, ephemeral audio frames in memory for the wake phrase.
- `LISTENING`: Wake word detected; prompts user with "Yes?" and captures command speech.
- `PROCESSING`: Command text routed to `AIBrain` for reasoning, tool routing, and execution.
- `SPEAKING`: Response synthesized and played aloud via `TTSProvider`.
- `ERROR`: Safe error state with automatic recovery back to `STANDBY`.

Allowed transitions:
- `STANDBY` → `LISTENING`
- `LISTENING` → `PROCESSING`
- `PROCESSING` → `SPEAKING`
- `SPEAKING` → `STANDBY`
- `Any state` → `STOPPED`
- `ERROR` → `STANDBY`

### 3. Clear Interface Separation
CHARVIS offers three distinct, non-conflicting interaction modes:
1. **Standard Text CLI**: Type commands into the prompt (`You: `).
2. **Explicit Voice Mode (Phase 8)**: Type `voice` to enter an interactive conversation loop.
3. **Standby Wake-Word Mode (Phase 9)**: Type `wakeword` to enter local standby listening.

> [!NOTE]
> Wake-word mode is **NEVER** automatically enabled at application startup. It requires explicit user activation.

### 4. Privacy Guarantees
- **Zero Audio Persistence**: Short audio frames are processed strictly in RAM and immediately discarded. No WAV or PCM files are saved to disk.
- **Zero Cloud Streaming During Standby**: Continuous microphone audio is never streamed to OpenAI Whisper or any external cloud provider.
- **Local Keyword Spotting**: Frame analysis operates locally via `BaseWakeWordDetector` / `LocalKeywordDetector`.
- **Immediate Resource Cleanup**: Audio devices and streams are immediately released upon typing `stop wakeword`, `exit`, or pressing `Ctrl+C`.

### 5. Security Guardrails
The wake phrase serves solely as an activation mechanism; it **NEVER** authorizes dangerous actions.
- Any dangerous command spoken via wake word (such as `shutdown_system`, `restart_system`, or `delete_file`) immediately halts for human confirmation via `SafetyManager`.
- If the user denies or aborts confirmation, the operation is blocked.

### 6. Configuration Options
Configurable in `.env`:
| Setting | Default | Description |
|---|---|---|
| `WAKE_WORD_PHRASE` | `hey charvis` | Wake phrase activation trigger (case-insensitive) |
| `WAKE_WORD_TIMEOUT` | `30.0` | Maximum duration in seconds for standby session |
| `WAKE_WORD_FRAME_DURATION` | `1.0` | Duration in seconds of each short in-memory frame |
| `COMMAND_LISTEN_TIMEOUT` | `5.0` | Maximum seconds to wait for command speech after wake cue |

---

## Phase 10: Controlled Browser Automation

Phase 10 introduces controlled browser automation to CHARVIS using Playwright (Chromium), enabling web page navigation, inspection, interaction, and data extraction under strict safety guardrails.

### 1. Architecture & Isolated Profile

```
AIBrain / ToolRouter
       │
       ▼
 [tools/browser.py]  (10 Browser Tools)
       │
       ▼
 [browser/controller.py: BrowserController]
       │
       ├─► [browser/security.py: Security Guardrails]
       │       ├─ URL validation (http/https only)
       │       ├─ Sensitive field detection & redaction
       │       └─ High-impact action risk classification
       │
       ▼
 [Playwright Chromium Engine]
       │
       └─► Isolated Profile: data/browser_profile/
           (NEVER touches personal Chrome/Edge user data)
```

- **Isolated User Data Directory**: Browser state (cookies, local storage, cache) is kept in `data/browser_profile/`. CHARVIS never accesses or tampers with the user's personal Google Chrome, Microsoft Edge, or Firefox profiles.
- **Centralized Session Management**: `BrowserController` maintains an active Playwright browser instance across multi-step tool calls and automatically cleans up resources when `close_browser` is invoked or upon exit.
- **Headless & Headed Modes**: Runs headed by default (`BROWSER_HEADLESS=false`) so the user can observe actions, with optional headless operation.

### 2. Browser Safety & Security Guardrails

> [!IMPORTANT]
> **Browser Security Policy:**
> - **Strict URL Scheme Validation**: Only `http://` and `https://` URLs are permitted. Schemes such as `file://`, `javascript:`, `data:`, `vbscript:`, and browser-internal URLs (`chrome://`, `edge://`, `about:`) are rejected immediately with a `BrowserSecurityError`.
> - **External Action Confirmation**: High-impact actions that trigger irreversible or external real-world effects require explicit human confirmation (`CONFIRMATION_REQUIRED`). Keywords triggering confirmation: `buy`, `purchase`, `checkout`, `pay`, `order`, `subscribe`, `delete`, `remove`, `send message`, `send email`, `transfer`.
> - **Sensitive Field Protection**: Password, credit card, CVV, OTP, and PIN inputs trigger `CONFIRMATION_REQUIRED`. Furthermore, sensitive text is automatically masked and logged as `***REDACTED***` in tool outputs and logs.
> - **Zero Arbitrary JavaScript Execution**: CHARVIS does not expose `evaluate` or arbitrary script injection tools. All interactions occur via Playwright locators and user gestures.
> - **Download Blocking**: Automatic file downloads initiated by web pages are intercepted and cancelled immediately to safeguard the local filesystem.

### 3. Registered Browser Tools (10 Tools)

| Tool Name | Risk Level | Description |
|---|---|---|
| `open_browser(url, headless)` | `SAFE` | Opens an isolated browser session, optionally navigating to an initial URL. |
| `navigate_browser(url)` | `SAFE` | Navigates the active page to a validated HTTP/HTTPS URL. |
| `get_page_info(max_text_length)` | `SAFE` | Retrieves the page title, current URL, and visible page text. |
| `click_element(selector, text)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Clicks a page element by CSS/XPath selector or visible text. Actions involving checkout, payment, deletion, or sending messages require confirmation. |
| `type_into_element(selector, text, clear_first)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Types text into an element. Sensitive targets (passwords, card numbers, OTPs) require confirmation and redact the value. |
| `go_back()` | `SAFE` | Navigates back in browser history. |
| `go_forward()` | `SAFE` | Navigates forward in browser history. |
| `reload_page()` | `SAFE` | Reloads the current page. |
| `get_current_url()` | `SAFE` | Returns the current page URL. |
| `close_browser()` | `SAFE` | Closes the active browser session and frees resources. |

### 4. Browser Configuration Options

Configurable in `.env`:

| Setting | Default | Description |
|---|---|---|
| `BROWSER_HEADLESS` | `false` | Run browser in headless mode (`true` or `false`) |
| `BROWSER_NAVIGATION_TIMEOUT` | `30000` | Page navigation timeout in milliseconds |
| `BROWSER_ACTION_TIMEOUT` | `10000` | Element action timeout in milliseconds |
| `BROWSER_PAGE_TEXT_LIMIT` | `5000` | Maximum visible text characters extracted from a page |
| `BROWSER_USER_DATA_DIR` | `data/browser_profile` | Directory for the isolated browser user data profile |

---

## Phase 11: Screenshot & OCR

Phase 11 introduces visual awareness to CHARVIS through desktop screenshot capture and local Optical Character Recognition (OCR), operating under strict privacy boundaries and sandbox constraints.

### 1. Architecture & Local Processing

```
AIBrain / ToolRouter
       │
       ▼
 [tools/vision.py]  (7 Vision Tools)
       │
       ├─► [vision/security.py: Coordinate & Sandbox Guardrails]
       │       ├─ Coordinate boundary validation (x, y >= 0, w, h > 0)
       │       ├─ Monitor index validation
       │       ├─ Sandbox save destination validation
       │       └─ Area constraints (<= 33,177,600 px)
       │
       ▼
 [vision/screenshot.py: ScreenshotEngine] ──► In-Memory PIL Image (Never written unless asked)
       │
       ▼
 [vision/ocr.py: BaseOCRProvider]
       ├─► TesseractOCRProvider (Local offline Tesseract via pytesseract)
       └─► MockOCRProvider (Deterministic offline mock for tests)
```

- **In-Memory Capture**: All screenshots are captured directly into RAM (`PIL.Image.Image`). No temporary files, BMPs, or PNGs are saved to disk unless explicitly authorized via `save_screenshot`.
- **Local OCR Only**: Text recognition executes entirely locally via Tesseract OCR or Mock provider. CHARVIS **NEVER** uploads screenshots or visual data to external cloud APIs (OpenAI, Gemini, Claude, or third-party OCR services).
- **Perception Only**: Vision tools only perceive, locate, and read information. They **NEVER** directly trigger mouse clicks, movements, or keyboard strokes. Visual findings are passed to `AIBrain`, and any follow-up physical automation must go through existing Phase 5 tools with their respective safety controls.

### 2. Vision Privacy & Safety Guardrails

> [!IMPORTANT]
> **Vision Safety Policy:**
> - **Zero Background Monitoring**: CHARVIS does not continuously record screens or monitor the desktop in the background. Screenshots are captured strictly on-demand per tool call.
> - **Sandbox Protection for Saving**: `save_screenshot` requires explicit user authorization (`RiskLevel.CONFIRMATION_REQUIRED`) and restricts file writes strictly to `data/workspace/`. Path traversal (`..`) and absolute path escapes are blocked.
> - **Coordinate Boundaries**: Region coordinates `(x, y, width, height)` are validated against the primary screen resolution. Coordinates cannot be negative, dimensions must be strictly positive, and regions cannot exceed screen bounds or 8K resolution area limits.
> - **Sensitive Log Exclusion**: Extracted OCR text and screen contents are excluded from persistent diagnostic log files.

### 3. Registered Vision Tools (7 Tools)

| Tool Name | Risk Level | Description |
|---|---|---|
| `capture_screenshot()` | `SAFE` | Captures primary desktop screen into memory. Returns dimensions and timestamp. |
| `capture_screen(monitor)` | `SAFE` | Captures a specific display monitor index into memory. |
| `capture_region(x, y, width, height)` | `SAFE` | Captures a bounded rectangular region into memory with strict boundary validation. |
| `save_screenshot(filename, overwrite)` | `CONFIRMATION_REQUIRED` | Saves the current in-memory screenshot to the workspace sandbox directory. |
| `read_screen_text(max_length)` | `SAFE` | Captures primary screen and extracts visible text, word blocks, and bounding boxes via local OCR. |
| `read_region_text(x, y, width, height, max_length)` | `SAFE` | Captures a bounded region and extracts text with screen-relative bounding boxes. |
| `find_text_on_screen(text, case_sensitive)` | `SAFE` | Searches screen via local OCR for target string and returns matching bounding boxes. Perception only. |

### 4. Vision Configuration Options

Configurable in `.env`:

| Setting | Default | Description |
|---|---|---|
| `OCR_PROVIDER_TYPE` | `tesseract` | OCR provider backend (`tesseract`, `mock`) |
| `TESSERACT_CMD` | `None` | Optional custom executable path to `tesseract.exe` |
| `MAX_SCREENSHOT_WIDTH` | `7680` | Maximum allowable screenshot width in pixels |
| `MAX_SCREENSHOT_HEIGHT` | `4320` | Maximum allowable screenshot height in pixels |
| `MAX_REGION_AREA` | `33177600` | Maximum pixel area allowed for region captures |
| `MAX_OCR_TEXT_LENGTH` | `4000` | Maximum characters of extracted text returned to AI Brain |
| `OCR_CONFIDENCE_THRESHOLD` | `0.0` | Minimum confidence score threshold for recognized text blocks |
| `SCREENSHOT_SAVE_DIR` | `data/workspace` | Sandbox directory for saving screenshots |

---

## Phase 12: Vision / Screen Understanding

Phase 12 elevates CHARVIS from raw OCR text extraction to structured visual screen comprehension. It enables CHARVIS to recognize application windows, buttons, input fields, menus, text blocks, and icons, mapping their semantic roles and coordinates while strictly preserving user privacy and safety.

### 1. Architecture & Provider Abstraction

```
AIBrain / ToolRouter
       │
       ▼
 [tools/vision.py]  (5 New Perception-Only Tools / 12 Total Vision Tools)
       │
       ├─► [vision/security.py: Privacy & Model Guardrails]
       │       ├─ Cloud permission check: check_cloud_vision_allowed(config)
       │       ├─ Coordinate boundary validation (x, y, w, h within screen bounds)
       │       ├─ Output sanitization & length clamping (summary <= 2000, labels <= 100)
       │       └─ Element count enforcement (<= 50 elements)
       │
       ▼
 [vision/analyzer.py: VisionAnalyzer]
       │
       ├─► In-Memory Screenshot (ScreenshotEngine) + OCR (BaseOCRProvider)
       │
       ▼
 [vision/providers.py: BaseVisionProvider]
       ├─► LocalHeuristicVisionProvider (Default, 100% private, zero network calls)
       ├─► OpenAIVisionProvider (Multimodal cloud model; requires VISION_CLOUD_ENABLED=true)
       └─► MockVisionProvider (Deterministic mock for automated testing)
```

- **Local & Private by Default**: `VISION_CLOUD_ENABLED=false` by default. Under the default configuration, all screen understanding runs through `LocalHeuristicVisionProvider`, which combines in-memory image analysis with local OCR and rule-based heuristics. **Zero images or visual data leave your machine.**
- **Cloud Vision Provider with Strict Opt-In**: If enabled via `VISION_CLOUD_ENABLED=true` and an API key is configured, `OpenAIVisionProvider` can encode screenshots (base64 PNG) to query multimodal vision models (e.g., `gpt-4o-mini`). Attempts to use cloud vision without explicit consent raise `VisionCloudDisabledError`.
- **Perception Only**: Vision tools analyze and report structured screen descriptions and element bounding boxes. They **NEVER** execute clicks, type keystrokes, or move the cursor. Downstream actions must be explicitly routed through Phase 5 control tools by the user or cognitive loop.

### 2. Supported Element Types & Data Models

- **`SUPPORTED_ELEMENT_TYPES`**:
  `window`, `button`, `input_field`, `text_block`, `menu`, `icon`, `image`, `unknown`
- **`ScreenElement`**:
  - `element_type`: Validated type from supported types
  - `label`: Bounded text label describing the element (<= 100 characters)
  - `x`, `y`, `width`, `height`: Pixel coordinates and dimensions
  - `confidence`: Bounded score between 0.0 and 1.0
  - `center`: Computed `(x + width // 2, y + height // 2)` helper for mouse targeting
- **`ScreenDescription`**:
  - `summary`: Human-readable summary of the screen state (<= 2000 characters)
  - `active_window`: Title/name of the primary visible window (if detectable)
  - `elements`: List of validated `ScreenElement` instances (capped at 50)
  - `width`, `height`: Resolution of the captured frame
  - `timestamp`: Capture timestamp in ISO 8601

### 3. Registered Phase 12 Vision Tools (5 New Tools / 12 Total)

| Tool Name | Risk Level | Description |
|---|---|---|
| `analyze_screen(provider_type)` | `SAFE` | Captures primary screen and returns full structured `ScreenDescription` (summary, active window, elements). |
| `analyze_screen_region(x, y, width, height, provider_type)` | `SAFE` | Captures a bounded desktop region and analyzes elements with screen-relative coordinates. |
| `find_visual_element(target, element_type)` | `SAFE` | Searches the screen for a visual element by label, keyword, or element type, returning matching bounding boxes and center coordinates. |
| `describe_screen()` | `SAFE` | Generates a high-level summary of the active desktop layout, visible apps, and prominent UI landmarks. |
| `get_screen_elements(element_type)` | `SAFE` | Returns a structured list of detected UI elements, optionally filtered by `element_type`. |

### 4. Phase 12 Configuration Options

Configurable in `.env`:

| Setting | Default | Description |
|---|---|---|
| `VISION_CLOUD_ENABLED` | `false` | Enable/disable sending screenshots to cloud vision providers (`true` or `false`) |
| `VISION_PROVIDER_TYPE` | `local` | Default vision provider backend (`local`, `openai`, `mock`) |
| `VISION_MODEL` | `gpt-4o-mini` | Cloud vision model name when cloud provider is active |
| `VISION_TIMEOUT` | `30.0` | Timeout in seconds for vision analysis calls |
| `MAX_SCREEN_ELEMENTS` | `50` | Maximum number of UI elements returned per analysis |
| `MAX_ELEMENT_LABEL_LENGTH` | `100` | Maximum character length of element labels |
| `MAX_SCREEN_SUMMARY_LENGTH` | `2000` | Maximum character length of screen summaries |

---

## Phase 13: Memory System

Phase 13 introduces a structured, selective, and privacy-preserving memory architecture to CHARVIS. It equips the assistant with short-term (in-process session) memory and persistent long-term (local SQLite) storage, enabling personalized and contextual responses while preventing unbounded bloat, rejecting sensitive credentials, and treating memory strictly as untrusted data.

> [!IMPORTANT]
> **Core Principle:**
> **CHARVIS does not automatically remember every conversation.**
> Memory is selective, structured, inspectable, and controllable. It captures useful context (such as preferred programming languages, recurring project configurations, and stable workflows) while strictly rejecting credentials, tokens, cards, and sensitive browser session data.

### 1. Architecture

```
                    AIBrain
                       │
              ┌────────┴────────┐
              ▼                 ▼
       Session Memory      Long-Term Memory
       (Process-local)     (SQLite Database)
              │                 │
              └────────┬────────┘
                       ▼
                 MemoryManager
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Storage      Retrieval    Security
      (SQLite)     (Scoring)    (Sanitizer)
          │            │            │
          └────────────┴────────────┘
                       │
                       ▼
                 Memory Result
```

- **Independent from LLM Provider**: `AIBrain` interfaces with `MemoryManager` via clean abstractions (`BaseMemoryStorage`). Zero database vendor lock-in.
- **Local SQLite Storage**: Stored strictly at `data/memory/charvis_memory.db`. Zero cloud memory databases, zero vector database dependencies, zero embeddings.
- **Session vs. Long-Term Memory**:
  - `SessionMemory`: In-memory temporary cache for the active conversation turn (current task, recent user intents). Discarded cleanly on exit unless explicitly promoted.
  - `SQLiteMemoryStorage`: Fully parameterized SQL database storing structured `MemoryItem` entities across reboots.

### 2. Memory Categories & Sources

- **Explicit Categories (`MemoryCategory`)**:
  - `PREFERENCE`: User communication and coding preferences (e.g., `"user prefers Python for rapid prototyping"`).
  - `PROJECT`: Architecture and tech stack details (e.g., `"FoodConnect uses Firebase"`).
  - `WORKFLOW`: Recurring operational styles (e.g., `"user wants step-by-step verification"`).
  - `FACT`: Verified external facts (e.g., `"user's OS is Windows 11"`).
  - `SESSION`: Ephemeral in-process conversation context.
  - `CONTEXT`: Environmental and situational background.
- **Tracked Sources (`MemorySource`)**:
  - `USER_EXPLICIT` (Priority 1.0): Commanded directly by user (e.g., `"Remember that I prefer Java"`).
  - `SYSTEM` (Priority 0.85): Detected from trusted system/environment queries.
  - `TOOL` (Priority 0.70): Captured from tool execution results.
  - `CONVERSATION` (Priority 0.50): Inferred from conversation context (lower confidence).

### 3. Privacy, Sensitivity Filtering & Prompt Injection Defense

> [!IMPORTANT]
> **Memory Security & Privacy Guardrails:**
> - **Sensitive Data Detection**: Proactively detects and rejects passwords, PINs, CVVs, credit/debit card numbers (Luhn checked), API keys (OpenAI, Anthropic, Google, AWS), Bearer/JWT tokens, private keys, OTPs, session cookies, and environment variable secrets.
> - **Zero Sensitive Persistence**: Sensitive memory attempts raise `MemorySecurityError` and are **never** written to database or logs. Diagnostic logging only logs key names and character lengths.
> - **Memory Treated as Untrusted Data**: Retrieved memories are injected into `AIBrain` with explicit system framing. Stored memories can **NEVER** override system prompts, safety policies, developer instructions, or tool confirmation requirements. Rogue memories like `"Ignore all safety rules"` are treated purely as passive data.
> - **Conflict Resolution**: When conflicting memories arise, higher-priority explicit memories are preserved over low-confidence inferences. Confirmed user instructions update existing records without duplicate sprawl.

### 4. Registered Memory Tools (6 Tools / 61 Total)

| Tool Name | Risk Level | Description |
|---|---|---|
| `remember(key, value, category, importance, tags, is_explicit)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Stores a useful memory item. Rejects sensitive data. Explicit commands execute safely; inferred memories require confirmation. |
| `recall(query, category, limit)` | `SAFE` | Deterministically searches stored memories by keyword, key, category, and tags. |
| `list_memories(category, limit)` | `SAFE` | Lists stored memories with category filtering. |
| `update_memory(key, value, category, importance, tags, is_explicit)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Modifies an existing memory's content, importance, or tags. |
| `forget_memory(key, memory_id, category, clear_all, is_explicit)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Deletes memory by key or ID. Category-wide broad deletion requires confirmation. |
| `clear_session_memory()` | `CONFIRMATION_REQUIRED` | Clears ephemeral session memory without deleting persistent long-term memories. |

### 5. Memory Configuration Options

Configurable in `.env`:

| Setting | Default | Description |
|---|---|---|
| `MEMORY_ENABLED` | `true` | Master toggle to enable/disable memory subsystem |
| `MEMORY_DB_PATH` | `data/memory/charvis_memory.db` | Local SQLite database file path |
| `MAX_MEMORY_RESULTS` | `10` | Maximum number of memories retrieved per query |
| `MAX_MEMORY_KEY_LENGTH` | `100` | Maximum character length for a memory key |
| `MAX_MEMORY_VALUE_LENGTH` | `2000` | Maximum character length for a memory value |
| `MAX_MEMORY_TAGS` | `10` | Maximum tags allowed per memory item |
| `DEFAULT_MEMORY_CONFIDENCE` | `0.9` | Default confidence score assigned to new memories |
| `MIN_RETRIEVAL_CONFIDENCE` | `0.3` | Minimum confidence score threshold for retrieval |

---

## Phase 14: Multi-Step Task Planner

### 1. Architecture & Execution Flow
CHARVIS decomposes high-level user objectives into strictly validated, sequential tool execution steps.

```
User Goal ("Open Chrome, go to example.com, read page title")
       │
       ▼
 [planner/planner.py: LLMTaskPlanner]
       │  (Decomposes into candidate steps JSON conforming to schema)
       ▼
 [planner/validator.py: PlanValidator]
       │  (Validates tool registry, arg schemas, ordering, rejects code injection)
       ▼
 [planner/models.py: Task (status=READY)]
       │
       ▼
 [planner/executor.py: TaskExecutor]
       │
       ├─► Step 1 ──► [tools/router.py: ToolRouter] ──► [core/safety.py] ──► Tool Execution
       │                   │
       │                   ▼
       │             [ToolResult] ──► [planner/evaluator.py: ResultEvaluator]
       │                                   │ (SUCCESS / USER_DENIED / RETRY_ELIGIBLE / FAILED)
       │
       ├─► Step 2 ──► [tools/router.py: ToolRouter] ──► [core/safety.py] ...
       │
       ▼
 Task Status: COMPLETED / FAILED / WAITING_CONFIRMATION / PAUSED
```

### 2. Critical Safety & Invariant Enforcement
- **Planner is NOT a Permission System**: The planner only proposes candidate actions. Every step MUST execute through `ToolRouter` and `SafetyManager`.
- **Zero Risk Downgrading**: The planner cannot lower tool risk levels or bypass human authorization.
- **Human Confirmation Integrity**: Steps requiring confirmation pause with `WAITING_CONFIRMATION` unless confirmed. If confirmation is denied by the user, the task terminates immediately with `FAILED` and **zero retries**.
- **Zero Arbitrary Code Execution**: Code injection patterns (`os.system`, `subprocess`, `exec`, `eval`, `powershell`, `bash`, `cmd.exe`, `__import__`) are strictly blocked by `PlanValidator` with `PlanSecurityError`.
- **Perception Data Isolation**: Screen OCR text, vision summaries, webpage content, and recalled memories are strictly treated as **untrusted data**, never executable instructions.
- **Strict Guardrail Limits**:
  - `MAX_TASK_STEPS = 15`: Prevents runaway sequences.
  - `MAX_REPLANS_PER_TASK = 3`: Prevents infinite self-correction loops.
  - `MAX_STEP_RETRIES = 1`: Transient retries allowed only for non-destructive actions.
  - `MAX_ACTIVE_TASKS = 20`: Bounded in-memory storage; oldest terminal tasks evicted first.

### 3. Registered Task Planner Tools (7 Tools / 68 Total)

| Tool Name | Risk Level | Description |
|---|---|---|
| `create_task(goal, context)` | `SAFE` | Decomposes a user goal into a validated sequential task plan without executing it. |
| `run_task(task_id, auto_replan)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Sequentially executes the steps of a planned task. |
| `pause_task(task_id, reason)` | `SAFE` | Pauses an in-progress running task cleanly between steps. |
| `resume_task(task_id)` | Dynamic (`SAFE` / `CONFIRMATION_REQUIRED`) | Resumes execution of a paused or confirmation-waiting task. |
| `cancel_task(task_id, reason)` | `SAFE` | Cancels an active or paused task cleanly. |
| `get_task_status(task_id)` | `SAFE` | Inspects detailed status, steps, errors, and execution logs of a task. |
| `list_tasks(status, limit)` | `SAFE` | Lists tasks in memory with optional status filtering. |

### 4. Planner Configuration Options

Configurable in `.env`:

| Setting | Default | Description |
|---|---|---|
| `MAX_TASK_STEPS` | `15` | Maximum steps permitted per task plan |
| `MAX_REPLANS_PER_TASK` | `3` | Maximum automatic replan attempts allowed on failure |
| `MAX_STEP_RETRIES` | `1` | Maximum retries allowed for non-destructive transient step errors |
| `MAX_TASK_CONTEXT_LENGTH` | `4000` | Maximum character length for context strings passed to planner |
| `MAX_ACTIVE_TASKS` | `20` | Maximum in-memory tasks kept in TaskStore before eviction |

---

## Phase 15: Desktop GUI Architecture

Phase 15 introduces a native Windows Desktop GUI built with standard Python `tkinter` and `ttk`. The GUI is strictly an **interface presentation layer** that coordinates with existing backend subsystems (`AIBrain`, `SafetyManager`, `TaskPlanner`, `TaskExecutor`, `MemoryManager`) through non-blocking background workers and a thread-safe UI dispatcher queue.

### 1. Launching the GUI

```powershell
# Launch the CHARVIS Desktop GUI
python main.py --gui

# Or using the shorthand flag
python main.py -g
```

### 2. Key Architecture Components

- **`CharvisApp` (`gui/app.py`)**: Root window coordinator with modern dark theme styling, view switcher, and thread-safe queue polling via `root.after()`.
- **`GUIState` (`gui/state.py`)**: Thread-safe reactive state container with listener subscriptions notifying UI widgets of updates.
- **`GUIController` (`gui/controller.py`)**: Asynchronous coordination layer utilizing a bounded `ThreadPoolExecutor` to offload brain, voice, browser, and task operations without blocking the Tkinter event loop.
- **`ConfirmationDialog` (`gui/widgets/confirmation.py`)**: Modal security dialog wired directly to `SafetyManager.confirmation_callback`. Blocks only the background tool execution worker until the user explicitly clicks Confirm or Cancel.
- **Views**:
  - **Chat (`gui/widgets/chat.py`)**: Rich scrollable conversation transcript displaying user prompts, assistant replies, tool activities, and system alerts.
  - **Task Planner (`gui/widgets/task_panel.py`)**: Real-time progress bar, step-by-step task breakdown, and live controls (Generate Plan, Run, Pause, Resume, Cancel).
  - **Memory Explorer (`gui/widgets/memory_view.py`)**: Strictly read-only viewer for searching and inspecting persistent memories without risk of SQLite DB corruption.
  - **Settings Dashboard (`gui/widgets/settings_view.py`)**: System diagnostic overview, Runtime & Windows Startup controls card, and masked credentials.

---

## Phase 16: Background Runtime & Windows Startup

Phase 16 introduces a safe, controlled background runtime for CHARVIS with optional user-controlled Windows startup integration.

### 1. Launching Background Runtime

```powershell
# Launch the CHARVIS Background Runtime Daemon
python main.py --background

# Or with shorthand flag
python main.py -b

# Launch Background Runtime and attach the Desktop GUI
python main.py --gui --background
```

### 2. Architecture & Authoritative Core

```
Windows / Startup
       │
       ▼
CHARVIS Background Runtime (Daemon)
       │
Runtime Controller (Lifecycle, Health, Heartbeat)
       │
Authoritative CHARVIS Core (AIBrain, ToolRouter, SafetyManager, Memory, Planner)
       ▲
       │ Localhost TCP (127.0.0.1) IPC
Runtime Client
       ▲
       │
Desktop GUI (Tkinter + ttk)
```

- **Single Authoritative Core**: The GUI does NOT duplicate the AI Brain. When a background runtime is active, the GUI automatically connects as an IPC client. When no background runtime exists, the GUI uses a local in-process core or allows the user to click `[Start]` to launch the runtime.
- **Single-Instance Enforcement (`runtime/lifecycle.py`)**: Uses a safe process metadata lockfile under `data/runtime/` recording PID, process creation time, and timestamp. Stale locks from crashed processes are safely detected and recovered without terminating unrelated processes.

### 3. Localhost IPC Communication & Security

- **Strict Localhost Binding**: Bound strictly to `127.0.0.1`. Binding to `0.0.0.0` or any external interface is blocked by policy and raises an immediate security exception.
- **Allowed High-Level Operations**: `status`, `health`, `chat`, `task_create`, `task_run`, `task_pause`, `task_resume`, `task_cancel`, `voice_start`, `voice_stop`, `shutdown`, `ping`.
- **Zero Arbitrary Tool or Code Execution**: The IPC mechanism rejects low-level tool invocation (`execute_tool`, `run_tool`), eval, shell commands, or subprocess execution. All actions must flow through the authoritative AI Brain and Tool Router subject to `SafetyManager` policies.
- **Framing & Limits**: Framed using newline-delimited JSON with an enforced maximum message size limit (default 1MB).

### 4. Explicit Runtime States & Transitions

The runtime state machine (`runtime/state.py`) strictly enforces explicit transitions:
- `STOPPED -> STARTING -> RUNNING -> STOPPING -> STOPPED`
- `RUNNING -> PAUSED -> RUNNING`
- `RUNNING -> DEGRADED -> RUNNING`
- `* -> ERROR -> STOPPING -> STOPPED`

Illegal transitions raise `InvalidStateTransitionError`. Idempotent shutdowns are guaranteed.

### 5. Privacy & Wake-Word Invariants

- **Zero Continuous Listening by Default**: CHARVIS does NOT automatically listen to the microphone merely because background mode is enabled.
- **Wake Word Default = OFF**: Wake-word standby mode remains disabled by default upon background startup. It must be explicitly enabled by the user.
- **No Autonomous Automation**: CHARVIS does not autonomously execute tasks in the background without explicit user request.
- **Zero Stored Audio**: When voice or wake-word is active, audio is processed locally and discarded immediately.

### 6. Transparent Windows Startup Integration

- **User-Controlled**: Windows startup integration is 100% opt-in and requires explicit user action in the GUI or confirmation-required tool call.
- **Startup Folder Method**: Uses a clean, transparent launcher script (`CHARVIS_Startup.bat`) placed in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`.
- **Zero Stealth / Hacks**: Strictly avoids registry Run keys, scheduled tasks, Windows services, or privilege escalation.
- **Safe Command**: Points to static arguments (`python.exe main.py --background`) with no embedded secrets or credentials.

### 7. Registered Runtime Tools (Phases 3–16: 75 Total Tools)

| Tool Name | Risk Level | Description |
|---|---|---|
| `get_runtime_status` | `SAFE` | Inspects background runtime state, version, PID, uptime, and active tasks. |
| `get_runtime_health` | `SAFE` | Inspects operational health across brain, memory, planner, voice, browser, and IPC. |
| `get_startup_status` | `SAFE` | Checks whether Windows startup integration is currently enabled. |
| `stop_runtime` | `CONFIRMATION_REQUIRED` | Gracefully shuts down the background runtime. |
| `restart_runtime` | `CONFIRMATION_REQUIRED` | Gracefully restarts the background runtime. |
| `enable_startup` | `CONFIRMATION_REQUIRED` | Enables CHARVIS to launch automatically in the background on Windows startup. |
| `disable_startup` | `CONFIRMATION_REQUIRED` | Removes CHARVIS from Windows startup. |

### 8. Resource Cleanup & Idempotent Shutdown

On shutdown:
1. Stops accepting new IPC requests.
2. Stops wake-word engine if active and releases microphone handles.
3. Closes Playwright browser automation instances.
4. Flushes SQLite memory storage and closes handles.
5. Releases runtime instance lock cleanly.
6. Closes IPC socket and marks state `STOPPED`.

Calling `stop()` multiple times is idempotent and safe.

### 9. Troubleshooting

- **GUI shows "CHARVIS OFFLINE"**: The background runtime is stopped. Click `[Start]` in the Settings panel or run `python main.py --background`.
- **Stale Lock Recovery**: If CHARVIS crashed unexpectedly, the next start automatically verifies the dead PID and safely recovers stale metadata without affecting unrelated processes.

---

## Phase 17: Hardening, Reliability & Performance

Phase 17 hardens the entire CHARVIS system across reliability, concurrency safety, lifecycle management, IPC robustness, and bounded resource utilization without adding new tools or changing existing security boundaries.

### 1. Key Hardening Improvements

- **Confirmation Race Hardening & Single-Use Enforcement (`core/safety.py`)**:
  - Every confirmation request carries a unique UUID `confirmation_id` with an explicit state machine: `PENDING` -> `APPROVED` | `DENIED` | `EXPIRED` | `CANCELLED`.
  - All secondary transitions or double-clicks are rejected with `ConfirmationStateError`.
  - Stale callbacks from previous tasks or expired actions cannot approve subsequent actions.
- **Bounded Confirmation Timeout**:
  - Configurable `confirmation_timeout_seconds` (default: 120s). Unanswered confirmations transition strictly to `EXPIRED`. Actions never execute on timeout.
- **Task Identity & Execution Hardening (`planner/executor.py`)**:
  - Strict step-by-step verification using unique `task_id` and `step_id`.
  - Enforces max 15 steps, max 3 autonomous replans, max 1 retry for non-destructive transient errors.
  - Destructive tools (`delete_file`, `shutdown_system`, etc.) are never retried automatically.
  - Cancelled, completed, or failed tasks cannot be resumed or re-executed.
- **Localhost IPC Hardening (`runtime/ipc.py`)**:
  - Bound strictly to `127.0.0.1` (refuses `0.0.0.0` or external IPs).
  - Runtime generates a random session token stored only in memory and protected local metadata.
  - Enforced max message size limit (1MB default), bounded concurrent connections (`max_ipc_connections`), socket idle timeout, and request timeouts.
  - Prohibited execution commands (`shell`, `eval`, `exec`, `execute_tool`, `sql`) are rejected with `SAFETY_ERROR`.
- **GUI Reconnection State Machine (`gui/controller.py`)**:
  - Safe lifecycle transitions: `ONLINE -> DISCONNECTED -> RECONNECTING -> ONLINE`.
  - Exponential backoff (1s -> 2s -> 4s -> 8s -> 10s max) using responsive threading events that wake immediately upon manual trigger or app shutdown.
- **Resource Diagnostics & Low-Frequency Monitor (`diagnostics/`)**:
  - Bounded 5–15 second sampling interval without CPU busy-loops.
  - Captures RSS memory, CPU usage, thread count, active workers, active tasks, and IPC connections.
- **Graceful 13-Step Idempotent Shutdown (`runtime/controller.py`)**:
  - Structured shutdown order: mark `STOPPING` -> reject new IPC -> cancel pending confirmations -> stop tasks -> stop voice/wake-word -> close browser -> close IPC -> close memory DB -> release single-instance lock -> mark `STOPPED`.
- **Data Exposure & Secret Sanitization (`logger.py`)**:
  - `SensitiveDataFilter` actively masks passwords, API keys, bearer tokens, PINs, OTPs, session tokens, and private keys across all log outputs.

### 2. Configurable Resource & Safety Limits

| Setting | Default | Description |
|---|---|---|
| `MAX_BACKGROUND_WORKERS` | `4` | Bounded thread pool limit for concurrent background requests |
| `MAX_IPC_CONNECTIONS` | `10` | Maximum simultaneous localhost IPC client connections |
| `RUNTIME_MAX_MESSAGE_SIZE`| `1048576` (1MB) | Maximum allowed byte size for a single incoming IPC message |
| `CONFIRMATION_TIMEOUT_SECONDS` | `120.0` | Timeout after which pending human confirmation auto-expires |
| `MAX_CHAT_HISTORY_ITEMS` | `1000` | Bounded conversation memory history cap |
| `MAX_TASK_HISTORY_ITEMS` | `200` | Bounded completed/failed task execution history cap |
| `MAX_RUNTIME_MEMORY_WARNING_MB` | `500` | Memory threshold triggering diagnostic warnings |
| `RECONNECT_INITIAL_DELAY` | `1.0` | Initial reconnect delay for GUI in seconds |
| `RECONNECT_MAX_DELAY` | `10.0` | Maximum exponential backoff reconnect delay in seconds |
| `WAKE_WORD_ENABLED` | `False` | Wake-word detection remains opt-in and OFF by default |

### 3. Empirical Performance Measurements

Measured on Windows 11 (Intel Core, 16 logical cores, 16GB RAM):

- **Idle CPU**: `1.60%` (Target: < 2.0%)
- **Idle Memory (RSS)**: `88.59 MB`
- **Runtime Startup Time**: `4.96 ms`
- **Runtime Shutdown Time**: `5.02 ms` (Target: < 5.0s)
- **GUI Init Time**: `5.15 ms`
- **Local IPC Status Latency**: `8.32 ms` (Target: < 100 ms)
- **Task Creation Latency**: `0.013 ms`
- **25-Cycle Lifecycle Leak Delta**: `+1.78 MB RSS` (no handle or thread leaks)
- **Continuous Workload Test**: 252 operations completed with 0 errors

### 4. Known Limitations & Watchlist

- Windows console output encoding requires UTF-8 (`PYTHONIOENCODING=utf-8`).
- GUI reconnect backoff caps at 10 seconds; if the background runtime is intentionally terminated, the user can manually restart it from the Settings view.
- Offline and local operations do not touch cloud providers unless explicitly authorized.

---

## Phase 18: Packaging, System Tray & Startup UX

### 1. Windows System Tray Integration
- **Zero-Asset Dynamic Icons**: Programmatically renders 6 distinct high-contrast 64x64 RGBA icons (Ready, Listening, Processing, Paused, Error, Offline) with shape glyphs for colorblind accessibility.
- **Authoritative IPC Binding**: Connects exclusively via `RuntimeClient` or `RuntimeController`. Strictly prohibits direct tool execution from tray menus.
- **8-Item Non-Destructive Menu**:
  1. Open CHARVIS (restores/deiconifies GUI)
  2. Voice Mode (initiates bounded voice interaction)
  3. Wake Word (toggles Phase 9 engine state)
  4. Pause CHARVIS (transitions runtime to PAUSED)
  5. Resume CHARVIS (transitions runtime back to RUNNING)
  6. Runtime Status (emits sanitized desktop notification with uptime and state)
  7. Settings / Diagnosis (brings GUI to settings view)
  8. Exit CHARVIS (authoritative 10-step graceful runtime shutdown)

### 2. Single-Instance Desktop UX & Window Management
- **Single Instance Guarantee**: `RuntimeLock` prevents duplicate background runtime processes. Subsequent launches of `main.py --tray` or `main.py --gui` discover and attach to the existing running instance.
- **Window Minimize-to-Tray**: Closing the desktop GUI window withdraws/hides the window without terminating background runtime tasks or AI orchestration.
- **Explicit Exit Separation**: Window close is decoupled from application termination. Terminating CHARVIS requires an explicit user action via the tray menu.

### 3. User Activation & Keyboard Foundation
- **Activation Orchestration**: `ActivationManager` coordinates user interaction state machine (`INACTIVE`, `ACTIVATING`, `LISTENING`, `PROCESSING`, `COMPLETED`, `CANCELLED`, `ERROR`).
- **Safe Global Hotkey (`Ctrl + Alt + Space`)**: Native Windows `RegisterHotKey` implementation without third-party keylogger libraries. Never logs, monitors, or intercepts arbitrary keyboard input. Disabled by default for user safety.
- **Voice & Wake Word Reuse**: Reuses Phase 8 STT/TTS and Phase 9 wake-word engines directly without creating duplicate engines or background tasks.

### 4. Sanitized Desktop Notifications & Path Portability
- **Sensitive Data Redaction**: Desktop notifications scrub API keys (`sk-...`), passwords, session tokens, and PINs via `SensitiveDataFilter`.
- **Anti-Spam Debouncing**: Throttles rapid notification bursts across identical notification categories.
- **Centralized Path Resolver**: `core/paths.py` eliminates all developer-specific hardcoded paths (e.g. `C:\Charan\Charvis`), enabling seamless execution from Windows Startup, arbitrary working directories, and future package installers.

---

## Phase 19: Activation Experience & Assistant UI

Phase 19 delivers a unified, premium desktop activation pipeline and interactive assistant surface:

### 1. Unified Activation Pipeline
- **Four Cohesive Activation Sources**: Wake word (`"Hey Charvis"`), Global Hotkey (`Ctrl+Alt+Space`), GUI Assistant Button, and System Tray Voice Mode all route to a single authoritative `ActivationManager`.
- **State Machine**: Fully deterministic transitions (`INACTIVE` → `ACTIVATING` → `LISTENING` → `PROCESSING` → `SPEAKING` → `COMPLETED` / `CANCELLED` / `ERROR`).
- **Concurrent Activation Protection**: Rejects or ignores duplicate activation triggers while already listening, processing, or speaking.
- **Audio Clean-up & Graceful Cancellation**: Audio capture can be cancelled mid-stream without lingering background threads or orphaned recording handles.

### 2. Dedicated Assistant View & Visual Status Orb
- **Dynamic Visual Orb**: Real-time pulsing orb indicator reflecting current assistant status:
  - Cyan: Idle / Inactive
  - Yellow: Activating & Readying Voice
  - Red / Orange: Listening
  - Purple: Processing AI Brain & Planner
  - Green: Speaking TTS Response
- **Full Privacy & Secret Redaction**: Transcript cards immediately redact API keys, bearer tokens, passwords, and sensitive strings before rendering on screen.
- **Multi-Step Planner Progress**: Shows real-time progress for complex multi-step execution plans directly in the Assistant deck.
- **Compact Floating Overlay Mode**: Toggleable compact mode with always-on-top positioning (`toggle_compact_mode`) for minimal screen footprint while keeping CHARVIS accessible.
- **Safety Manager Single-Use Confirmations**: Confirmation prompts remain strictly tied to `SafetyManager` single-use tokens; assistant UI cannot bypass or reuse authorization.

---

## Running Automated Tests

Run the complete test suite:

```powershell
pytest -v
```

**671 passed, 1 skipped across all subsystems (100% pass rate).**
- Comprehensive coverage across all 19 phases: Foundation, AI Brain, Tool Router, App Control, Safety Hardening, Mouse/Keyboard, Filesystem, System Control, Voice I/O, Wake Word, Browser, Screenshot & OCR, Vision Understanding, Memory System, Multi-Step Task Planner, Desktop GUI, Background Runtime & Startup, Hardening & Diagnostics, Packaging/System Tray/Startup UX, and Activation Experience & Assistant UI.
- 100% regression safety across all 75 registered tools.
- Offline mocks allow instant, deterministic test execution without hardware or cloud dependencies.



