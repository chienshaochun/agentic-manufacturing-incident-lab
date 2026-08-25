"""Structured work products returned by specialist agents."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    HandoffKind,
    HandoffLedger,
)
from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)
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


@dataclass(frozen=True, slots=True)
class IncidentReport:
    """Evidence-bound report produced after an approved safety review."""

    report_id: str
    incident_id: str
    title: str
    executive_summary: str
    conclusion: str
    action_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "report_id",
            "incident_id",
            "title",
            "executive_summary",
            "conclusion",
        ):
            require_text(getattr(self, field_name), field_name)
        for field_name in ("action_ids", "observation_ids", "evidence_ids"):
            values = tuple(getattr(self, field_name))
            if not values:
                raise ValueError(f"{field_name} must not be empty")
            for value in values:
                require_text(value, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicates")
            object.__setattr__(self, field_name, values)
        require_timezone(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class ReportWorkProduct:
    """An evidence-bound report paired with its reporter handoff."""

    report: IncidentReport
    handoff: AgentHandoff

    def __post_init__(self) -> None:
        if self.handoff.kind is not HandoffKind.REPORT_RESULT:
            raise ValueError("report work product requires report_result")
        if self.handoff.incident_id != self.report.incident_id:
            raise ValueError("report handoff must match the report incident")
        if self.handoff.action_ids != self.report.action_ids:
            raise ValueError("report handoff must reference every report action")
        if self.handoff.observation_ids != self.report.observation_ids:
            raise ValueError("report handoff must reference every report observation")


class MultiAgentStatus(StrEnum):
    """Terminal outcome of the first coordinated specialist workflow."""

    COMPLETED = "completed"
    SAFE_STOPPED = "safe_stopped"


@dataclass(frozen=True, slots=True)
class MultiAgentRun:
    """Aggregate containing all specialist outputs and communication history."""

    status: MultiAgentStatus
    ledger: HandoffLedger
    diagnostic: DiagnosticWorkProduct
    safety_review: SafetyReviewProduct
    report: ReportWorkProduct | None = None

    def __post_init__(self) -> None:
        incident_id = self.diagnostic.run.incident.incident_id
        if self.ledger.incident_id != incident_id:
            raise ValueError("multi-agent ledger must match diagnostic incident")
        ledger_handoffs = set(self.ledger.handoffs)
        required_handoffs = {
            self.diagnostic.handoff,
            self.safety_review.handoff,
        }
        if not required_handoffs.issubset(ledger_handoffs):
            raise ValueError("multi-agent ledger must contain specialist handoffs")
        if self.safety_review.handoff.incident_id != incident_id:
            raise ValueError("safety review must match diagnostic incident")
        if self.safety_review.handoff.action_ids != self.diagnostic.handoff.action_ids:
            raise ValueError("safety review must cover every diagnostic action")
        if (
            self.safety_review.handoff.observation_ids
            != self.diagnostic.handoff.observation_ids
        ):
            raise ValueError("safety review must cover every diagnostic observation")

        expected_kinds = (
            HandoffKind.INVESTIGATION_REQUEST,
            HandoffKind.DIAGNOSTIC_RESULT,
            HandoffKind.SAFETY_REVIEW_REQUEST,
            HandoffKind.SAFETY_REVIEW_RESULT,
        )
        if self.status is MultiAgentStatus.COMPLETED:
            expected_kinds = (
                *expected_kinds,
                HandoffKind.REPORT_REQUEST,
                HandoffKind.REPORT_RESULT,
            )
        if tuple(handoff.kind for handoff in self.ledger.handoffs) != expected_kinds:
            raise ValueError("multi-agent ledger has an invalid workflow sequence")

        if self.status is MultiAgentStatus.COMPLETED:
            if self.safety_review.outcome is not SafetyReviewOutcome.APPROVED:
                raise ValueError("completed multi-agent run requires approved review")
            if self.report is None:
                raise ValueError("completed multi-agent run requires a report")
        elif self.report is not None:
            raise ValueError("safe-stopped multi-agent run must not contain a report")

        if self.report is not None:
            if self.report.report.incident_id != incident_id:
                raise ValueError("report must match diagnostic incident")
            if self.report.handoff not in ledger_handoffs:
                raise ValueError("multi-agent ledger must contain report handoff")
            if self.report.report.action_ids != self.diagnostic.handoff.action_ids:
                raise ValueError("report must include every diagnostic action")
            if (
                self.report.report.observation_ids
                != self.diagnostic.handoff.observation_ids
            ):
                raise ValueError("report must include every diagnostic observation")
            evidence_ids = tuple(
                evidence.evidence_id for evidence in self.diagnostic.run.evidence
            )
            if self.report.report.evidence_ids != evidence_ids:
                raise ValueError("report must include every diagnostic evidence record")
        if self.ledger.pending_requests:
            raise ValueError("terminal multi-agent run must not contain pending requests")
