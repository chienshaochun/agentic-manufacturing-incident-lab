"""Structured work products returned by specialist agents."""

from dataclasses import dataclass
from enum import StrEnum

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    HandoffKind,
)
from agentic_manufacturing_incident_lab.domain._validation import require_text
from agentic_manufacturing_incident_lab.runtime import InvestigationRun


@dataclass(frozen=True, slots=True)
class DiagnosticWorkProduct:
    """A diagnostic run paired with its traceable handoff response."""

    run: InvestigationRun
    handoff: AgentHandoff

    def __post_init__(self) -> None:
        if self.handoff.kind is not HandoffKind.DIAGNOSTIC_RESULT:
            raise ValueError("diagnostic work product requires diagnostic_result")
        if self.handoff.incident_id != self.run.incident.incident_id:
            raise ValueError("diagnostic handoff must match the run incident")
        action_ids = tuple(record.action.action_id for record in self.run.executions)
        observation_ids = tuple(
            observation.observation_id for observation in self.run.observations
        )
        if self.handoff.action_ids != action_ids:
            raise ValueError("diagnostic handoff must reference every run action")
        if self.handoff.observation_ids != observation_ids:
            raise ValueError("diagnostic handoff must reference every run observation")


class SafetyReviewOutcome(StrEnum):
    """Independent review disposition for one diagnostic work product."""

    APPROVED = "approved"
    REQUIRES_ATTENTION = "requires_attention"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SafetyReviewProduct:
    """Structured reviewer verdict paired with its handoff response."""

    outcome: SafetyReviewOutcome
    rationale: str
    findings: tuple[str, ...]
    handoff: AgentHandoff

    def __post_init__(self) -> None:
        require_text(self.rationale, "rationale")
        findings = tuple(self.findings)
        if not findings:
            raise ValueError("safety review findings must not be empty")
        for finding in findings:
            require_text(finding, "finding")
        if self.handoff.kind is not HandoffKind.SAFETY_REVIEW_RESULT:
            raise ValueError("safety review product requires safety_review_result")
        object.__setattr__(self, "findings", findings)
