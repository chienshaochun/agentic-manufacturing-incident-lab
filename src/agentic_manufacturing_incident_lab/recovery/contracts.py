"""Immutable contracts for bounded recovery after terminal tool failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, Protocol, runtime_checkable

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)
from agentic_manufacturing_incident_lab.domain.models import ScalarValue
from agentic_manufacturing_incident_lab.tools import ToolSpec

if TYPE_CHECKING:
    from agentic_manufacturing_incident_lab.runtime.executor import (
        ActionExecutionRecord,
    )


class RecoveryDisposition(StrEnum):
    """Treatment selected after a logical action has terminally failed."""

    TRY_ALTERNATIVE = "try_alternative"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    """Auditable recovery decision for one unsuccessful action."""

    recovery_id: str
    action_id: str
    incident_id: str
    policy_name: str
    disposition: RecoveryDisposition
    rationale: str
    assessed_at: datetime
    alternative_tool_name: str | None = None
    alternative_parameters: Mapping[str, ScalarValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "recovery_id",
            "action_id",
            "incident_id",
            "policy_name",
            "rationale",
        ):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.assessed_at, "assessed_at")
        parameters = MappingProxyType(dict(self.alternative_parameters))
        if self.disposition is RecoveryDisposition.TRY_ALTERNATIVE:
            require_text(self.alternative_tool_name, "alternative_tool_name")
        elif self.alternative_tool_name is not None or parameters:
            raise ValueError("safe-stop recovery must not contain an alternative action")
        object.__setattr__(self, "alternative_parameters", parameters)


@runtime_checkable
class RecoveryPolicy(Protocol):
    """Select one bounded alternative or safe stop after a failed action."""

    name: str

    def assess(
        self,
        failed_execution: ActionExecutionRecord,
        *,
        available_tools: tuple[ToolSpec, ...],
        prior_executions: tuple[ActionExecutionRecord, ...],
        assessed_at: datetime,
    ) -> RecoveryAssessment:
        """Return a recovery assessment without invoking any tool."""
        ...
