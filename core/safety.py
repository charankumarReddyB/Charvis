"""
Safety Manager for CHARVIS (Phase 4.1 & Phase 17 Hardening).
Classifies tool risk levels and manages single-use, bounded-timeout human confirmation protocols.
"""

from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from typing import Any, Callable, Dict, Optional
import uuid

from config import get_settings
from core.errors import SafetyError
from logger import get_logger

logger = get_logger("CHARVIS.Safety")


class RiskLevel(str, Enum):
    """Risk tiers for tools and actions in CHARVIS."""
    SAFE = "SAFE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    HIGH_RISK = "HIGH_RISK"


class ConfirmationState(str, Enum):
    """State lifecycle for a human confirmation request (Phase 17)."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ConfirmationStateError(Exception):
    """Raised when an invalid state transition is attempted on a confirmation request."""
    pass


@dataclass
class ConfirmationRequest:
    """
    Immutable representation of an action requiring explicit user authorization.
    Tracks single-use state transitions and enforces strict timeout boundaries.
    """
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: RiskLevel
    custom_message: Optional[str] = None
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    confirmation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ConfirmationState = ConfirmationState.PENDING
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 120.0
    resolved_at: Optional[float] = None
    resolution_reason: Optional[str] = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check whether the confirmation request has exceeded its time-to-live."""
        now = current_time if current_time is not None else time.time()
        return (now - self.created_at) >= self.timeout_seconds

    def transition_to(self, new_state: ConfirmationState, reason: Optional[str] = None) -> None:
        """
        Transition to a new state with strict single-use validation.
        Allowed transitions:
          PENDING -> APPROVED
          PENDING -> DENIED
          PENDING -> EXPIRED
          PENDING -> CANCELLED
        All other transitions or repeated transitions raise ConfirmationStateError.
        """
        with self._lock:
            # If request is pending but time expired, force transition to EXPIRED
            if self.state == ConfirmationState.PENDING and self.is_expired():
                self.state = ConfirmationState.EXPIRED
                self.resolved_at = time.time()
                self.resolution_reason = "Confirmation request timed out"
                logger.warning("Confirmation %s auto-expired after %.1fs", self.confirmation_id, self.timeout_seconds)
                if new_state != ConfirmationState.EXPIRED:
                    raise ConfirmationStateError(
                        f"Cannot transition confirmation {self.confirmation_id} to {new_state.value}: request has EXPIRED"
                    )
                return

            if self.state != ConfirmationState.PENDING:
                raise ConfirmationStateError(
                    f"Illegal transition: Confirmation {self.confirmation_id} already in terminal state '{self.state.value}'. "
                    f"Attempted to transition to '{new_state.value}'."
                )

            if new_state == ConfirmationState.PENDING:
                raise ConfirmationStateError("Cannot transition from PENDING back to PENDING.")

            self.state = new_state
            self.resolved_at = time.time()
            self.resolution_reason = reason or f"Transitioned to {new_state.value}"
            logger.info("Confirmation %s transitioned to %s (reason: %s)", self.confirmation_id, new_state.value, self.resolution_reason)

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "confirmation_id": self.confirmation_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "risk_level": self.risk_level.value,
            "custom_message": self.custom_message,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "timeout_seconds": self.timeout_seconds,
            "resolved_at": self.resolved_at,
            "resolution_reason": self.resolution_reason,
            "is_expired": self.is_expired(),
        }


