from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.safety import (
    ApprovalOutcome,
    RiskBasedSafetyPolicy,
    SafetyDisposition,
    SafetyPolicy,
    create_approval_request,
    record_approval_decision,
)

REQUESTED_AT = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)


def make_action(risk: ActionRisk = ActionRisk.READ_ONLY) -> Action:
    return Action(
        action_id="ACT-001",
        incident_id="INC-001",
        tool_name="diagnostic_tool",
        rationale="Perform one policy-controlled operation.",
        risk=risk,
        requested_at=REQUESTED_AT,
        parameters={"asset_id": "ST-02"},
    )


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (ActionRisk.READ_ONLY, SafetyDisposition.ALLOW),
        (ActionRisk.CONTROLLED_WRITE, SafetyDisposition.REQUIRE_APPROVAL),
        (ActionRisk.HIGH_IMPACT, SafetyDisposition.DENY),
    ],
)
def test_default_policy_maps_risk_to_least_privilege_disposition(
    risk: ActionRisk,
    expected: SafetyDisposition,
) -> None:
    action = make_action(risk)

    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )

    assert assessment.disposition is expected
    assert assessment.action_id == action.action_id
    assert assessment.incident_id == action.incident_id
    assert assessment.assessment_id == "SAF-ACT-001"


def test_default_policy_satisfies_safety_protocol() -> None:
    assert isinstance(RiskBasedSafetyPolicy(), SafetyPolicy)


def test_safety_assessment_is_deterministic_and_immutable() -> None:
    action = make_action()
    assessed_at = REQUESTED_AT + timedelta(seconds=1)
    first = RiskBasedSafetyPolicy().assess(action, assessed_at=assessed_at)
    second = RiskBasedSafetyPolicy().assess(action, assessed_at=assessed_at)

    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.rationale = "Changed"  # type: ignore[misc]


def test_safety_assessment_cannot_precede_action_request() -> None:
    with pytest.raises(ValueError, match="cannot precede"):
        RiskBasedSafetyPolicy().assess(
            make_action(),
            assessed_at=REQUESTED_AT - timedelta(seconds=1),
        )


def test_controlled_write_creates_self_contained_approval_request() -> None:
    action = make_action(ActionRisk.CONTROLLED_WRITE)
    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )

    request = create_approval_request(
        action,
        assessment,
        requested_at=REQUESTED_AT + timedelta(seconds=2),
    )

    assert request.request_id == "APR-ACT-001"
    assert request.action == action
    assert request.assessment == assessment
    assert request.reason == assessment.rationale


def test_approval_request_rejects_nonapproval_assessment() -> None:
    action = make_action(ActionRisk.READ_ONLY)
    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="requires an approval disposition"):
        create_approval_request(
            action,
            assessment,
            requested_at=REQUESTED_AT + timedelta(seconds=2),
        )


def test_approval_request_rejects_mismatched_action() -> None:
    action = make_action(ActionRisk.CONTROLLED_WRITE)
    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )
    other_action = replace(action, action_id="ACT-OTHER")

    with pytest.raises(ValueError, match="action_id must match"):
        create_approval_request(
            other_action,
            assessment,
            requested_at=REQUESTED_AT + timedelta(seconds=2),
        )


@pytest.mark.parametrize("outcome", list(ApprovalOutcome))
def test_approval_decision_records_actor_reason_and_outcome(
    outcome: ApprovalOutcome,
) -> None:
    action = make_action(ActionRisk.CONTROLLED_WRITE)
    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )
    request = create_approval_request(
        action,
        assessment,
        requested_at=REQUESTED_AT + timedelta(seconds=2),
    )

    decision = record_approval_decision(
        request,
        outcome=outcome,
        decided_by="operator-01",
        rationale="Reviewed against the synthetic maintenance plan.",
        decided_at=REQUESTED_AT + timedelta(seconds=3),
    )

    assert decision.decision_id == "APD-APR-ACT-001"
    assert decision.request == request
    assert decision.outcome is outcome
    assert decision.decided_by == "operator-01"


def test_approval_decision_must_follow_request() -> None:
    action = make_action(ActionRisk.CONTROLLED_WRITE)
    assessment = RiskBasedSafetyPolicy().assess(
        action,
        assessed_at=REQUESTED_AT + timedelta(seconds=1),
    )
    request = create_approval_request(
        action,
        assessment,
        requested_at=REQUESTED_AT + timedelta(seconds=2),
    )

    with pytest.raises(ValueError, match="must follow"):
        record_approval_decision(
            request,
            outcome=ApprovalOutcome.APPROVED,
            decided_by="operator-01",
            rationale="Invalid decision time.",
            decided_at=request.requested_at,
        )
