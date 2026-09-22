"""
Unit tests for CHARVIS ResultEvaluator (Phase 14).
"""

from planner.evaluator import ResultEvaluator
from planner.models import EvaluationResult, TaskStep
from tools.schemas import ToolResult


def test_evaluator_successful_step():
    """Verify successful tool result evaluates to SUCCESS or TASK_COMPLETE."""
    evaluator = ResultEvaluator()
    step = TaskStep(order=1, tool_name="calculator", arguments={"expression": "5+5"})
    result = ToolResult(success=True, tool_name="calculator", data={"result": 10})

    eval_res = evaluator.evaluate_step(step, result, is_final_step=False)
    assert eval_res == EvaluationResult.SUCCESS

    eval_final = evaluator.evaluate_step(step, result, is_final_step=True)
    assert eval_final == EvaluationResult.TASK_COMPLETE


def test_evaluator_user_denial():
    """Verify denial by user or safety policy evaluates to USER_DENIED."""
    evaluator = ResultEvaluator()
    step = TaskStep(order=1, tool_name="delete_file", arguments={"path": "important.txt"})
    result = ToolResult(
        success=False,
        tool_name="delete_file",
        error="Action denied: User did not authorize execution of this operation.",
    )

    eval_res = evaluator.evaluate_step(step, result)
    assert eval_res == EvaluationResult.USER_DENIED


def test_evaluator_retry_eligible_for_transient_failure():
    """Verify non-destructive transient failures are flagged as RETRY_ELIGIBLE."""
    evaluator = ResultEvaluator(max_retries=1)
    step = TaskStep(order=1, tool_name="read_file", arguments={"path": "temp.txt"}, retry_count=0)
    result = ToolResult(success=False, tool_name="read_file", error="File temporarily locked by another process")

    eval_res = evaluator.evaluate_step(step, result)
    assert eval_res == EvaluationResult.RETRY_ELIGIBLE


def test_evaluator_retries_exhausted():
    """Verify that once max_retries is reached, outcome is FAILED."""
    evaluator = ResultEvaluator(max_retries=1)
    step = TaskStep(order=1, tool_name="read_file", arguments={"path": "temp.txt"}, retry_count=1)
    result = ToolResult(success=False, tool_name="read_file", error="File temporarily locked")

    eval_res = evaluator.evaluate_step(step, result)
    assert eval_res == EvaluationResult.FAILED


def test_evaluator_non_retryable_destructive_action():
    """Verify destructive actions (delete, shutdown) are never marked retry-eligible."""
    evaluator = ResultEvaluator(max_retries=2)
    step = TaskStep(order=1, tool_name="delete_file", arguments={"path": "file.txt"}, retry_count=0)
    result = ToolResult(success=False, tool_name="delete_file", error="File not found")

    eval_res = evaluator.evaluate_step(step, result)
    assert eval_res == EvaluationResult.FAILED
