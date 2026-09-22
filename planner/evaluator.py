"""
Result evaluation engine for CHARVIS Task Planner (Phase 14).
Evaluates ToolResults from ToolRouter to determine whether a task should continue,
pause, retry, replan, or terminate.
"""

from typing import Optional
from config import get_settings
from logger import get_logger
from planner.models import EvaluationResult, TaskStep
from planner.safety import is_non_retryable_action
from tools.schemas import ToolResult

logger = get_logger("CHARVIS.Planner.Evaluator")


class ResultEvaluator:
    """
    Evaluates actual execution outcomes of tool steps.
    Distinguishes between genuine success, user denials, transient failures,
    and non-retryable destructive errors.
    """

    def __init__(self, max_retries: Optional[int] = None) -> None:
        settings = get_settings()
        self.max_retries = max_retries if max_retries is not None else settings.max_step_retries

    def evaluate_step(
        self,
        step: TaskStep,
        result: ToolResult,
        is_final_step: bool = False,
    ) -> EvaluationResult:
        """
        Evaluate a completed step execution outcome.
        """
        # Case 1: Failure or User Denial
        if not result.success:
            err_msg = (result.error or "").lower()
            logger.warning("Step %d (%s) failed: %s", step.order, step.tool_name, result.error)

            # Check if this was a user denial
            if "denied" in err_msg or "not authorize" in err_msg:
                return EvaluationResult.USER_DENIED

            # Check if automatic retry is permitted for this tool
            if step.retry_count < self.max_retries:
                if not is_non_retryable_action(step.tool_name, step.arguments):
                    logger.info("Transient error on step %d eligible for retry", step.order)
                    return EvaluationResult.RETRY_ELIGIBLE

            return EvaluationResult.FAILED

        # Case 2: Success
        logger.debug("Step %d (%s) evaluated as SUCCESS", step.order, step.tool_name)
        if is_final_step:
            return EvaluationResult.TASK_COMPLETE

        return EvaluationResult.SUCCESS
