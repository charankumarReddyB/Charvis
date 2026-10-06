"""CHARVIS Wake-Word Engine Subsystem.

Manages assistant standby state, short audio frame processing, wake-word activation,
active listening timeout, STT command handoff, AIBrain processing, and TTS output.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from config import Settings, get_settings
from core.safety import RiskLevel
from logger import get_logger
from voice.audio import AudioCapture, MicrophoneUnavailableError, NoSpeechDetectedError, VoiceError
from voice.stt import BaseSTTProvider, get_stt_provider
from voice.tts import BaseTTSProvider, get_tts_provider
from wakeword.detector import (
    BaseWakeWordDetector,
    LocalKeywordDetector,
    normalize_wake_phrase,
)
from wakeword.states import InvalidStateTransitionError, WakeWordState

if TYPE_CHECKING:
    from core.brain import AIBrain

logger = get_logger(__name__)


class WakeWordEngine:
    """Coordinates standby wake-word monitoring and assistant command lifecycle."""

    # Explicit allowed state transitions
    _ALLOWED_TRANSITIONS: dict[WakeWordState, set[WakeWordState]] = {
        WakeWordState.STOPPED: {WakeWordState.STANDBY},
        WakeWordState.STANDBY: {WakeWordState.LISTENING, WakeWordState.STOPPED, WakeWordState.ERROR},
        WakeWordState.LISTENING: {WakeWordState.PROCESSING, WakeWordState.STANDBY, WakeWordState.STOPPED, WakeWordState.ERROR},
        WakeWordState.PROCESSING: {WakeWordState.SPEAKING, WakeWordState.STOPPED, WakeWordState.ERROR},
        WakeWordState.SPEAKING: {WakeWordState.STANDBY, WakeWordState.STOPPED, WakeWordState.ERROR},
        WakeWordState.ERROR: {WakeWordState.STANDBY, WakeWordState.STOPPED},
    }

    def __init__(
        self,
        brain: Optional[AIBrain] = None,
        detector: Optional[BaseWakeWordDetector] = None,
        audio_capture: Optional[AudioCapture] = None,
        stt_provider: Optional[BaseSTTProvider] = None,
        tts_provider: Optional[BaseTTSProvider] = None,
        settings: Optional[Settings] = None,
        confirmation_callback: Optional[Callable[[str, Dict[str, Any], RiskLevel, Optional[str]], bool]] = None,
        on_wake_detected: Optional[Callable[[], None]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        if brain is None:
            from core.brain import AIBrain
            self.brain = AIBrain()
        else:
            self.brain = brain
        self.detector = detector or LocalKeywordDetector(wake_phrase=self.settings.wake_word_phrase)
        self.audio_capture = audio_capture or AudioCapture()
        self.stt_provider = stt_provider or get_stt_provider()
        self.tts_provider = tts_provider or get_tts_provider()
        self.confirmation_callback = confirmation_callback
        self.on_wake_detected = on_wake_detected

        self._state: WakeWordState = WakeWordState.STOPPED
        self._last_error: Optional[str] = None
        self._activation_response: str = "Yes?"

    @property
    def is_running(self) -> bool:
        """Return True if the engine is running (not in STOPPED state)."""
        return self._state != WakeWordState.STOPPED

    @property
    def _running(self) -> bool:
        return self.is_running

    @_running.setter
    def _running(self, val: bool) -> None:
        if not val:
            self._state = WakeWordState.STOPPED
        else:
            self._state = WakeWordState.STANDBY

    @property
    def state(self) -> WakeWordState:
        """Current engine state."""
        return self._state

    @property
    def last_error(self) -> Optional[str]:
        """Description of the most recent error, if any."""
        return self._last_error

    def transition_to(self, new_state: WakeWordState) -> None:
        """Transition the engine to a new state enforcing valid lifecycle rules.

        Raises:
            InvalidStateTransitionError: If the transition is not allowed.
        """
        allowed = self._ALLOWED_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            err_msg = (
                f"Invalid state transition from '{self._state.value}' to '{new_state.value}'."
            )
            logger.error(err_msg)
            raise InvalidStateTransitionError(err_msg)

        logger.debug("WakeWordEngine state changed: %s -> %s", self._state.value, new_state.value)
        self._state = new_state

    def start(self) -> None:
        """Start the wake-word engine and enter STANDBY mode."""
        if self._state != WakeWordState.STOPPED:
            logger.warning("WakeWordEngine start() called while in state '%s'", self._state.value)
            return

        self.transition_to(WakeWordState.STANDBY)
        self.detector.start()
        logger.info("WakeWordEngine started in STANDBY mode (phrase: '%s')", self.detector.wake_phrase)

    def stop(self) -> None:
        """Stop the wake-word engine and transition to STOPPED."""
        if self._state == WakeWordState.STOPPED:
            return

        try:
            self.detector.stop()
        except Exception as e:
            logger.debug("Exception stopping wake word detector: %s", e)
        self._state = WakeWordState.STOPPED
        logger.info("WakeWordEngine stopped successfully")

    def strip_wake_phrase(self, text: str) -> str:
        """Remove the wake phrase from the beginning of user speech.

        Example:
            "Hey CHARVIS, open notepad" -> "open notepad"
            "hey charvis what is cpu usage" -> "what is cpu usage"
            "Hey CHARVIS" -> ""
        """
        if not text:
            return ""

        wake_phrase = self.detector.wake_phrase
        cleaned = text.strip()

        # Check if text starts with wake phrase case-insensitively
        pattern = rf"^\s*{re.escape(wake_phrase)}[\s,\.!\?]*"
        remainder = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return remainder

    def process_frame(self, frame: bytes) -> bool:
        """Process a single short audio frame.

        Returns:
            bool: True if wake word was detected and handled, False otherwise.
        """
        if self._state != WakeWordState.STANDBY:
            return False

        if not self.detector.detect(frame):
            return False

        logger.info("Wake word detected in audio frame")
        if self.on_wake_detected is not None:
            try:
                self.on_wake_detected()
            except Exception as cb_err:
                logger.error("Error in on_wake_detected callback: %s", cb_err)
            return True

        self.handle_wake_detection()
        return True

    def handle_wake_detection(self) -> Optional[str]:
        """Execute the active listening and command processing lifecycle.

        Flow:
            STANDBY -> LISTENING (Cue: 'Yes?') -> PROCESSING (STT + Brain) -> SPEAKING (TTS) -> STANDBY
        """
        try:
            # 1. STANDBY -> LISTENING
            self.transition_to(WakeWordState.LISTENING)

            # Provide clear activation cue
            try:
                self.tts_provider.speak(self._activation_response)
            except Exception as tts_err:
                logger.warning("Activation cue TTS failed: %s", tts_err)

            # 2. Capture user command with timeout
            command_text = self._listen_for_command()

            if not command_text:
                logger.info("No command speech received within timeout; returning to STANDBY")
                self.transition_to(WakeWordState.STANDBY)
                return None

            # 3. LISTENING -> PROCESSING
            self.transition_to(WakeWordState.PROCESSING)
            logger.info("Processing command: '%s'", command_text)

            response = self.brain.process_user_message(
                user_input=command_text,
                confirmation_callback=self.confirmation_callback,
            )

            # 4. PROCESSING -> SPEAKING
            self.transition_to(WakeWordState.SPEAKING)
            try:
                self.tts_provider.speak(response)
            except Exception as tts_err:
                logger.warning("Command response TTS failed: %s", tts_err)

            # 5. SPEAKING -> STANDBY
            self.transition_to(WakeWordState.STANDBY)
            return response

        except Exception as err:
            self._last_error = str(err)
            logger.exception("Error during wake-word command cycle: %s", err)
            try:
                self.transition_to(WakeWordState.ERROR)
            except Exception:
                pass
            # Safely return to STANDBY from ERROR
            try:
                self.transition_to(WakeWordState.STANDBY)
            except Exception:
                self._state = WakeWordState.STANDBY
            return None

    def _listen_for_command(self) -> str:
        """Listen for the user's spoken command using bounded STT."""
        timeout = float(self.settings.command_listen_timeout)
        try:
            audio_bytes = self.audio_capture.record_audio(
                duration=timeout,
            )
            raw_text = self.stt_provider.transcribe(
                audio_bytes,
                language=self.settings.stt_language,
            )
            clean_command = self.strip_wake_phrase(raw_text)
            return clean_command
        except (NoSpeechDetectedError, VoiceError) as speech_err:
            logger.debug("Command listening finished with no speech or error: %s", speech_err)
            return ""
        except Exception as err:
            logger.warning("Unexpected error while recording command: %s", err)
            return ""

    def run_standby_loop(self, max_iterations: Optional[int] = None) -> None:
        """Run the standby monitoring loop, capturing short audio frames until stopped.

        Args:
            max_iterations: Optional loop limit (primarily for testing).
        """
        self.start()
        frame_duration = float(self.settings.wake_word_frame_duration)
        iterations = 0

        logger.info("WakeWordEngine standby loop active. Listening for '%s'...", self.detector.wake_phrase)

        try:
            while self._state != WakeWordState.STOPPED:
                if max_iterations is not None and iterations >= max_iterations:
                    break

                iterations += 1

                # Capture short audio frame locally in memory
                try:
                    frame = self.audio_capture.record_audio(duration=frame_duration)
                    self.process_frame(frame)
                except MicrophoneUnavailableError:
                    logger.error("Microphone unavailable during wake-word standby")
                    self.transition_to(WakeWordState.ERROR)
                    break
                except KeyboardInterrupt:
                    raise
                except Exception as err:
                    logger.debug("Frame capture/processing cycle exception: %s", err)
                    time.sleep(0.1)

        finally:
            self.stop()
