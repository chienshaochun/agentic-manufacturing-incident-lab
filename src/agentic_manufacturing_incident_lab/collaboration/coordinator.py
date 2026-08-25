"""Central coordinator for the deterministic multi-agent workflow."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
    HandoffLedger,
)
from agentic_manufacturing_incident_lab.collaboration.diagnostic import DiagnosticAgent
from agentic_manufacturing_incident_lab.collaboration.products import (
    MultiAgentRun,
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.collaboration.reporter import ReporterAgent
from agentic_manufacturing_incident_lab.collaboration.safety_reviewer import (
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.domain.models import Incident


class CoordinatorAgent:
    """Route one incident through diagnostic, safety, and reporting specialists."""

    __slots__ = ("_diagnostic", "_reporter", "_safety_reviewer")

    def __init__(
        self,
        *,
        diagnostic: DiagnosticAgent,
        safety_reviewer: SafetyReviewerAgent,
        reporter: ReporterAgent,
    ) -> None:
        self._diagnostic = diagnostic
        self._safety_reviewer = safety_reviewer
        self._reporter = reporter

    def run(
        self,
        *,
        incident: Incident,
        known_asset_ids: tuple[str, ...],
    ) -> MultiAgentRun:
        """Run the synchronous specialist workflow with auditable handoffs."""
        ledger = HandoffLedger(incident_id=incident.incident_id)
        investigation_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-INVESTIGATE",
            incident_id=incident.incident_id,
            kind=HandoffKind.INVESTIGATION_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.DIAGNOSTIC,
            purpose=incident.goal,
            created_at=incident.reported_at,
        )
        ledger = ledger.append(investigation_request)
        diagnostic = self._diagnostic.handle(
            investigation_request,
            incident=incident,
            known_asset_ids=known_asset_ids,
        )
        ledger = ledger.append(diagnostic.handoff)

        safety_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-SAFETY-REVIEW",
            incident_id=incident.incident_id,
            kind=HandoffKind.SAFETY_REVIEW_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.SAFETY_REVIEWER,
            purpose="Review all diagnostic actions, approvals, and evidence.",
            created_at=diagnostic.handoff.created_at + timedelta(seconds=1),
            observation_ids=diagnostic.handoff.observation_ids,
            action_ids=diagnostic.handoff.action_ids,
        )
        ledger = ledger.append(safety_request)
        safety_review = self._safety_reviewer.handle(
            safety_request,
            diagnostic=diagnostic,
        )
        ledger = ledger.append(safety_review.handoff)

        if safety_review.outcome is not SafetyReviewOutcome.APPROVED:
            return MultiAgentRun(
                status=MultiAgentStatus.SAFE_STOPPED,
                ledger=ledger,
                diagnostic=diagnostic,
                safety_review=safety_review,
            )

        report_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-REPORT",
            incident_id=incident.incident_id,
            kind=HandoffKind.REPORT_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.REPORTER,
            purpose="Produce an evidence-bound report from the approved record.",
            created_at=safety_review.handoff.created_at + timedelta(seconds=1),
            observation_ids=diagnostic.handoff.observation_ids,
            action_ids=diagnostic.handoff.action_ids,
        )
        ledger = ledger.append(report_request)
        report = self._reporter.handle(
            report_request,
            diagnostic=diagnostic,
            safety_review=safety_review,
        )
        ledger = ledger.append(report.handoff)
        return MultiAgentRun(
            status=MultiAgentStatus.COMPLETED,
            ledger=ledger,
            diagnostic=diagnostic,
            safety_review=safety_review,
            report=report,
        )
