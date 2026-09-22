"""
CHARVIS - Charan's AI Virtual Intelligent System
Phase 3: Tool-Calling Architecture Terminal Interface
"""

import platform
import sys
from typing import Any, Dict, Optional

from config import Settings, get_settings
from core.brain import AIBrain
from core.safety import RiskLevel
from logger import get_logger, setup_logging


def print_banner(
    settings_or_name: Optional[object] = None,
    app_version: Optional[str] = None,
    environment: Optional[str] = None,
    tool_count: int = 1,
) -> None:
    """Display the aesthetic ASCII startup banner."""
    if isinstance(settings_or_name, Settings):
        settings = settings_or_name
        app_name = settings.app_name
        version = settings.app_version
        env = settings.environment
        provider = settings.ai_provider.upper()
        model = settings.ai_model
        api_status = (
            "Configured" if settings.is_api_key_configured else "Not Set (Set OPENAI_API_KEY in .env)"
        )
    else:
        app_name = str(settings_or_name) if settings_or_name else "CHARVIS"
        version = app_version or "0.15.0"
        env = environment or "development"
        provider = "OPENAI"
        model = "gpt-4o-mini"
        api_status = "N/A"

    banner = f"""
============================================================
  {app_name} - AI Virtual Intelligent System (v{version})
  Phase 15    : Desktop GUI
  Environment : {env}
  Provider    : {provider} ({model})
  API Key     : {api_status}
  Tools       : {tool_count} active (calc, apps, keyboard, mouse, fs, system, voice, wakeword, browser, vision, memory, planner)
  Platform    : {platform.system()} {platform.release()} ({platform.machine()})
  Commands    : Type 'wakeword' for wake-word mode, 'voice' for voice mode, 'exit' to quit
                Or run with '--gui' to launch Desktop GUI
============================================================
"""
    print(banner)


def cli_confirmation_callback(
    tool_name: str,
    arguments: Dict[str, Any],
    risk_level: RiskLevel,
    custom_message: Optional[str] = None,
) -> bool:
    """Prompt user in terminal for authorization when executing confirmation-required tools."""
    notice = f"  Notice    : {custom_message}\n" if custom_message else ""
    prompt = (
        f"\n[SECURITY CONFIRMATION REQUIRED]\n"
        f"CHARVIS is requesting permission to execute:\n"
        f"  Tool      : {tool_name}\n"
        f"  Arguments : {arguments}\n"
        f"  Risk Level: {risk_level.value}\n"
        f"{notice}"
        f"Proceed? [y/N]: "
    )
    try:
        user_response = input(prompt).strip().lower()
        return user_response in {"y", "yes"}
    except (KeyboardInterrupt, EOFError):
        print("\nConfirmation aborted.")
        return False


def run_voice_mode(brain: AIBrain, settings: Settings) -> None:
    """Controlled, on-demand voice interaction loop."""
    logger = get_logger("CHARVIS.VoiceMode")
    from voice.audio import AudioCapture, MicrophoneUnavailableError, NoSpeechDetectedError
    from voice.stt import get_stt_provider
    from voice.tts import get_tts_provider

    capture = AudioCapture()
    if not capture.is_microphone_available():
        print("\n[Error] No microphone device detected. Voice mode cannot start.\n")
        return

    stt = get_stt_provider()
    tts = get_tts_provider()

    print("\n" + "=" * 60)
    print("CHARVIS Voice Mode Enabled.")
    print("Speak into your microphone when 'Listening...' appears.")
    print("Say 'exit voice mode', 'stop listening', or press Ctrl+C to quit.")
    print("=" * 60 + "\n")

    exit_phrases = {
        "exit voice mode",
        "exit voice",
        "stop listening",
        "exit",
        "quit",
    }

    while True:
        try:
            print("Listening... (Speak now)")
            duration = min(settings.phrase_timeout, 8.0)
            audio_bytes = capture.record_audio(duration=duration)

            try:
                user_text = stt.transcribe(audio_bytes, language=settings.stt_language)
            except NoSpeechDetectedError:
                print("(No speech detected. Listening again...)\n")
                continue

            print(f"You said: {user_text}")

            clean_phrase = user_text.lower().strip().rstrip(".!?")
            if clean_phrase in exit_phrases:
                print("\nCHARVIS: Exiting voice mode. Returning to text interface.\n")
                try:
                    tts.speak("Exiting voice mode.")
                except Exception:
                    pass
                break

            response = brain.process_user_message(
                user_input=user_text,
                confirmation_callback=cli_confirmation_callback,
            )
            print(f"\nCHARVIS: {response}\n")

            try:
                tts.speak(response)
            except Exception as tts_err:
                logger.warning("TTS output failed: %s", tts_err)
                print(f"[Notice] Voice playback issue: {tts_err}")

        except KeyboardInterrupt:
            print("\nVoice mode interrupted. Returning to text CLI.\n")
            break
        except Exception as err:
            logger.exception("Error in voice interaction loop: %s", err)
            print(f"[Voice Error] {err}\n")
            break


