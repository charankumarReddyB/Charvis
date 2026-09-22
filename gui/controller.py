"""
GUI Controller for CHARVIS (Phase 15).
Coordinates UI events with existing backends (AIBrain, ToolRouter, SafetyManager, Planner, Memory)
using non-blocking background workers and thread-safe UI updates.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from config import get_settings
from core.brain import AIBrain
from core.safety import RiskLevel
from gui.models import (
    AppView,
    ChatMessage,
    ConfirmationRequest,
    SystemState,
    TaskDisplayItem,
)
from gui.state import GUIState
from logger import get_logger
from tools.planner import get_task_executor, get_task_planner, get_task_store

logger = get_logger("CHARVIS.GUI.Controller")


class GUIController:
    """
    Controller layer connecting the Desktop GUI with existing CHARVIS subsystems.
    Strictly coordinates; never executes low-level tool automation directly.
    """

    def __init__(
        self,
        state: Optional[GUIState] = None,
        ui_dispatcher: Optional[Callable[[Callable[[], None]], None]] = None,
        brain: Optional[AIBrain] = None,
    ) -> None:
        self.state = state or GUIState()
        self.brain = brain or AIBrain()
        # ui_dispatcher runs the callable on the Tkinter main thread
        self.ui_dispatcher = ui_dispatcher or (lambda fn: fn())

        # Bounded worker pool for background requests
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="CharvisWorker")
        self._shutdown_event = threading.Event()

    def dispatch_ui(self, fn: Callable[[], None]) -> None:
        """Safely schedule a callable to execute on the Tkinter main thread."""
        try:
            self.ui_dispatcher(fn)
        except Exception as e:
            logger.error("Failed to dispatch to UI thread: %s", e)

    # ==========================================================================
    # Conversation & Message Handling
    # ==========================================================================
    def send_user_message(self, text: str) -> None:
        """Submit a user query to AIBrain via background worker thread."""
        cleaned = text.strip()
        if not cleaned:
            return

        if self.state.is_busy:
            logger.warning("Query ignored: AI Brain is currently busy.")
            return

        # 1. Update UI state for user message
        self.state.add_message("user", cleaned)
        self.state.set_processing(True)

        # 2. Launch background execution
        self._executor.submit(self._run_brain_query, cleaned)

    def _run_brain_query(self, query: str) -> None:
        """Background worker executing cognitive loop with confirmation callback."""
        try:
            logger.info("Executing AI Brain query in background worker...")
            response = self.brain.process_user_message(
                user_input=query,
                confirmation_callback=self.handle_confirmation,
            )

            def on_success() -> None:
                self.state.add_message("assistant", response)
                self.state.set_processing(False)
                # Refresh tasks in case user command created or ran a task
                self.load_tasks()

            self.dispatch_ui(on_success)

        except Exception as e:
            logger.error("Error processing user message: %s", e)
            safe_error_msg = f"CHARVIS couldn't complete that request: {type(e).__name__}"

            def on_error() -> None:
                self.state.add_message("error", safe_error_msg)
                self.state.set_processing(False)

            self.dispatch_ui(on_error)

    # ==========================================================================
    # Security Confirmation Handling
    # ==========================================================================
    def handle_confirmation(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: Union[RiskLevel, str],
        custom_message: Optional[str] = None,
    ) -> bool:
        """
        Confirmation callback invoked by SafetyManager on a background thread.
        Pauses the background thread until user clicks Confirm or Cancel on the GUI.
        """
        risk_str = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        logger.info(
            "Confirmation requested for '%s' (Risk: %s). Prompting user via GUI...",
            tool_name,
            risk_str,
        )

        req = ConfirmationRequest(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            custom_message=custom_message,
        )

        # Post confirmation request to UI state and log chat notice
        def on_request() -> None:
            self.state.add_message(
                "tool",
                f"Action '{tool_name}' requires your authorization ({risk_str}).",
                metadata={"tool_name": tool_name, "risk_level": risk_str},
            )
            self.state.request_confirmation(req)

        self.dispatch_ui(on_request)

        # Wait for user decision (blocks only this background worker thread)
        # Timeout after 5 minutes if abandoned
        wait_success = req.event.wait(timeout=300.0)

        # Clear confirmation prompt from UI state
        def on_decision() -> None:
            self.state.clear_confirmation()
            if not wait_success:
                self.state.add_message(
                    "tool",
                    f"Action '{tool_name}' confirmation timed out. Execution denied.",
                )
            else:
                decision_text = "authorized" if req.result else "denied"
                self.state.add_message(
                    "tool",
                    f"Action '{tool_name}' was {decision_text} by user.",
                )

        self.dispatch_ui(on_decision)

        if not wait_success:
            logger.warning("Confirmation prompt for '%s' timed out. Denying action.", tool_name)
            return False

        logger.info("Confirmation for '%s' resolved to: %s", tool_name, req.result)
        return req.result

    def submit_confirmation(self, request_id: str, approved: bool) -> None:
        """Called from UI thread when user clicks Confirm or Cancel."""
        req = self.state.pending_confirmation
        if req and req.request_id == request_id:
            if approved:
                req.approve()
            else:
                req.deny()

    # ==========================================================================
    # Voice Subsystem Integration
    # ==========================================================================
    def start_voice_input(self) -> None:
        """Explicitly activate microphone input in background worker."""
        if self.state.is_listening or self.state.is_busy:
            return

        self.state.set_listening(True)
        self._executor.submit(self._run_voice_capture)

    def _run_voice_capture(self) -> None:
        """Record bounded speech snippet and send transcribed text to brain."""
        try:
            from voice.audio import AudioCapture
            from voice.stt import get_stt_provider

            capture = AudioCapture()
            if not capture.is_microphone_available():
                def on_mic_err() -> None:
                    self.state.add_message("error", "No microphone detected on this system.")
                    self.state.set_listening(False)
                self.dispatch_ui(on_mic_err)
                return

            stt = get_stt_provider()
            logger.info("Recording voice input snippet...")
            audio_data = capture.record_audio(duration=5.0)

            if audio_data is None:
                def on_no_speech() -> None:
                    self.state.add_message("system", "No speech was detected.")
                    self.state.set_listening(False)
                self.dispatch_ui(on_no_speech)
                return

            transcription = stt.transcribe(audio_data).strip()
            logger.info("Voice transcription received: '%s'", transcription)

            def on_transcribed() -> None:
                self.state.set_listening(False)
                if transcription:
                    self.send_user_message(transcription)
                else:
                    self.state.add_message("system", "Speech was not recognized.")

            self.dispatch_ui(on_transcribed)

        except Exception as e:
            logger.error("Error during voice input: %s", e)
            def on_voice_err() -> None:
                self.state.add_message("error", f"Voice error: {e}")
                self.state.set_listening(False)
            self.dispatch_ui(on_voice_err)

    # ==========================================================================
    # Multi-Step Task Planner Integration
    # ==========================================================================
    def load_tasks(self) -> None:
        """Fetch tasks from TaskStore and update state."""
        try:
            store = get_task_store()
            raw_tasks = store.list_all(limit=20)
            items = [TaskDisplayItem.from_task_dict(t.to_dict()) for t in raw_tasks]

            def update_ui() -> None:
                self.state.set_tasks(items)
                if items and self.state.active_task is None:
                    self.state.set_active_task(items[-1])

            self.dispatch_ui(update_ui)
        except Exception as e:
            logger.error("Failed to load tasks from store: %s", e)

    def create_task(self, goal: str) -> None:
        """Create a new planned task in background worker."""
        cleaned = goal.strip()
        if not cleaned:
            return

        self.state.set_processing(True)

        def worker() -> None:
            try:
                planner = get_task_planner()
                store = get_task_store()
                task = planner.plan(cleaned)
                store.add(task)
                item = TaskDisplayItem.from_task_dict(task.to_dict())

                def on_created() -> None:
                    self.state.set_active_task(item)
                    self.state.add_message(
                        "tool",
                        f"Task created: '{task.goal}' ({len(task.steps)} steps).",
                        metadata={"task_id": task.task_id},
                    )
                    self.state.set_processing(False)
                    self.load_tasks()

                self.dispatch_ui(on_created)

            except Exception as e:
                logger.error("Failed to create task: %s", e)
                def on_fail() -> None:
                    self.state.add_message("error", f"Failed to plan task: {e}")
                    self.state.set_processing(False)
                self.dispatch_ui(on_fail)

        self._executor.submit(worker)

    def run_active_task(self, task_id: Optional[str] = None) -> None:
        """Execute a task sequentially through TaskExecutor."""
        target_id = task_id or (self.state.active_task.task_id if self.state.active_task else None)
        if not target_id:
            logger.warning("Cannot run task: No task selected.")
            return

        self.state.set_system_state(SystemState.EXECUTING, f"Executing task {target_id[:8]}...")

        def worker() -> None:
            try:
                store = get_task_store()
                task = store.get(target_id)
                if not task:
                    logger.warning("Task '%s' not found in store.", target_id)
                    return

                executor = get_task_executor()
                updated_task = executor.run_task(
                    task,
                    confirmation_callback=self.handle_confirmation,
                    auto_replan=True,
                )
                item = TaskDisplayItem.from_task_dict(updated_task.to_dict())

                def on_done() -> None:
                    self.state.set_active_task(item)
                    self.state.set_system_state(SystemState.IDLE, "Ready")
                    self.state.add_message(
                        "tool",
                        f"Task '{updated_task.goal}' {updated_task.status.value}.",
                        metadata={"task_id": updated_task.task_id, "status": updated_task.status.value},
                    )
                    self.load_tasks()

                self.dispatch_ui(on_done)

            except Exception as e:
                logger.error("Error executing task %s: %s", target_id, e)
                def on_err() -> None:
                    self.state.set_system_state(SystemState.ERROR, "Task execution failed")
                    self.state.add_message("error", f"Task execution failed: {e}")
                    self.load_tasks()
                self.dispatch_ui(on_err)

        self._executor.submit(worker)

    def pause_active_task(self, task_id: Optional[str] = None) -> None:
        """Pause a running task."""
        target_id = task_id or (self.state.active_task.task_id if self.state.active_task else None)
        if not target_id:
            return
        try:
            store = get_task_store()
            task = store.get(target_id)
            if task:
                executor = get_task_executor()
                executor.pause_task(task, reason="Paused by user via GUI")
                self.load_tasks()
        except Exception as e:
            logger.error("Failed to pause task: %s", e)

    def resume_active_task(self, task_id: Optional[str] = None) -> None:
        """Resume execution of a paused task."""
        self.run_active_task(task_id)

    def cancel_active_task(self, task_id: Optional[str] = None) -> None:
        """Cancel an in-progress or paused task."""
        target_id = task_id or (self.state.active_task.task_id if self.state.active_task else None)
        if not target_id:
            return
        try:
            store = get_task_store()
            task = store.get(target_id)
            if task:
                executor = get_task_executor()
                executor.cancel_task(task, reason="Cancelled by user via GUI")
                self.load_tasks()
        except Exception as e:
            logger.error("Failed to cancel task: %s", e)

    # ==========================================================================
    # Memory Inspection (Read-Only)
    # ==========================================================================
    def get_memories(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch stored memories strictly read-only for display.
        Never directly mutates SQLite database.
        """
        try:
            # Check if mock or object provides get_all()
            if hasattr(self.brain.memory_manager, "get_all"):
                items = self.brain.memory_manager.get_all()
                results = []
                for m in items:
                    if isinstance(m, dict):
                        results.append(m)
                    else:
                        cat_val = getattr(getattr(m, "category", ""), "value", str(getattr(m, "category", "general")))
                        results.append({
                            "key": getattr(m, "key", ""),
                            "value": str(getattr(m, "value", "")),
                            "category": cat_val,
                            "scope": getattr(getattr(m, "scope", ""), "value", "persistent"),
                            "confidence": getattr(m, "confidence", 1.0),
                        })
                return results

            if query and query.strip():
                items = self.brain.memory_manager.recall(query.strip(), limit=50)
            elif hasattr(self.brain.memory_manager, "list_memories"):
                items = self.brain.memory_manager.list_memories(limit=50)
            elif hasattr(self.brain.memory_manager, "storage") and hasattr(self.brain.memory_manager.storage, "list"):
                items = self.brain.memory_manager.storage.list(limit=50)
            else:
                items = []

            results = []
            for m in items:
                val = m.value if len(m.value) <= 150 else m.value[:147] + "..."
                cat = m.category.value if hasattr(m.category, "value") else str(m.category)
                scope = m.scope.value if hasattr(getattr(m, "scope", None), "value") else str(getattr(m, "scope", "persistent"))
                results.append({
                    "id": getattr(m, "id", "")[:8],
                    "category": cat,
                    "key": m.key,
                    "value": val,
                    "scope": scope,
                    "confidence": getattr(m, "confidence", 1.0),
                })
            return results
        except Exception as e:
            logger.error("Error reading memories: %s", e)
            return []

    # ==========================================================================
    # System & Settings Status (Read-Only)
    # ==========================================================================
    def get_system_status(self) -> Dict[str, Any]:
        """Fetch safe system overview without exposing credentials or secrets."""
        settings = get_settings()
        tool_cnt = self.brain.registry.count() if hasattr(self.brain, "registry") else 68
        return {
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "ai_provider": settings.ai_provider.upper(),
            "ai_model": settings.ai_model,
            "api_configured": "Configured" if settings.is_api_key_configured else "Not Configured",
            "voice_enabled": "Available" if settings.voice_enabled else "Disabled",
            "wake_word_phrase": settings.wake_word_phrase,
            "vision_cloud_enabled": "Enabled" if settings.vision_cloud_enabled else "Disabled (Local only)",
            "max_task_steps": settings.max_task_steps,
            "max_replans_per_task": settings.max_replans_per_task,
            "max_active_tasks": settings.max_active_tasks,
            "tool_count": tool_cnt,
            "total_tools": tool_cnt,
        }

    # ==========================================================================
    # Application Shutdown
    # ==========================================================================
    def shutdown(self) -> None:
        """Gracefully release worker pool, audio handles, and database resources."""
        logger.info("Shutting down GUIController...")
        self._shutdown_event.set()
        try:
            self._executor.shutdown(wait=False)
        except Exception as e:
            logger.debug("Error shutting down executor: %s", e)

        try:
            if hasattr(self.brain, "memory_manager") and hasattr(self.brain.memory_manager, "storage"):
                self.brain.memory_manager.storage.close()
        except Exception as e:
            logger.debug("Error closing memory storage: %s", e)

        logger.info("GUIController shutdown complete.")
