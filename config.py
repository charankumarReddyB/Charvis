"""
Configuration management for CHARVIS.
Uses pydantic-settings to validate and manage environment variables safely.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the CHARVIS project
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    app_name: str = Field(default="CHARVIS", description="Application display name")
    app_version: str = Field(default="0.15.0", description="Application semantic version")

    environment: Literal["development", "testing", "production"] = Field(
        default="development", description="Runtime environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Logging
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    log_file_path: Path = Field(
        default=BASE_DIR / "data" / "logs" / "charvis.log",
        description="Path to log file output",
    )

    # AI Provider Settings (Phase 2)
    ai_provider: str = Field(default="openai", description="Active AI provider")
    ai_model: str = Field(default="gpt-4o-mini", description="Model name to use")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    openai_base_url: Optional[str] = Field(default=None, description="Custom OpenAI compatible endpoint URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=1024, ge=1, description="Maximum tokens for model response")
    request_timeout: float = Field(default=30.0, gt=0.0, description="Request timeout in seconds")
    system_prompt: Optional[str] = Field(default=None, description="Optional custom system prompt override")

    # Computer Control Settings (Phase 5)
    max_type_length: int = Field(
        default=1000, ge=1, le=10000, description="Maximum characters allowed in a single type_text call"
    )
    max_scroll_amount: int = Field(
        default=100, ge=1, le=1000, description="Maximum scroll clicks allowed in a single scroll call"
    )
    pyautogui_failsafe: bool = Field(
        default=True, description="Enable PyAutoGUI fail-safe emergency corner stop"
    )

    # Filesystem Settings (Phase 6)
    filesystem_workspace: Path = Field(
        default=BASE_DIR / "data" / "workspace",
        description="Path to allowed sandbox root directory",
    )
    max_file_read_size: int = Field(
        default=1_048_576, ge=1024, le=52_428_800, description="Maximum bytes allowed for file reading (default 1MB)"
    )
    max_file_write_size: int = Field(
        default=1_048_576, ge=1024, le=52_428_800, description="Maximum bytes allowed for file writing (default 1MB)"
    )
    max_search_results: int = Field(
        default=100, ge=1, le=1000, description="Maximum search results returned"
    )
    max_directory_entries: int = Field(
        default=200, ge=1, le=2000, description="Maximum directory listing entries returned"
    )

    # System Information & Control Settings (Phase 7)
    system_drive: str = Field(
        default="C:\\",
        description="Configured system drive path for disk metrics (e.g. 'C:\\')",
    )

    # Voice Input & Output Settings (Phase 8)
    voice_enabled: bool = Field(default=True, description="Enable voice input and output subsystems")
    stt_provider: str = Field(default="google", description="Speech-to-text provider (google, openai, mock)")
    tts_provider: str = Field(default="pyttsx3", description="Text-to-speech provider (pyttsx3, openai, mock)")
    stt_language: str = Field(default="en-US", description="Language code for speech recognition")
    listen_timeout: float = Field(default=5.0, gt=0.0, le=60.0, description="Seconds to wait before speech begins")
    phrase_timeout: float = Field(default=10.0, gt=0.0, le=120.0, description="Maximum duration in seconds for a single phrase")
    max_tts_length: int = Field(default=1000, ge=10, le=10000, description="Maximum characters allowed for text-to-speech")
    
    # Wake Word Settings (Phase 9)
    wake_word_phrase: str = Field(default="hey charvis", description="Wake word activation phrase")
    wake_word_timeout: float = Field(default=30.0, gt=0.0, le=3600.0, description="Standby session timeout in seconds")
    wake_word_frame_duration: float = Field(default=1.0, gt=0.1, le=5.0, description="Duration in seconds of each audio frame chunk")
    command_listen_timeout: float = Field(default=5.0, gt=0.5, le=30.0, description="Seconds to wait for command speech after wake-word detection")
    wake_word_detector_type: str = Field(default="local", description="Wake word detector backend: local, mock")

    # Browser Automation Settings (Phase 10)
    browser_navigation_timeout: float = Field(
        default=30.0, gt=1.0, le=120.0, description="Timeout in seconds for page navigation"
    )
    browser_action_timeout: float = Field(
        default=10.0, gt=0.5, le=60.0, description="Timeout in seconds for locator actions (click, type)"
    )
    browser_page_text_limit: int = Field(
        default=4000, ge=100, le=50000, description="Maximum characters of visible page text returned to LLM"
    )
    browser_headless: bool = Field(
        default=False, description="Run browser in headless mode (False = user can see browser window)"
    )
    browser_user_data_dir: Path = Field(
        default=BASE_DIR / "data" / "browser_profile",
        description="Path to isolated browser user data directory",
    )

    # Vision & OCR Settings (Phase 11)
    ocr_provider_type: str = Field(
        default="tesseract", description="OCR provider type: tesseract, mock"
    )
    tesseract_cmd: Optional[str] = Field(
        default=None, description="Optional custom executable path for Tesseract OCR"
    )
    max_screenshot_width: int = Field(
        default=7680, ge=100, le=15360, description="Maximum allowed screenshot width in pixels"
    )
    max_screenshot_height: int = Field(
        default=4320, ge=100, le=8640, description="Maximum allowed screenshot height in pixels"
    )
    max_region_area: int = Field(
        default=33_177_600, ge=100, description="Maximum region area in pixels (width * height)"
    )
    max_ocr_text_length: int = Field(
        default=4000, ge=50, le=50000, description="Maximum characters of OCR text returned to LLM"
    )
    ocr_confidence_threshold: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Minimum confidence score threshold for OCR blocks"
    )
    screenshot_save_dir: Path = Field(
        default=BASE_DIR / "data" / "workspace",
        description="Directory for saving screenshots (must reside in sandbox)",
    )

    # Vision & Screen Understanding Settings (Phase 12)
    vision_cloud_enabled: bool = Field(
        default=False,
        description="Explicit user authorization required to transmit screenshots to external cloud vision APIs",
    )
    vision_provider_type: str = Field(
        default="local",
        description="Vision understanding provider: local, mock, openai",
    )
    vision_model: str = Field(
        default="gpt-4o-mini",
        description="Multimodal model identifier when cloud vision is enabled",
    )
    vision_timeout: float = Field(
        default=30.0,
        gt=1.0,
        le=120.0,
        description="Timeout in seconds for vision analysis requests",
    )
    max_screen_elements: int = Field(
        default=50,
        ge=5,
        le=500,
        description="Maximum number of detected UI elements returned in screen description",
    )
    max_element_label_length: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Maximum characters allowed for an element label",
    )
    max_screen_summary_length: int = Field(
        default=1000,
        ge=50,
        le=5000,
        description="Maximum characters allowed for human-readable screen summary",
    )

    # Memory System Settings (Phase 13)
    memory_enabled: bool = Field(
        default=True,
        description="Enable/disable CHARVIS memory subsystem",
    )
    memory_db_path: Path = Field(
        default=BASE_DIR / "data" / "memory" / "charvis_memory.db",
        description="Path to SQLite memory database",
    )
    max_memory_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of retrieved memories per query",
    )
    max_memory_key_length: int = Field(
        default=100,
        ge=5,
        le=200,
        description="Maximum characters allowed for a memory key",
    )
    max_memory_value_length: int = Field(
        default=2000,
        ge=50,
        le=10000,
        description="Maximum characters allowed for a memory value",
    )
    max_memory_tags: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum tags allowed per memory item",
    )
    default_memory_confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Default confidence score for created memories",
    )
    min_retrieval_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score threshold for memory retrieval",
    )

    # Task Planner Settings (Phase 14)
    max_task_steps: int = Field(
        default=15,
        ge=1,
        le=30,
        description="Maximum allowed sequential steps in a generated task plan",
    )
    max_replans_per_task: int = Field(
        default=3,
        ge=0,
        le=5,
        description="Maximum autonomous replans allowed per task",
    )
    max_step_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Maximum retry attempts for transient tool failures",
    )
    max_task_context_length: int = Field(
        default=4000,
        ge=500,
        le=10000,
        description="Maximum character length of task history context sent to LLM",
    )
    max_active_tasks: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Maximum active in-memory task records retained in process",
    )

    # GUI Settings (Phase 15)
    gui_window_title: str = Field(default="CHARVIS", description="Title for GUI main window")
    gui_window_width: int = Field(default=1020, ge=600, le=3840, description="Default GUI window width")
    gui_window_height: int = Field(default=720, ge=400, le=2160, description="Default GUI window height")
    gui_theme: str = Field(default="dark", description="Default GUI theme: 'dark' or 'light'")
    gui_poll_interval_ms: int = Field(default=50, ge=10, le=500, description="Event queue polling interval in ms")


    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_val = value.strip().upper()
        if upper_val not in valid_levels:
            raise ValueError(f"Invalid log_level '{value}'. Must be one of: {', '.join(sorted(valid_levels))}")
        return upper_val

    @field_validator("log_file_path", mode="before")
    @classmethod
    def resolve_log_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @field_validator("filesystem_workspace", mode="before")
    @classmethod
    def resolve_workspace_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("browser_user_data_dir", mode="before")
    @classmethod
    def resolve_browser_user_data_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("screenshot_save_dir", mode="before")
    @classmethod
    def resolve_screenshot_save_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("memory_db_path", mode="before")
    @classmethod
    def resolve_memory_db_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_api_key_configured(self) -> bool:
        """Check if an API key is configured for the active AI provider."""
        if self.ai_provider.lower() == "openai":
            return bool(self.openai_api_key and self.openai_api_key.strip())
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
