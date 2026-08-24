"""Core domain objects shared by the simulator and agents."""

from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Evidence,
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
)
from agentic_manufacturing_incident_lab.domain.task import (
    InvalidTaskTransition,
    TaskState,
    TaskStatus,
    allowed_next_statuses,
    transition_task,
)

__all__ = [
    "Action",
    "ActionResult",
    "ActionResultStatus",
    "ActionRisk",
    "Evidence",
    "Incident",
    "IncidentSeverity",
    "Observation",
    "ObservationKind",
    "InvalidTaskTransition",
    "TaskState",
    "TaskStatus",
    "allowed_next_statuses",
    "transition_task",
]
