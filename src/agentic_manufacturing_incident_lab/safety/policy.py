"""Default least-privilege safety policy and approval record factories."""

from datetime import datetime

from agentic_manufacturing_incident_lab.domain._validation import require_timezone
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.safety.contracts import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    SafetyAssessment,
    SafetyDisposition,
)


class RiskBasedSafetyPolicy:
    """Allow reads, require approval for writes, and deny high-impact actions."""

    name = "least_privilege_risk_policy_v1"

    def assess(self, action: Action, *, assessed_at: datetime) -> SafetyAssessment:
        """Classify an action using its registry-resolved risk level."""
        require_timezone(assessed_at, "assessed_at")
        if assessed_at < action.requested_at:
            raise ValueError("safety assessment cannot precede action request")

        if action.risk is ActionRisk.READ_ONLY:
            disposition = SafetyDisposition.ALLOW
            rationale = "Read-only diagnostic actions are allowed by default."
        elif action.risk is ActionRisk.CONTROLLED_WRITE:
            disposition = SafetyDisposition.REQUIRE_APPROVAL
            rationale = "Controlled-write actions require explicit human approval."
        else:
            disposition = SafetyDisposition.DENY
            rationale = "High-impact actions are denied by the default safety policy."

        return SafetyAssessment(
            assessment_id=f"SAF-{action.action_id}",
            action_id=action.action_id,
            incident_id=action.incident_id,
            policy_name=self.name,
            disposition=disposition,
            rationale=rationale,
            assessed_at=assessed_at,
        )


def create_approval_request(
    action: Action,
    assessment: SafetyAssessment,
    *,
    requested_at: datetime,
) -> ApprovalRequest:
    """Create the deterministic request associated with one assessed action."""
    return ApprovalRequest(
        request_id=f"APR-{action.action_id}",
        action=action,
        assessment=assessment,
        reason=assessment.rationale,
        requested_at=requested_at,
    )


def record_approval_decision(
    request: ApprovalRequest,
    *,
    outcome: ApprovalOutcome,
    decided_by: str,
    rationale: str,
    decided_at: datetime,
) -> ApprovalDecision:
    """Create one attributable terminal decision for an approval request."""
    return ApprovalDecision(
        decision_id=f"APD-{request.request_id}",
        request=request,
        outcome=outcome,
        decided_by=decided_by,
        rationale=rationale,
        decided_at=decided_at,
    )
