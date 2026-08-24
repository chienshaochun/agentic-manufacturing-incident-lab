"""Immutable records describing the outcome of an attempted action."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


class ActionResultStatus(StrEnum):
    """Terminal outcome returned after an action is processed."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ActionResult:
    """The auditable outcome of one action, separate from the action request."""

    result_id: str
    action_id: str
    incident_id: str
    status: ActionResultStatus
    summary: str
    completed_at: datetime
    observation_ids: tuple[str, ...] = ()
    error_code: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("result_id", "action_id", "incident_id", "summary"):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.completed_at, "completed_at")

        observation_ids = tuple(self.observation_ids)
        for observation_id in observation_ids:
            require_text(observation_id, "observation_id")
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation_ids must not contain duplicates")
        object.__setattr__(self, "observation_ids", observation_ids)

        if self.status is ActionResultStatus.SUCCEEDED:
            if self.error_code is not None:
                raise ValueError("a successful action result must not have an error_code")
        else:
            require_text(self.error_code, "error_code")
