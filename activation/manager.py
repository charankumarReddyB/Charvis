"""
Central Activation Manager for CHARVIS (Phase 18).
Orchestrates voice interaction, wake-word activation, and hotkey entry points
by delegating to existing Phase 8 (Voice), Phase 9 (Wake-Word), and Phase 2 (AIBrain)
subsystems without duplicating brain logic or executing tools directly.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Callable, Dict, List, Optional

from activation.hotkey import GlobalHotkeyManager
from activation.models import (
    ActivationSession,
    ActivationSource,
    ActivationState,
    ActivationStateError,
)
from core.notifications import NotificationType, get_notification_service
from logger import get_logger

logger = get_logger("CHARVIS.Activation.Manager")


class ActivationManager:
    """
    Central coordinator for interactive user activations.
    Ensures safe lifecycle transitions, updates listeners (Tray/GUI),
    and strictly enforces human-in-the-loop safety boundaries.
    """

    def __init__(
        self,
        brain: Optional[Any] = None,
        wake_word_engine: Optional[Any] = None,
        runtime_client: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        hotkey_enabled: bool = False,
        confirmation_callback: Optional[Callable[..., bool]] = None,
    ) -> None:
        self.brain = brain or (runtime_controller.brain if runtime_controller and hasattr(runtime_controller, "brain") else None)
        self.runtime_client = runtime_client
        self.runtime_controller = runtime_controller
        self.wake_word_engine = wake_word_engine
        self._confirmation_callback = confirmation_callback
        self._current_session: Optional[ActivationSession] = None
        self._listeners: List[Callable[[ActivationSession], None]] = []
        self._lock = threading.RLock()
        self._cancel_event = threading.Event()
        self._active_capture: Optional[Any] = None
        self._active_tts: Optional[Any] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="CharvisActivation")
        self._notification_service = get_notification_service()

        # Global hotkey integration
        self.hotkey_manager = GlobalHotkeyManager(
            on_trigger=lambda: self.request_activation(ActivationSource.HOTKEY),
            enabled=hotkey_enabled,
        )

    def set_confirmation_callback(self, callback: Optional[Callable[..., bool]]) -> None:
        """Configure confirmation handler for safety-sensitive actions."""
        self._confirmation_callback = callback

    def _redact_secrets(self, text: Optional[str]) -> str:
        """Sanitize secrets, passwords, tokens, and keys from display text."""
        if not text:
            return ""
        from logger import SensitiveDataFilter
        data_filter = SensitiveDataFilter()
        sanitized = text
        for pattern, replacement in data_filter.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @property
    def is_active(self) -> bool:
        """True if an activation session is currently running."""
        with self._lock:
            return self._current_session is not None and not self._current_session.is_terminal

    def activate(
        self,
        source: ActivationSource = ActivationSource.HOTKEY,
        prompt_cue: bool = False,
    ) -> ActivationSession:
        """Alias for request_activation."""
        return self.request_activation(source=source, prompt_cue=prompt_cue)

    @property
    def current_state(self) -> ActivationState:
        """Return the current activation state."""
        with self._lock:
            return self._current_session.state if self._current_session else ActivationState.INACTIVE

    @property
    def current_session(self) -> Optional[ActivationSession]:
        """Return the active activation session snapshot."""
        with self._lock:
            return self._current_session

    def add_listener(self, listener: Callable[[ActivationSession], None]) -> None:
        """Subscribe a callback to state change notifications."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ActivationSession], None]) -> None:
        """Unsubscribe a callback from state change notifications."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(self, session: ActivationSession) -> None:
        """Dispatch state updates to registered UI/Tray observers."""
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(session)
            except Exception as e:
                logger.debug("Error in activation listener: %s", e)

    def request_activation(
        self,
        source: ActivationSource = ActivationSource.HOTKEY,
        prompt_cue: bool = False,
    ) -> ActivationSession:
        """
        Request a new user activation session.
        Enforces single-activation concurrency; ignores duplicate requests if active.
        """
        with self._lock:
            if self._current_session and not self._current_session.is_terminal:
                logger.info(
                    "Activation already active (state=%s); ignoring duplicate request from '%s'.",
                    self._current_session.state.value,
                    source.value,
                )
                return self._current_session

            self._cancel_event.clear()
            session = ActivationSession(source=source, state=ActivationState.ACTIVATING)
            self._current_session = session
            logger.info("Activation requested from source '%s' (session_id=%s)", source.value, session.session_id)

        self._notification_service.notify(
            title="CHARVIS",
            message="CHARVIS is ready and listening...",
            notification_type=NotificationType.LISTENING,
        )
        self._notify_listeners(session)

        # Launch background voice interaction loop
        self._executor.submit(self._run_voice_interaction, session, prompt_cue)
        return session

    def cancel_activation(self, reason: str = "User cancelled") -> Optional[ActivationSession]:
        """Safely cancel an active activation session and release audio resources."""
        self._cancel_event.set()

        # Stop active microphone or TTS immediately
        if self._active_capture is not None:
            try:
                self._active_capture.stop()
            except Exception as e:
                logger.debug("Notice stopping capture on cancel: %s", e)

        if self._active_tts is not None and hasattr(self._active_tts, "stop"):
            try:
                self._active_tts.stop()
            except Exception as e:
                logger.debug("Notice stopping TTS on cancel: %s", e)

        with self._lock:
            if not self._current_session or self._current_session.is_terminal:
                return self._current_session

            try:
                self._current_session.transition_to(ActivationState.CANCELLED, error=reason)
            except ActivationStateError:
                pass
            session = self._current_session
            logger.info("Activation cancelled: %s", reason)

        self._notify_listeners(session)
        self._cleanup_session()
        return session

    def _cleanup_session(self) -> None:
        """Reset current active session reference."""
        with self._lock:
            self._current_session = None

    def _run_voice_interaction(self, session: ActivationSession, prompt_cue: bool = False) -> None:
        """Background worker executing voice speech recognition and AI processing."""
        try:
            # 1. Transition to LISTENING
            with self._lock:
                if session != self._current_session or session.state == ActivationState.CANCELLED:
                    return
                session.transition_to(ActivationState.LISTENING)
            self._notify_listeners(session)

            # Optional audible prompt cue (e.g. for wake-word activation)
            if prompt_cue or session.source == ActivationSource.WAKE_WORD:
                try:
                    from voice.tts import get_tts_provider
                    tts = get_tts_provider()
                    tts.speak("Yes?")
                except Exception as cue_err:
                    logger.debug("Prompt cue playback notice: %s", cue_err)

            # 2. Capture voice input via Phase 8 AudioCapture and STT
            user_text = ""
            try:
                from config import get_settings
                from voice.audio import AudioCapture
                from voice.stt import get_stt_provider

                settings = get_settings()
                capture = AudioCapture()
                self._active_capture = capture
                stt = get_stt_provider()

                duration = float(getattr(settings, "command_listen_timeout", 5.0))
                audio_data = capture.record_audio(duration=duration, cancel_event=self._cancel_event)
                if audio_data and not self._cancel_event.is_set():
                    user_text = stt.transcribe(audio_data)
            except Exception as e:
                logger.info("Voice capture or STT notice: %s", e)
                with self._lock:
                    if session == self._current_session and not self._cancel_event.is_set() and not session.is_terminal:
                        try:
                            session.transition_to(ActivationState.ERROR, error=str(e))
                        except Exception:
                            pass
                        self._notify_listeners(session)
                        return
            finally:
                self._active_capture = None

            # 3. If cancelled while listening or terminal
            with self._lock:
                if session != self._current_session or session.is_terminal or self._cancel_event.is_set():
                    return

            # Clean and validate transcribed text
            if session.source == ActivationSource.WAKE_WORD and self.wake_word_engine:
                user_text = self.wake_word_engine.strip_wake_phrase(user_text)

            clean_text = user_text.strip() if user_text else ""
            if not clean_text:
                logger.info("No speech recognized during activation session.")
                with self._lock:
                    if session.is_terminal or self._cancel_event.is_set():
                        return
                    session.transition_to(ActivationState.COMPLETED)
                self._notify_listeners(session)
                self._cleanup_session()
                return

            # 4. Transition to PROCESSING with captured command
            redacted_command = self._redact_secrets(clean_text)
            with self._lock:
                if session != self._current_session or session.is_terminal or self._cancel_event.is_set():
                    return
                session.command_text = redacted_command
                session.transition_to(ActivationState.PROCESSING)
            self._notify_listeners(session)
            logger.info("Processing user speech command: '%s'", redacted_command)

            # 5. Delegate command to authoritative AIBrain / RuntimeClient
            response_text = ""
            if self.runtime_client and self.runtime_client.is_runtime_running():
                response_text = self.runtime_client.send_chat(clean_text)
            else:
                if self.brain is None:
                    from core.brain import AIBrain
                    self.brain = AIBrain()
                if self._confirmation_callback is not None:
                    response_text = self.brain.process_user_message(
                        clean_text,
                        confirmation_callback=self._confirmation_callback,
                    )
                else:
                    response_text = self.brain.process_user_message(clean_text)

            redacted_response = self._redact_secrets(response_text)
            with self._lock:
                session.response_text = redacted_response

            # 6. Speak response via Phase 8 TTS in SPEAKING state
            with self._lock:
                if session != self._current_session or session.is_terminal or self._cancel_event.is_set():
                    return
                session.transition_to(ActivationState.SPEAKING)
            self._notify_listeners(session)

            try:
                from voice.tts import get_tts_provider
                tts = get_tts_provider()
                self._active_tts = tts
                if response_text and not self._cancel_event.is_set():
                    tts.speak(response_text)
            except Exception as e:
                logger.debug("TTS playback notice: %s", e)
            finally:
                self._active_tts = None

            # 7. Transition to COMPLETED
            with self._lock:
                if session != self._current_session or session.is_terminal or self._cancel_event.is_set():
                    return
                session.transition_to(ActivationState.COMPLETED)
            self._notify_listeners(session)

        except Exception as e:
            logger.error("Error during activation session: %s", e)
            with self._lock:
                if session == self._current_session and not session.is_terminal:
                    try:
                        session.transition_to(ActivationState.ERROR, error=str(e))
                    except ActivationStateError:
                        pass
                    self._notify_listeners(session)
        finally:
            self._cleanup_session()

    def enable_wake_word(self) -> bool:
        """Start the existing Phase 9 wake-word detector engine."""
        if self.wake_word_engine is None:
            from wakeword.engine import WakeWordEngine
            self.wake_word_engine = WakeWordEngine(brain=self.brain)

        try:
            self.wake_word_engine.start()
            logger.info("WakeWordEngine activated via ActivationManager.")
            self._notification_service.notify(
                title="CHARVIS",
                message="Wake word listening enabled.",
                notification_type=NotificationType.READY,
            )
            return True
        except Exception as e:
            logger.error("Failed to start WakeWordEngine: %s", e)
            return False

    def disable_wake_word(self) -> bool:
        """Stop the existing Phase 9 wake-word detector engine."""
        stopped = False
        if self.wake_word_engine:
            try:
                self.wake_word_engine.stop()
                stopped = True
            except Exception as e:
                logger.error("Error stopping WakeWordEngine: %s", e)
        try:
            from tools.wakeword import get_active_engine, set_active_engine
            active = get_active_engine()
            if active:
                active.stop()
                set_active_engine(None)
                stopped = True
        except Exception:
            pass
        if stopped:
            logger.info("WakeWordEngine deactivated via ActivationManager.")
            self._notification_service.notify(
                title="CHARVIS",
                message="Wake word listening stopped.",
                notification_type=NotificationType.PAUSED,
            )
        return stopped

    def is_wake_word_running(self) -> bool:
        """Check if wake word engine is currently running."""
        if self.wake_word_engine and getattr(self.wake_word_engine, "is_running", False):
            return True
        try:
            from tools.wakeword import get_active_engine
            active = get_active_engine()
            if active and getattr(active, "is_running", False):
                return True
        except Exception:
            pass
        return False

    def shutdown(self) -> None:
        """Cleanly terminate hotkey listener and background worker threads."""
        self.cancel_activation("Manager shutting down")
        self.hotkey_manager.stop()
        self.disable_wake_word()
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        logger.info("ActivationManager cleanly stopped.")
