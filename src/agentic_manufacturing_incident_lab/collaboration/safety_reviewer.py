"""Independent safety and evidence reviewer for diagnostic work products."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
)
from agentic_manufacturing_incident_lab.collaboration.products import (
    DiagnosticWorkProduct,
    SafetyReviewOutcome,
    SafetyReviewProduct,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.safety import (
    ApprovalOutcome,
    SafetyDisposition,
)


class SafetyReviewerAgent:
    """Review a complete diagnostic scope without owning executable tools."""

    __slots__ = ()

    def handle(
        self,
        request: AgentHandoff,
        *,
        diagnostic: DiagnosticWorkProduct,
    ) -> SafetyReviewProduct:
        """Return an independent verdict over safety and evidence completeness."""
        if request.kind is not HandoffKind.SAFETY_REVIEW_REQUEST:
            raise ValueError("SafetyReviewerAgent requires safety_review_request")
        if request.recipient is not AgentRole.SAFETY_REVIEWER:
            raise ValueError("safety review request must target SafetyReviewerAgent")
        run = diagnostic.run
        if request.incident_id != run.incident.incident_id:
            raise ValueError("safety review request must match the diagnostic incident")
        if request.action_ids != diagnostic.handoff.action_ids:
            raise ValueError("safety review request must include every diagnostic action")
        if request.observation_ids != diagnostic.handoff.observation_ids:
            raise ValueError(
                "safety review request must include every diagnostic observation"
            )

        outcome, rationale, findings = self._review(diagnostic)
        handoff = AgentHandoff(
            handoff_id=f"HND-{run.incident.incident_id}-SAFETY-RESULT",
            incident_id=run.incident.incident_id,
            kind=HandoffKind.SAFETY_REVIEW_RESULT,
            sender=AgentRole.SAFETY_REVIEWER,
            recipient=AgentRole.COORDINATOR,
            purpose=f"Safety review {outcome.value}: {rationale}",
            created_at=request.created_at + timedelta(seconds=1),
            observation_ids=request.observation_ids,
            action_ids=request.action_ids,
            in_reply_to=request.handoff_id,
        )
        return SafetyReviewProduct(
            outcome=outcome,
            rationale=rationale,
            findings=findings,
            handoff=handoff,
        )

    @staticmethod
    def _review(
        diagnostic: DiagnosticWorkProduct,
    ) -> tuple[SafetyReviewOutcome, str, tuple[str, ...]]:
        run = diagnostic.run
        findings: list[str] = []
        assessments_by_action_id = {
            assessment.action_id: assessment
            for assessment in run.safety_assessments
        }
        approved_action_ids = {
            decision.request.action.action_id
            for decision in run.approval_decisions
            if decision.outcome is ApprovalOutcome.APPROVED
        }
        rejected_action_ids = {
            decision.request.action.action_id
            for decision in run.approval_decisions
            if decision.outcome is ApprovalOutcome.REJECTED
        }

        unauthorized_action_ids: list[str] = []
        for record in run.executions:
            action_id = record.action.action_id
            assessment = assessments_by_action_id.get(action_id)
            if assessment is None:
                unauthorized_action_ids.append(action_id)
                continue
            if assessment.disposition is SafetyDisposition.ALLOW:
                continue
            if (
                assessment.disposition is SafetyDisposition.REQUIRE_APPROVAL
                and action_id in approved_action_ids
            ):
                continue
            unauthorized_action_ids.append(action_id)

        if unauthorized_action_ids:
            findings.append(
                "Executed actions without valid authorization: "
                + ", ".join(unauthorized_action_ids)
            )
        if rejected_action_ids:
            findings.append(
                "Human-rejected actions remained unexecuted as required: "
                + ", ".join(sorted(rejected_action_ids))
            )

        if unauthorized_action_ids:
            return (
                SafetyReviewOutcome.REJECTED,
                "The execution history does not satisfy authorization controls.",
                tuple(findings),
            )

        if run.final_state.status is TaskStatus.WAITING_APPROVAL:
            findings.append("The investigation is waiting for a human decision.")
            return (
                SafetyReviewOutcome.REQUIRES_ATTENTION,
                "Human approval must be resolved before review can pass.",
                tuple(findings),
            )

        if run.final_state.status is not TaskStatus.COMPLETED or not run.evidence:
            findings.append(
                f"The diagnostic run ended as {run.final_state.status.value} "
                "without completion evidence."
            )
            return (
                SafetyReviewOutcome.REQUIRES_ATTENTION,
                "The run is safe to retain but does not support a final report.",
                tuple(findings),
            )

        findings.append(
            f"Reviewed {len(run.executions)} authorized actions and "
            f"{len(run.evidence)} evidence record."
        )
        return (
            SafetyReviewOutcome.APPROVED,
            "All executed actions were authorized and completion is evidence-backed.",
            tuple(findings),
        )