def run_wakeword_mode(brain: AIBrain, settings: Settings) -> None:
    """Controlled, local wake-word standby interaction loop."""
    logger = get_logger("CHARVIS.WakeWordMode")
    from voice.audio import AudioCapture
    from voice.stt import get_stt_provider
    from voice.tts import get_tts_provider
    from wakeword.detector import LocalKeywordDetector
    from wakeword.engine import WakeWordEngine
    from tools.wakeword import set_active_engine

    capture = AudioCapture()
    if not capture.is_microphone_available():
        print("\n[Error] No microphone device detected. Wake-word mode cannot start.\n")
        return

    stt = get_stt_provider()
    tts = get_tts_provider()
    detector = LocalKeywordDetector(wake_phrase=settings.wake_word_phrase)
    engine = WakeWordEngine(
        brain=brain,
        detector=detector,
        audio_capture=capture,
        stt_provider=stt,
        tts_provider=tts,
        settings=settings,
        confirmation_callback=cli_confirmation_callback,
    )
    set_active_engine(engine)

    print("\n" + "=" * 60)
    print("Wake-word mode enabled.")
    print(f'Say "{settings.wake_word_phrase.title()}" to activate.')
    print("Say 'stop wakeword' or press Ctrl+C to disable.")
    print("=" * 60 + "\n")

    try:
        engine.start()
        frame_duration = float(settings.wake_word_frame_duration)
        stop_phrases = {"stop wakeword", "disable wakeword", "exit wakeword", "stop wake word", "exit", "quit"}

        while engine.state != engine.state.STOPPED:
            try:
                frame = capture.record_audio(duration=frame_duration)
                if engine.detector.detect(frame):
                    # Wake word triggered
                    engine.transition_to(engine.state.LISTENING)
                    try:
                        tts.speak("Yes?")
                    except Exception:
                        pass
                    print("\n[Wake Word Detected] Listening for command...")

                    # Capture command
                    cmd_audio = capture.record_audio(duration=float(settings.command_listen_timeout))
                    try:
                        cmd_text = stt.transcribe(cmd_audio, language=settings.stt_language)
                    except Exception:
                        cmd_text = ""

                    clean_cmd = engine.strip_wake_phrase(cmd_text)
                    if not clean_cmd:
                        print("(No command heard. Returning to standby...)\n")
                        engine.transition_to(engine.state.STANDBY)
                        continue

                    print(f"Command heard: {clean_cmd}")

                    # Check for stop phrase
                    if clean_cmd.lower().strip().rstrip(".!?") in stop_phrases:
                        print("\nCHARVIS: Wake-word mode disabled. Returning to text interface.\n")
                        try:
                            tts.speak("Wake word mode disabled.")
                        except Exception:
                            pass
                        break

                    # Process via Brain
                    engine.transition_to(engine.state.PROCESSING)
                    response = brain.process_user_message(
                        user_input=clean_cmd,
                        confirmation_callback=cli_confirmation_callback,
                    )
                    print(f"\nCHARVIS: {response}\n")

                    # Speak response
                    engine.transition_to(engine.state.SPEAKING)
                    try:
                        tts.speak(response)
                    except Exception as tts_err:
                        logger.warning("TTS output error: %s", tts_err)

                    engine.transition_to(engine.state.STANDBY)
                    print("Standby: listening for wake phrase...")

            except KeyboardInterrupt:
                raise
            except Exception as loop_err:
                logger.debug("Wake-word loop iteration error: %s", loop_err)
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nWake-word mode stopped. Returning to text CLI.\n")
    finally:
        engine.stop()
        set_active_engine(None)


