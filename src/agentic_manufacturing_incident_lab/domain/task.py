"""Investigation task states and their permitted transitions."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


class TaskStatus(StrEnum):
    """Lifecycle state of an incident investigation task."""

    CREATED = "created"
    INVESTIGATING = "investigating"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SAFE_STOPPED = "safe_stopped"


@dataclass(frozen=True, slots=True)
class TaskState:
    """One immutable snapshot of a task at a specific revision."""

    task_id: str
    incident_id: str
    status: TaskStatus
    revision: int
    updated_at: datetime
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("task_id", "incident_id", "reason"):
            require_text(getattr(self, field_name), field_name)
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("revision must be a non-negative integer")
        require_timezone(self.updated_at, "updated_at")


class InvalidTaskTransition(ValueError):
    """Raised when a task attempts a forbidden lifecycle transition."""


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.INVESTIGATING, TaskStatus.SAFE_STOPPED}),
    TaskStatus.INVESTIGATING: frozenset(
        {
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SAFE_STOPPED,
        }
    ),
    TaskStatus.WAITING_APPROVAL: frozenset(
        {TaskStatus.INVESTIGATING, TaskStatus.SAFE_STOPPED}
    ),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.SAFE_STOPPED: frozenset(),
}


def allowed_next_statuses(status: TaskStatus) -> frozenset[TaskStatus]:
    """Return the lifecycle states reachable from the current status."""
    return _ALLOWED_TRANSITIONS[status]


def transition_task(
    current: TaskState,
    target: TaskStatus,
    *,
    reason: str,
    updated_at: datetime,
) -> TaskState:
    """Create the next task snapshot after validating a state transition."""
    if target not in allowed_next_statuses(current.status):
        raise InvalidTaskTransition(f"cannot transition from {current.status} to {target}")
    require_text(reason, "reason")
    require_timezone(updated_at, "updated_at")
    if updated_at <= current.updated_at:
        raise ValueError("updated_at must be later than the current task state")

    return replace(
        current,
        status=target,
        revision=current.revision + 1,
        updated_at=updated_at,
        reason=reason,
    )
