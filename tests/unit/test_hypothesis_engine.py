from datetime import datetime, timedelta, timezone

import pytest

from agentic_manufacturing_incident_lab.domain import (
    HypothesisStatus,
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
)
from agentic_manufacturing_incident_lab.hypotheses import (
    ConnectivityHypothesisPolicy,
    HypothesisDefinition,
    evaluate_hypotheses,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _incident() -> Incident:
    return Incident(
        incident_id="INC-001",
        title="Station connectivity failure",
        description="ST-02 is unreachable.",
        asset_id="ST-02",
        severity=IncidentSeverity.WARNING,
        reported_at=NOW,
        goal="Localize the connectivity failure.",
    )


def _observation(sequence: int, asset_id: str, **values: bool) -> Observation:
    return Observation(
        observation_id=f"OBS-{sequence:03d}",
        incident_id="INC-001",
        source="simulator",
        kind=(
            ObservationKind.CONNECTIVITY
            if "network_reachable" in values
            else ObservationKind.METRIC
        ),
        summary=f"Measurement {sequence} completed.",
        observed_at=NOW + timedelta(seconds=sequence),
        values={"asset_id": asset_id, **values},
    )


def _by_suffix(hypotheses, suffix: str):
    return next(item for item in hypotheses if item.hypothesis_id.endswith(suffix))


def test_connectivity_policy_starts_with_three_open_hypotheses() -> None:
    hypotheses = ConnectivityHypothesisPolicy().evaluate(
        _incident(),
        (),
        evaluated_at=NOW,
    )

    assert len(hypotheses) == 3
    assert {item.status for item in hypotheses} == {HypothesisStatus.OPEN}


def test_isolated_station_observations_support_and_reject_competing_causes() -> None:
    observations = (
        _observation(1, "ST-02", network_reachable=False),
        _observation(2, "ST-01", network_reachable=True),
        _observation(3, "ST-02", telemetry_available=False),
    )

    hypotheses = ConnectivityHypothesisPolicy().evaluate(
        _incident(),
        observations,
        evaluated_at=NOW + timedelta(seconds=4),
    )

    station = _by_suffix(hypotheses, "-STATION")
    shared = _by_suffix(hypotheses, "-SHARED")
    assert station.status is HypothesisStatus.SUPPORTED
    assert station.confidence == pytest.approx(0.95)
    assert station.supporting_observation_ids == ("OBS-001", "OBS-002", "OBS-003")
    assert shared.status is HypothesisStatus.REJECTED
    assert shared.contradicting_observation_ids == ("OBS-002",)


def test_peer_failure_supports_shared_infrastructure_hypothesis() -> None:
    observations = (
        _observation(1, "ST-02", network_reachable=False),
        _observation(2, "ST-01", network_reachable=False),
    )

    hypotheses = ConnectivityHypothesisPolicy().evaluate(
        _incident(),
        observations,
        evaluated_at=NOW + timedelta(seconds=3),
    )

    assert _by_suffix(hypotheses, "-SHARED").status is HypothesisStatus.SUPPORTED
    assert _by_suffix(hypotheses, "-STATION").status is HypothesisStatus.REJECTED


def test_conflicting_signal_for_same_observation_is_rejected() -> None:
    from agentic_manufacturing_incident_lab.domain import (
        HypothesisEffect,
        HypothesisSignal,
    )

    definitions = (HypothesisDefinition("HYP-001", "Candidate cause."),)
    signals = (
        HypothesisSignal("HYP-001", "OBS-001", HypothesisEffect.SUPPORTS, 0.5, "A"),
        HypothesisSignal("HYP-001", "OBS-001", HypothesisEffect.CONTRADICTS, 0.5, "B"),
    )

    with pytest.raises(ValueError, match="conflicting signals"):
        evaluate_hypotheses(
            incident=_incident(),
            definitions=definitions,
            signals=signals,
            evaluated_at=NOW,
        )
