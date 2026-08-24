from datetime import UTC, datetime

import pytest

from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Evidence,
)


def test_action_records_intent_without_claiming_execution() -> None:
    action = Action(
        action_id="ACT-001",
        incident_id="INC-001",
        tool_name="connectivity_probe",
        rationale="Compare the affected station with a healthy peer.",
        risk=ActionRisk.READ_ONLY,
        requested_at=datetime(2026, 8, 24, 8, 5, tzinfo=UTC),
        parameters={"target": "ST-02", "attempts": 3},
    )

    assert action.tool_name == "connectivity_probe"
    assert action.risk is ActionRisk.READ_ONLY
    assert not hasattr(action, "succeeded")


def test_action_copies_and_freezes_parameters() -> None:
    parameters = {"target": "ST-02"}
    action = Action(
        action_id="ACT-001",
        incident_id="INC-001",
        tool_name="connectivity_probe",
        rationale="Check whether the station is reachable.",
        risk=ActionRisk.READ_ONLY,
        requested_at=datetime(2026, 8, 24, 8, 5, tzinfo=UTC),
        parameters=parameters,
    )

    parameters["target"] = "ST-01"

    assert action.parameters["target"] == "ST-02"
    with pytest.raises(TypeError):
        action.parameters["target"] = "ST-01"  # type: ignore[index]


def test_action_rejects_blank_tool_name() -> None:
    with pytest.raises(ValueError, match="tool_name must not be blank"):
        Action(
            action_id="ACT-001",
            incident_id="INC-001",
            tool_name="  ",
            rationale="Check whether the station is reachable.",
            risk=ActionRisk.READ_ONLY,
            requested_at=datetime(2026, 8, 24, 8, 5, tzinfo=UTC),
        )


def test_evidence_connects_a_claim_to_observations() -> None:
    evidence = Evidence(
        evidence_id="EVD-001",
        incident_id="INC-001",
        claim="The failure is isolated to ST-02.",
        observation_ids=["OBS-001", "OBS-002"],  # type: ignore[arg-type]
        confidence=0.85,
        created_at=datetime(2026, 8, 24, 8, 8, tzinfo=UTC),
    )

    assert evidence.observation_ids == ("OBS-001", "OBS-002")
    assert evidence.confidence == 0.85


def test_evidence_requires_at_least_one_observation() -> None:
    with pytest.raises(ValueError, match="at least one observation"):
        Evidence(
            evidence_id="EVD-001",
            incident_id="INC-001",
            claim="The failure is isolated to ST-02.",
            observation_ids=(),
            confidence=0.85,
            created_at=datetime(2026, 8, 24, 8, 8, tzinfo=UTC),
        )


def test_evidence_rejects_duplicate_observation_references() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        Evidence(
            evidence_id="EVD-001",
            incident_id="INC-001",
            claim="The failure is isolated to ST-02.",
            observation_ids=("OBS-001", "OBS-001"),
            confidence=0.85,
            created_at=datetime(2026, 8, 24, 8, 8, tzinfo=UTC),
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01, True])
def test_evidence_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence must be between"):
        Evidence(
            evidence_id="EVD-001",
            incident_id="INC-001",
            claim="The failure is isolated to ST-02.",
            observation_ids=("OBS-001",),
            confidence=confidence,
            created_at=datetime(2026, 8, 24, 8, 8, tzinfo=UTC),
        )


def test_evidence_requires_timezone_aware_creation_time() -> None:
    with pytest.raises(ValueError, match="created_at must include timezone"):
        Evidence(
            evidence_id="EVD-001",
            incident_id="INC-001",
            claim="The failure is isolated to ST-02.",
            observation_ids=("OBS-001",),
            confidence=0.85,
            created_at=datetime(2026, 8, 24, 8, 8),
        )