def interactive_loop(brain: AIBrain, settings: Settings) -> None:
    """Interactive command-line conversation loop."""
    logger = get_logger("CHARVIS.CLI")
    logger.info("CHARVIS interactive session started.")

    if not settings.is_api_key_configured:
        print("[Notice] OPENAI_API_KEY is not set in your .env file.")
        print("         CHARVIS will prompt for configuration when queries are sent.\n")

    while True:
        try:
            # Prompt user
            user_input = input("You: ").strip()

            # Handle empty input
            if not user_input:
                continue

            # Handle exit commands
            if user_input.lower() in {"exit", "quit", "bye", "q"}:
                print("\nCHARVIS: Goodbye! Have a productive day.\n")
                logger.info("User requested exit from interactive session.")
                break

            # Handle wake-word mode entry
            if user_input.lower() in {"wakeword", "/wakeword", "wake", "standby"}:
                run_wakeword_mode(brain, settings)
                continue

            # Handle voice mode entry
            if user_input.lower() in {"voice", "/voice"}:
                run_voice_mode(brain, settings)
                continue

            # Handle reset command
            if user_input.lower() == "/reset":
                brain.reset_session()
                print("\nCHARVIS: Session memory has been reset.\n")
                continue

            # Process through AI Brain with safety confirmation callback
            response = brain.process_user_message(
                user_input=user_input,
                confirmation_callback=cli_confirmation_callback,
            )
            print(f"\nCHARVIS: {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n\nCHARVIS: Session interrupted. Exiting cleanly. Goodbye!\n")
            logger.info("Session terminated by interrupt signal.")
            break
        except Exception as e:
            logger.exception("Unexpected error in conversation loop: %s", str(e))
            print(f"\n[Error] An unexpected error occurred: {e}\n")


def main() -> int:
    """Main application initialization and execution."""
    try:
        settings = get_settings()
        setup_logging(settings)
        logger = get_logger("CHARVIS")

        logger.info(
            "Starting %s v%s in %s mode (Debug=%s)",
            settings.app_name,
            settings.app_version,
            settings.environment,
            settings.debug,
        )

        brain = AIBrain()
        print_banner(settings, tool_count=brain.registry.count())

        # Cleanup expired memories on startup
        try:
            purged = brain.memory_manager.cleanup_expired()
            if purged > 0:
                logger.info("Cleaned up %d expired memories at startup.", purged)
        except Exception as e:
            logger.warning("Failed to clean up expired memories at startup: %s", e)

        # Launch Desktop GUI if --gui flag is present
        if "--gui" in sys.argv or "-g" in sys.argv:
            logger.info("Launching CHARVIS Desktop GUI...")
            from gui.app import CharvisApp
            app = CharvisApp()
            app.run()
            return 0

        try:
            interactive_loop(brain, settings)
        finally:
            try:
                brain.memory_manager.storage.close()
            except Exception:
                pass

        logger.info("%s session closed gracefully.", settings.app_name)
        return 0

    except KeyboardInterrupt:
        print("\nShutdown requested by user. Exiting cleanly...")
        return 0
    except Exception as e:
        print(f"\n[FATAL] Failed to start CHARVIS: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
