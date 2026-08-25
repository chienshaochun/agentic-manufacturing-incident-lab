"""Evidence-bound report specialist for approved diagnostic work."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
)
from agentic_manufacturing_incident_lab.collaboration.products import (
    DiagnosticWorkProduct,
    IncidentReport,
    ReportWorkProduct,
    SafetyReviewOutcome,
    SafetyReviewProduct,
)


class ReporterAgent:
    """Create a report from approved evidence without owning executable tools."""

    __slots__ = ()

    def handle(
        self,
        request: AgentHandoff,
        *,
        diagnostic: DiagnosticWorkProduct,
        safety_review: SafetyReviewProduct,
    ) -> ReportWorkProduct:
        """Produce one deterministic report after independent approval."""
        if request.kind is not HandoffKind.REPORT_REQUEST:
            raise ValueError("ReporterAgent requires report_request")
        if request.recipient is not AgentRole.REPORTER:
            raise ValueError("report request must target ReporterAgent")
        run = diagnostic.run
        if request.incident_id != run.incident.incident_id:
            raise ValueError("report request must match the diagnostic incident")
        if safety_review.outcome is not SafetyReviewOutcome.APPROVED:
            raise ValueError("ReporterAgent requires an approved safety review")
        if safety_review.handoff.incident_id != run.incident.incident_id:
            raise ValueError("safety review must match the diagnostic incident")
        if safety_review.handoff.action_ids != diagnostic.handoff.action_ids:
            raise ValueError("safety review must include every diagnostic action")
        if (
            safety_review.handoff.observation_ids
            != diagnostic.handoff.observation_ids
        ):
            raise ValueError("safety review must include every diagnostic observation")
        if request.action_ids != diagnostic.handoff.action_ids:
            raise ValueError("report request must include every diagnostic action")
        if request.observation_ids != diagnostic.handoff.observation_ids:
            raise ValueError("report request must include every diagnostic observation")
        if not run.evidence:
            raise ValueError("ReporterAgent requires evidence-backed completion")

        generated_at = request.created_at + timedelta(seconds=1)
        report = IncidentReport(
            report_id=f"RPT-{run.incident.incident_id}",
            incident_id=run.incident.incident_id,
            title=f"Incident investigation report: {run.incident.title}",
            executive_summary=(
                f"A diagnostic specialist completed {len(run.executions)} "
                f"authorized actions and collected {len(run.observations)} "
                "observations. An independent safety reviewer approved the record."
            ),
            conclusion=" ".join(evidence.claim for evidence in run.evidence),
            action_ids=request.action_ids,
            observation_ids=request.observation_ids,
            evidence_ids=tuple(evidence.evidence_id for evidence in run.evidence),
            generated_at=generated_at,
        )
        handoff = AgentHandoff(
            handoff_id=f"HND-{run.incident.incident_id}-REPORT-RESULT",
            incident_id=run.incident.incident_id,
            kind=HandoffKind.REPORT_RESULT,
            sender=AgentRole.REPORTER,
            recipient=AgentRole.COORDINATOR,
            purpose="Evidence-bound incident report completed.",
            created_at=generated_at,
            observation_ids=report.observation_ids,
            action_ids=report.action_ids,
            in_reply_to=request.handoff_id,
        )
        return ReportWorkProduct(report=report, handoff=handoff)
