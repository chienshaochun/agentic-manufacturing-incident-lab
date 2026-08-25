"""Immutable contracts for action safety assessments and human approval."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)
from agentic_manufacturing_incident_lab.domain.models import Action


class SafetyDisposition(StrEnum):
    """Runtime treatment assigned to one proposed action."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class SafetyAssessment:
    """One auditable policy assessment of a proposed action."""

    assessment_id: str
    action_id: str
    incident_id: str
    policy_name: str
    disposition: SafetyDisposition
    rationale: str
    assessed_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "assessment_id",
            "action_id",
            "incident_id",
            "policy_name",
            "rationale",
        ):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.assessed_at, "assessed_at")


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A controlled-write action waiting for an explicit human decision."""

    request_id: str
    action: Action
    assessment: SafetyAssessment
    reason: str
    requested_at: datetime

    def __post_init__(self) -> None:
        require_text(self.request_id, "request_id")
        require_text(self.reason, "reason")
        require_timezone(self.requested_at, "requested_at")
        if self.assessment.action_id != self.action.action_id:
            raise ValueError("assessment action_id must match approval action")
        if self.assessment.incident_id != self.action.incident_id:
            raise ValueError("assessment incident_id must match approval action")
        if self.assessment.disposition is not SafetyDisposition.REQUIRE_APPROVAL:
            raise ValueError("approval request requires an approval disposition")
        if self.requested_at < self.assessment.assessed_at:
            raise ValueError("approval request cannot precede safety assessment")


class ApprovalOutcome(StrEnum):
    """Terminal human decision for one approval request."""

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """One attributable and timestamped human approval or rejection."""

    decision_id: str
    request: ApprovalRequest
    outcome: ApprovalOutcome
    decided_by: str
    rationale: str
    decided_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "decided_by", "rationale"):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.decided_at, "decided_at")
        if self.decided_at <= self.request.requested_at:
            raise ValueError("approval decision must follow approval request")


@runtime_checkable
class SafetyPolicy(Protocol):
    """Interchangeable policy that assesses a fully resolved Action."""

    name: str

    def assess(self, action: Action, *, assessed_at: datetime) -> SafetyAssessment:
        """Assign one allow, approval, or deny disposition."""
        ...
