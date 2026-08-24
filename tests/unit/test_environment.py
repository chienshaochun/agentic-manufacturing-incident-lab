from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab.domain.models import ObservationKind
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)


def make_environment(seed: int = 43) -> SimulatedEnvironment:
    return SimulatedEnvironment(build_station_connectivity_scenario(seed=seed))


def test_environment_exposes_brief_without_public_scenario_answer() -> None:
    environment = make_environment()

    assert environment.brief.incident.asset_id == "ST-02"
    assert not hasattr(environment.brief, "root_cause_code")
    assert not hasattr(environment, "scenario")


def test_connectivity_measurement_reflects_affected_asset_truth() -> None:
    observation = make_environment().measure_connectivity("ST-02")

    assert observation.kind is ObservationKind.CONNECTIVITY
    assert observation.source == "simulated_connectivity_sensor"
    assert observation.values == {
        "asset_id": "ST-02",
        "network_reachable": False,
    }


def test_connectivity_measurement_distinguishes_healthy_peer() -> None:
    environment = make_environment()

    affected = environment.measure_connectivity("ST-02")
    healthy = environment.measure_connectivity("ST-01")

    assert affected.values["network_reachable"] is False
    assert healthy.values["network_reachable"] is True


def test_telemetry_measurement_uses_metric_observation() -> None:
    observation = make_environment().measure_telemetry("ST-02")

    assert observation.kind is ObservationKind.METRIC
    assert observation.source == "simulated_telemetry_sensor"
    assert observation.values["telemetry_available"] is False


def test_measurements_advance_deterministic_ids_and_clock() -> None:
    environment = make_environment()
    reported_at = environment.brief.incident.reported_at

    first = environment.measure_connectivity("ST-02")
    second = environment.measure_connectivity("ST-01")

    assert first.observation_id.endswith("OBS-001")
    assert second.observation_id.endswith("OBS-002")
    assert first.observed_at == reported_at + timedelta(seconds=30)
    assert second.observed_at == reported_at + timedelta(seconds=60)
    assert environment.current_time == second.observed_at
    assert environment.observation_count == 2


def test_same_query_sequence_replays_identical_observations() -> None:
    first_environment = make_environment()
    second_environment = make_environment()

    first_run = (
        first_environment.measure_connectivity("ST-02"),
        first_environment.measure_connectivity("ST-01"),
        first_environment.measure_telemetry("ST-02"),
    )
    second_run = (
        second_environment.measure_connectivity("ST-02"),
        second_environment.measure_connectivity("ST-01"),
        second_environment.measure_telemetry("ST-02"),
    )

    assert first_run == second_run


def test_unknown_asset_does_not_advance_environment() -> None:
    environment = make_environment()

    with pytest.raises(KeyError, match="unknown asset_id: ST-99"):
        environment.measure_connectivity("ST-99")

    assert environment.observation_count == 0
    assert environment.current_time == environment.brief.incident.reported_at
