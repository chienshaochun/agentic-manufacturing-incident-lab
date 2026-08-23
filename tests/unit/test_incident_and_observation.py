from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from agentic_manufacturing_incident_lab.domain.models import (
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
)


def make_incident() -> Incident:
    return Incident(
        incident_id="INC-001",
        title="Station connectivity failure",
        description="ST-02 cannot reach the telemetry gateway.",
        asset_id="ST-02",
        severity=IncidentSeverity.WARNING,
        reported_at=datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
        goal="Determine the most likely fault domain.",
    )


def test_incident_represents_a_reported_problem() -> None:
    incident = make_incident()

    assert incident.incident_id == "INC-001"
    assert incident.asset_id == "ST-02"
    assert incident.severity is IncidentSeverity.WARNING


def test_incident_is_immutable() -> None:
    incident = make_incident()

    with pytest.raises(FrozenInstanceError):
        incident.title = "Changed after reporting"  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["incident_id", "title", "description", "asset_id", "goal"])
def test_incident_rejects_blank_required_text(field_name: str) -> None:
    values = {
        "incident_id": "INC-001",
        "title": "Station connectivity failure",
        "description": "ST-02 cannot reach the telemetry gateway.",
        "asset_id": "ST-02",
        "severity": IncidentSeverity.WARNING,
        "reported_at": datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
        "goal": "Determine the most likely fault domain.",
    }
    values[field_name] = "   "

    with pytest.raises(ValueError, match=f"{field_name} must not be blank"):
        Incident(**values)  # type: ignore[arg-type]


def test_records_require_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="reported_at must include timezone"):
        Incident(
            incident_id="INC-001",
            title="Station connectivity failure",
            description="ST-02 cannot reach the telemetry gateway.",
            asset_id="ST-02",
            severity=IncidentSeverity.WARNING,
            reported_at=datetime(2026, 8, 23, 8, 0),
            goal="Determine the most likely fault domain.",
        )


def test_observation_is_linked_to_incident_and_preserves_evidence() -> None:
    raw_values = {"reachable": False, "packet_loss_percent": 100.0}
    observation = Observation(
        observation_id="OBS-001",
        incident_id="INC-001",
        source="connectivity_probe",
        kind=ObservationKind.CONNECTIVITY,
        summary="ST-02 did not respond to the simulated probe.",
        observed_at=datetime(2026, 8, 23, 8, 2, tzinfo=UTC),
        values=raw_values,
    )

    raw_values["reachable"] = True

    assert observation.incident_id == "INC-001"
    assert observation.values["reachable"] is False
    with pytest.raises(TypeError):
        observation.values["reachable"] = True  # type: ignore[index]
