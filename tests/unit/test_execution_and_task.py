from datetime import UTC, datetime, timedelta

import pytest

from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.task import (
    InvalidTaskTransition,
    TaskState,
    TaskStatus,
    allowed_next_statuses,
    transition_task,
)

STARTED_AT = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def make_task(status: TaskStatus = TaskStatus.CREATED) -> TaskState:
    return TaskState(
        task_id="TASK-001",
        incident_id="INC-001",
        status=status,
        revision=0,
        updated_at=STARTED_AT,
        reason="Investigation task created.",
    )


def test_successful_action_result_can_reference_observations() -> None:
    result = ActionResult(
        result_id="RES-001",
        action_id="ACT-001",
        incident_id="INC-001",
        status=ActionResultStatus.SUCCEEDED,
        summary="Connectivity probe completed.",
        completed_at=STARTED_AT,
        observation_ids=["OBS-001"],  # type: ignore[arg-type]
    )

    assert result.observation_ids == ("OBS-001",)
    assert result.error_code is None


@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (ActionResultStatus.FAILED, "tool_failure"),
        (ActionResultStatus.DENIED, "approval_denied"),
        (ActionResultStatus.TIMED_OUT, "tool_timeout"),
    ],
)
def test_unsuccessful_action_result_requires_error_code(
    status: ActionResultStatus,
    error_code: str,
) -> None:
    result = ActionResult(
        result_id="RES-001",
        action_id="ACT-001",
        incident_id="INC-001",
        status=status,
        summary="Action did not complete successfully.",
        completed_at=STARTED_AT,
        error_code=error_code,
    )

    assert result.error_code == error_code


def test_unsuccessful_action_result_rejects_missing_error_code() -> None:
    with pytest.raises(ValueError, match="error_code must not be blank"):
        ActionResult(
            result_id="RES-001",
            action_id="ACT-001",
            incident_id="INC-001",
            status=ActionResultStatus.FAILED,
            summary="Connectivity probe failed.",
            completed_at=STARTED_AT,
        )


def test_successful_action_result_rejects_error_code() -> None:
    with pytest.raises(ValueError, match="must not have an error_code"):
        ActionResult(
            result_id="RES-001",
            action_id="ACT-001",
            incident_id="INC-001",
            status=ActionResultStatus.SUCCEEDED,
            summary="Connectivity probe completed.",
            completed_at=STARTED_AT,
            error_code="unexpected_error",
        )


def test_action_result_rejects_duplicate_observation_references() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        ActionResult(
            result_id="RES-001",
            action_id="ACT-001",
            incident_id="INC-001",
            status=ActionResultStatus.SUCCEEDED,
            summary="Connectivity probe completed.",
            completed_at=STARTED_AT,
            observation_ids=("OBS-001", "OBS-001"),
        )


def test_transition_creates_new_task_revision_without_mutating_previous_state() -> None:
    created = make_task()

    investigating = transition_task(
        created,
        TaskStatus.INVESTIGATING,
        reason="Initial triage started.",
        updated_at=STARTED_AT + timedelta(minutes=1),
    )

    assert created.status is TaskStatus.CREATED
    assert created.revision == 0
    assert investigating.status is TaskStatus.INVESTIGATING
    assert investigating.revision == 1
    assert investigating.reason == "Initial triage started."


def test_waiting_task_can_resume_investigation_after_approval() -> None:
    waiting = make_task(TaskStatus.WAITING_APPROVAL)

    resumed = transition_task(
        waiting,
        TaskStatus.INVESTIGATING,
        reason="Operator approved the controlled action.",
        updated_at=STARTED_AT + timedelta(minutes=1),
    )

    assert resumed.status is TaskStatus.INVESTIGATING


def test_task_cannot_skip_directly_from_created_to_completed() -> None:
    with pytest.raises(InvalidTaskTransition, match="created.*completed"):
        transition_task(
            make_task(),
            TaskStatus.COMPLETED,
            reason="No investigation was performed.",
            updated_at=STARTED_AT + timedelta(minutes=1),
        )


@pytest.mark.parametrize(
    "terminal_status",
    [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SAFE_STOPPED],
)
def test_terminal_task_states_have_no_next_statuses(terminal_status: TaskStatus) -> None:
    assert allowed_next_statuses(terminal_status) == frozenset()


def test_task_transition_requires_forward_moving_timestamp() -> None:
    with pytest.raises(ValueError, match="must be later"):
        transition_task(
            make_task(),
            TaskStatus.INVESTIGATING,
            reason="Initial triage started.",
            updated_at=STARTED_AT,
        )


@pytest.mark.parametrize("revision", [-1, True, 1.5])
def test_task_rejects_invalid_revision(revision: object) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        TaskState(
            task_id="TASK-001",
            incident_id="INC-001",
            status=TaskStatus.CREATED,
            revision=revision,  # type: ignore[arg-type]
            updated_at=STARTED_AT,
            reason="Investigation task created.",
        )