class SafetyManager:
    """
    Manages safety policies, risk classification, and human-in-the-loop authorization.
    Guarantees single-use confirmation, race condition protection, and bounded timeouts (Phase 17).
    """

    def __init__(self, default_policy_strict: bool = True) -> None:
        self.default_policy_strict = default_policy_strict
        self._pending_confirmations: Dict[str, ConfirmationRequest] = {}
        self._lock = threading.RLock()
        logger.debug("SafetyManager initialized (strict=%s)", default_policy_strict)

    def requires_confirmation(self, risk_level: RiskLevel) -> bool:
        """Return True if the given risk level requires human authorization."""
        return risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.HIGH_RISK)

    def create_confirmation_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel,
        custom_message: Optional[str] = None,
        task_id: Optional[str] = None,
        step_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ConfirmationRequest:
        """Create and register a new pending confirmation request."""
        settings = get_settings()
        timeout = timeout_seconds if timeout_seconds is not None else settings.confirmation_timeout_seconds

        req = ConfirmationRequest(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            custom_message=custom_message,
            task_id=task_id,
            step_id=step_id,
            timeout_seconds=timeout,
        )

        with self._lock:
            # Expire any stale confirmations first
            self._expire_stale_locked()
            self._pending_confirmations[req.confirmation_id] = req

        logger.info("Created confirmation request %s for '%s' (risk: %s, timeout: %.1fs)", req.confirmation_id, tool_name, risk_level.value, timeout)
        return req

    def get_confirmation(self, confirmation_id: str) -> Optional[ConfirmationRequest]:
        """Lookup an active confirmation request by ID."""
        with self._lock:
            return self._pending_confirmations.get(confirmation_id)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        approved: bool,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Atomically resolve a pending confirmation.
        Returns True if resolved to APPROVED; False otherwise.
        Rejects double-resolution or expired requests.
        """
        with self._lock:
            req = self._pending_confirmations.get(confirmation_id)
            if not req:
                logger.warning("Attempted to resolve unknown confirmation: %s", confirmation_id)
                return False

            if req.is_expired():
                try:
                    req.transition_to(ConfirmationState.EXPIRED, "Expired prior to resolution")
                except ConfirmationStateError:
                    pass
                self._pending_confirmations.pop(confirmation_id, None)
                logger.warning("Confirmation %s expired; resolution rejected.", confirmation_id)
                return False

            target_state = ConfirmationState.APPROVED if approved else ConfirmationState.DENIED
            try:
                req.transition_to(target_state, reason)
                self._pending_confirmations.pop(confirmation_id, None)
                return approved
            except ConfirmationStateError as e:
                logger.warning("Failed to resolve confirmation %s: %s", confirmation_id, e)
                return False

    def cancel_confirmation(self, confirmation_id: str, reason: str = "Cancelled by user or system") -> bool:
        """Cancel a pending confirmation."""
        with self._lock:
            req = self._pending_confirmations.get(confirmation_id)
            if not req:
                return False
            try:
                req.transition_to(ConfirmationState.CANCELLED, reason)
                self._pending_confirmations.pop(confirmation_id, None)
                return True
            except ConfirmationStateError:
                return False

    def cancel_all_pending(self, reason: str = "Shutdown or abort") -> int:
        """Cancel all currently pending confirmations."""
        count = 0
        with self._lock:
            for cid in list(self._pending_confirmations.keys()):
                if self.cancel_confirmation(cid, reason):
                    count += 1
            self._pending_confirmations.clear()
        if count > 0:
            logger.info("Cancelled %d pending confirmations (reason: %s)", count, reason)
        return count

    def expire_stale_confirmations() -> int:
        """Check and transition any expired confirmations."""
        # Class or instance method fallback
        pass

    def expire_stale(self) -> int:
        """Expire all stale pending confirmations."""
        with self._lock:
            return self._expire_stale_locked()

    def _expire_stale_locked(self) -> int:
        """Internal helper to expire stale confirmations under lock."""
        count = 0
        now = time.time()
        for cid, req in list(self._pending_confirmations.items()):
            if req.is_expired(now):
                try:
                    req.transition_to(ConfirmationState.EXPIRED, "Confirmation timed out")
                except ConfirmationStateError:
                    pass
                self._pending_confirmations.pop(cid, None)
                count += 1
        return count

    def format_confirmation_prompt(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel,
        custom_message: Optional[str] = None,
        confirmation_id: Optional[str] = None,
    ) -> str:
        """Generate a clear, transparent confirmation prompt detailing the requested action."""
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
        warning_prefix = "[HIGH RISK ACTION]" if risk_level == RiskLevel.HIGH_RISK else "[CONFIRMATION REQUIRED]"
        notice = f"\n  Notice    : {custom_message}" if custom_message else ""
        cid_str = f"\n  ID        : {confirmation_id}" if confirmation_id else ""

        return (
            f"\n{warning_prefix}\n"
            f"CHARVIS is requesting permission to execute:\n"
            f"  Tool      : {tool_name}\n"
            f"  Arguments : {args_str}\n"
            f"  Risk Level: {risk_level.value}"
            f"{cid_str}"
            f"{notice}\n"
            f"Proceed? [y/N]: "
        )

    def verify_action(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel,
        confirmation_callback: Optional[Callable[..., bool]] = None,
        custom_message: Optional[str] = None,
        task_id: Optional[str] = None,
        step_id: Optional[str] = None,
        confirmation_id: Optional[str] = None,
    ) -> bool:
        """
        Verify whether an action is authorized to proceed.
        Returns True if safe or authorized; returns False if denied, expired, or cancelled.
        Guarantees single-use authorization and enforces bounded timeouts.
        """
        if not self.requires_confirmation(risk_level):
            return True

        logger.warning(
            "Action requires confirmation: %s with args: %s (Risk: %s)",
            tool_name,
            list(arguments.keys()),
            risk_level.value,
        )

        if confirmation_callback is None:
            logger.error("No confirmation callback provided for confirmation-required tool: %s. Denying.", tool_name)
            return False

        # Create or attach confirmation request
        req: ConfirmationRequest
        if confirmation_id:
            with self._lock:
                existing = self._pending_confirmations.get(confirmation_id)
                if existing and existing.state == ConfirmationState.PENDING:
                    req = existing
                else:
                    req = self.create_confirmation_request(
                        tool_name=tool_name,
                        arguments=arguments,
                        risk_level=risk_level,
                        custom_message=custom_message,
                        task_id=task_id,
                        step_id=step_id,
                    )
        else:
            req = self.create_confirmation_request(
                tool_name=tool_name,
                arguments=arguments,
                risk_level=risk_level,
                custom_message=custom_message,
                task_id=task_id,
                step_id=step_id,
            )

        try:
            # Check timeout before invoking callback
            if req.is_expired():
                req.transition_to(ConfirmationState.EXPIRED, "Request expired before user callback")
                with self._lock:
                    self._pending_confirmations.pop(req.confirmation_id, None)
                logger.warning("Confirmation request %s timed out before presentation.", req.confirmation_id)
                return False

            # Invoke callback with best matching signature
            confirmed = False
            try:
                # 5-arg signature including request
                confirmed = confirmation_callback(tool_name, arguments, risk_level, custom_message, req)
            except TypeError:
                try:
                    # 4-arg signature
                    confirmed = confirmation_callback(tool_name, arguments, risk_level, custom_message)
                except TypeError:
                    # 3-arg signature
                    confirmed = confirmation_callback(tool_name, arguments, risk_level)

            # Check if expired during callback execution
            if req.is_expired():
                try:
                    req.transition_to(ConfirmationState.EXPIRED, "Request timed out during callback")
                except ConfirmationStateError:
                    pass
                with self._lock:
                    self._pending_confirmations.pop(req.confirmation_id, None)
                logger.warning("Confirmation request %s timed out during authorization.", req.confirmation_id)
                return False

            # Atomically transition state based on callback result
            if confirmed:
                try:
                    req.transition_to(ConfirmationState.APPROVED, "User explicitly authorized execution")
                    logger.info("User explicitly authorized execution of tool: %s (ID: %s)", tool_name, req.confirmation_id)
                    return True
                except ConfirmationStateError as cse:
                    logger.warning("Could not approve confirmation %s: %s", req.confirmation_id, cse)
                    return False
                finally:
                    with self._lock:
                        self._pending_confirmations.pop(req.confirmation_id, None)
            else:
                try:
                    req.transition_to(ConfirmationState.DENIED, "User denied authorization")
                    logger.info("User denied authorization for tool: %s (ID: %s)", tool_name, req.confirmation_id)
                except ConfirmationStateError:
                    pass
                finally:
                    with self._lock:
                        self._pending_confirmations.pop(req.confirmation_id, None)
                return False

        except Exception as e:
            logger.error("Error during confirmation callback execution for %s: %s. Denying.", tool_name, str(e))
            try:
                req.transition_to(ConfirmationState.DENIED, f"Callback exception: {str(e)}")
            except ConfirmationStateError:
                pass
            finally:
                with self._lock:
                    self._pending_confirmations.pop(req.confirmation_id, None)
            return False
