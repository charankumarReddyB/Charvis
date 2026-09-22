"""Tests for Wake-Word Detector Subsystem (Phase 9).

Verifies normalization, phrase matching, case-insensitivity, rejection of invalid phrases,
lifecycle control (start/stop), and offline frame processing without cloud interaction.
"""

import pytest

from wakeword.detector import (
    BaseWakeWordDetector,
    LocalKeywordDetector,
    MockWakeWordDetector,
    normalize_wake_phrase,
)


def test_wake_word_normalization() -> None:
    """Verify phrase normalization strips whitespace, collapses spaces, and removes trailing punctuation."""
    assert normalize_wake_phrase("  hey   charvis  ") == "hey charvis"
    assert normalize_wake_phrase("Hey CHARVIS!") == "hey charvis"
    assert normalize_wake_phrase("HEY   CHARVIS???") == "hey charvis"
    assert normalize_wake_phrase("hey, charvis,") == "hey charvis"
    assert normalize_wake_phrase("") == ""
    assert normalize_wake_phrase("   ") == ""


def test_wake_word_case_insensitive_detection() -> None:
    """Verify case-insensitive detection accepts varying capitalizations."""
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    detector.start()

    # Audio frames containing encoded text representation
    assert detector.detect(b"TEXT:hey charvis") is True
    assert detector.detect(b"TEXT:Hey CHARVIS") is True
    assert detector.detect(b"TEXT:HEY CHARVIS") is True
    assert detector.detect(b"TEXT:  hEy   ChArViS  ") is True


def test_wake_word_rejection_of_incorrect_phrases() -> None:
    """Verify incorrect keywords or greetings are rejected."""
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    detector.start()

    assert detector.detect(b"TEXT:hey computer") is False
    assert detector.detect(b"TEXT:hello assistant") is False
    assert detector.detect(b"TEXT:alexa") is False
    assert detector.detect(b"TEXT:siri") is False
    assert detector.detect(b"TEXT:hey siri") is False
    assert detector.detect(b"TEXT:good morning") is False


def test_detector_start_and_stop_lifecycle() -> None:
    """Verify start() and stop() properly manage detector running state."""
    detector = LocalKeywordDetector(wake_phrase="hey charvis")
    assert detector.is_running() is False

    detector.start()
    assert detector.is_running() is True

    detector.stop()
    assert detector.is_running() is False


def test_stopped_detector_rejects_detection() -> None:
    """Verify that a stopped detector always returns False regardless of frame."""
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    detector.queue_detection(True)

    assert detector.is_running() is False
    # When not running, detect must return False
    assert detector.detect(b"TEXT:hey charvis") is False


def test_mock_detector_queueing_and_frame_tracking() -> None:
    """Verify MockWakeWordDetector allows deterministic queueing and frame history inspection."""
    detector = MockWakeWordDetector(wake_phrase="hey charvis")
    detector.start()

    detector.queue_detections([False, True, False])
    frame1 = b"frame_1"
    frame2 = b"frame_2"
    frame3 = b"frame_3"

    assert detector.detect(frame1) is False
    assert detector.detect(frame2) is True
    assert detector.detect(frame3) is False

    assert detector.frames_received == [frame1, frame2, frame3]

    detector.clear_history()
    assert detector.frames_received == []


def test_local_keyword_detector_empty_and_corrupt_frames_handled_gracefully() -> None:
    """Verify LocalKeywordDetector handles empty, short, or invalid frames without exceptions."""
    detector = LocalKeywordDetector(wake_phrase="hey charvis")
    detector.start()

    # Empty frame
    assert detector.detect(b"") is False
    # Short noise frame
    assert detector.detect(b"abc") is False
    # Random bytes
    assert detector.detect(b"\x00" * 200) is False

    detector.stop()


def test_base_detector_cannot_be_instantiated_directly() -> None:
    """Verify BaseWakeWordDetector is an abstract class."""
    with pytest.raises(TypeError):
        BaseWakeWordDetector()
