"""
Safety Manager for CHARVIS.
Classifies tool risk levels and manages user confirmation protocols.
"""

from enum import Enum
from typing import Any, Callable, Dict, Optional
from logger import get_logger

logger = get_logger("CHARVIS.Safety")


class RiskLevel(str, Enum):
    """Risk tiers for tools and actions in CHARVIS."""
    SAFE = "SAFE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    HIGH_RISK = "HIGH_RISK"


class SafetyManager:
    """
    Manages safety policies and human-in-the-loop authorization.
    Guarantees that dangerous or state-altering actions cannot proceed without explicit consent.
    """

    def __init__(self, default_policy_strict: bool = True) -> None:
        self.default_policy_strict = default_policy_strict
        logger.debug("SafetyManager initialized (strict=%s)", default_policy_strict)

    def requires_confirmation(self, risk_level: RiskLevel) -> bool:
        """Return True if the given risk level requires human authorization."""
        return risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.HIGH_RISK)

    def format_confirmation_prompt(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel,
        custom_message: Optional[str] = None,
    ) -> str:
        """Generate a clear, transparent confirmation prompt detailing the requested action."""
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
        warning_prefix = "[HIGH RISK ACTION]" if risk_level == RiskLevel.HIGH_RISK else "[CONFIRMATION REQUIRED]"
        notice = f"\n  Notice    : {custom_message}" if custom_message else ""

        return (
            f"\n{warning_prefix}\n"
            f"CHARVIS is requesting permission to execute:\n"
            f"  Tool      : {tool_name}\n"
            f"  Arguments : {args_str}\n"
            f"  Risk Level: {risk_level.value}"
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
    ) -> bool:
        """
        Verify whether an action is authorized to proceed.
        Returns True if safe or confirmed; returns False if denied.
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

        try:
            try:
                confirmed = confirmation_callback(tool_name, arguments, risk_level, custom_message)
            except TypeError:
                confirmed = confirmation_callback(tool_name, arguments, risk_level)

            if confirmed:
                logger.info("User explicitly authorized execution of tool: %s", tool_name)
                return True
            else:
                logger.info("User denied authorization for tool: %s", tool_name)
                return False
        except Exception as e:
            logger.error("Error during confirmation callback execution for %s: %s. Denying.", tool_name, str(e))
            return False
