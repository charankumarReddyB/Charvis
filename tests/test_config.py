"""
Unit tests for CHARVIS configuration management (Phase 1 & Phase 2).
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from config import Settings, get_settings


def test_default_settings():
    """Verify default configuration attributes."""
    settings = Settings()
    assert settings.app_name == "CHARVIS"
    assert settings.app_version in {"0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.8.0", "0.9.0", "0.10.0", "0.11.0", "0.12.0", "0.13.0", "0.14.0", "0.15.0"}
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert str(settings.log_file_path).endswith("charvis.log")
    # Phase 2 defaults
    assert settings.ai_provider == "openai"
    assert settings.ai_model == "gpt-4o-mini"
    assert settings.openai_api_key is None
    assert settings.temperature == 0.7
    assert settings.max_tokens == 1024
    assert settings.request_timeout == 30.0
    assert settings.is_api_key_configured is False
    # Phase 5 defaults
    assert settings.max_type_length == 1000
    assert settings.max_scroll_amount == 100
    assert settings.pyautogui_failsafe is True
    # Phase 6 defaults
    assert str(settings.filesystem_workspace).endswith("workspace")
    assert settings.max_file_read_size == 1_048_576
    assert settings.max_file_write_size == 1_048_576
    assert settings.max_search_results == 100
    assert settings.max_directory_entries == 200
    # Phase 7 defaults
    assert settings.system_drive == "C:\\"
    # Phase 8 defaults
    assert settings.voice_enabled is True
    assert settings.stt_provider == "google"
    assert settings.tts_provider == "pyttsx3"
    assert settings.stt_language == "en-US"
    assert settings.listen_timeout == 5.0
    assert settings.phrase_timeout == 10.0
    assert settings.max_tts_length == 1000
    # Phase 9 defaults
    assert settings.wake_word_phrase == "hey charvis"
    assert settings.wake_word_timeout == 30.0
    assert settings.wake_word_frame_duration == 1.0
    assert settings.command_listen_timeout == 5.0
    # Phase 10 defaults
    assert settings.browser_navigation_timeout == 30.0
    assert settings.browser_action_timeout == 10.0
    assert settings.browser_page_text_limit == 4000
    assert settings.browser_headless is False
    assert str(settings.browser_user_data_dir).endswith("browser_profile")
    # Phase 11 defaults
    assert settings.ocr_provider_type == "tesseract"
    assert settings.tesseract_cmd is None
    assert settings.max_screenshot_width == 7680
    assert settings.max_screenshot_height == 4320
    assert settings.max_region_area == 33_177_600
    assert settings.max_ocr_text_length == 4000
    assert settings.ocr_confidence_threshold == 0.0
    assert str(settings.screenshot_save_dir).endswith("workspace")


def test_log_level_validation_success():
    """Ensure valid log levels in any case are normalized to uppercase."""
    for level in ["debug", "INFO", "Warning", "error", "critical"]:
        settings = Settings(log_level=level)
        assert settings.log_level == level.upper()


def test_log_level_validation_failure():
    """Ensure invalid log level raises ValidationError."""
    with pytest.raises(ValidationError):
        Settings(log_level="SUPER_VERBOSE")


def test_environment_override(monkeypatch):
    """Ensure environment variables correctly override default settings."""
    monkeypatch.setenv("APP_NAME", "CHARVIS_TEST")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("AI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock-key-12345")
    monkeypatch.setenv("TEMPERATURE", "0.2")

    settings = Settings()
    assert settings.app_name == "CHARVIS_TEST"
    assert settings.debug is True
    assert settings.log_level == "DEBUG"
    assert settings.environment == "testing"
    assert settings.ai_model == "gpt-4o"
    assert settings.openai_api_key == "sk-test-mock-key-12345"
    assert settings.temperature == 0.2
    assert settings.is_api_key_configured is True


def test_api_key_configured_property():
    """Test is_api_key_configured property detection."""
    settings_no_key = Settings(openai_api_key=None)
    assert settings_no_key.is_api_key_configured is False

    settings_empty_key = Settings(openai_api_key="   ")
    assert settings_empty_key.is_api_key_configured is False

    settings_with_key = Settings(openai_api_key="sk-real-format-key")
    assert settings_with_key.is_api_key_configured is True


def test_custom_log_path():
    """Ensure custom log paths resolve correctly."""
    settings = Settings(log_file_path="custom/path.log")
    assert isinstance(settings.log_file_path, Path)
    assert settings.log_file_path.is_absolute()
    assert str(settings.log_file_path).endswith("custom\\path.log") or str(
        settings.log_file_path
    ).endswith("custom/path.log")


def test_get_settings_caching():
    """Ensure get_settings returns the singleton cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_memory_settings():
    """Ensure Phase 13 memory settings load with valid defaults."""
    settings = Settings()
    assert settings.memory_enabled is True
    assert settings.memory_db_path.is_absolute()
    assert str(settings.memory_db_path).endswith("charvis_memory.db")
    assert settings.max_memory_results == 10
    assert settings.max_memory_key_length == 100
    assert settings.max_memory_value_length == 2000
    assert settings.max_memory_tags == 10
    assert settings.default_memory_confidence == 0.9
    assert settings.min_retrieval_confidence == 0.3


def test_planner_settings():
    """Ensure Phase 14 planner settings load with valid defaults."""
    settings = Settings()
    assert settings.max_task_steps == 15
    assert settings.max_replans_per_task == 3
    assert settings.max_step_retries == 1
    assert settings.max_task_context_length == 4000
    assert settings.max_active_tasks == 20


def test_gui_settings():
    """Ensure Phase 15 GUI settings load with valid defaults."""
    settings = Settings()
    assert settings.gui_window_title == "CHARVIS"
    assert settings.gui_window_width == 1020
    assert settings.gui_window_height == 720
    assert settings.gui_theme == "dark"
    assert settings.gui_poll_interval_ms == 50



