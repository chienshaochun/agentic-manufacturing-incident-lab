from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab import Action, ActionRisk
from agentic_manufacturing_incident_lab.domain.models import ObservationKind
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    IncidentScopeError,
    ToolParameterError,
    build_diagnostic_registry,
)


def make_runtime(seed: int = 43):
    scenario = build_station_connectivity_scenario(seed=seed)
    environment = SimulatedEnvironment(scenario)
    registry = build_diagnostic_registry(environment)
    return scenario, environment, registry


def make_action(
    environment: SimulatedEnvironment,
    *,
    tool_name: str,
    asset_id: str = "ST-02",
    incident_id: str | None = None,
) -> Action:
    incident = environment.brief.incident
    return Action(
        action_id=f"ACT-{tool_name}",
        incident_id=incident.incident_id if incident_id is None else incident_id,
        tool_name=tool_name,
        rationale="Collect a read-only diagnostic measurement.",
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10),
        parameters={"asset_id": asset_id},
    )


def test_default_registry_contains_only_read_only_diagnostic_tools() -> None:
    _, _, registry = make_runtime()

    assert [(spec.name, spec.risk) for spec in registry.specs] == [
        ("check_connectivity", ActionRisk.READ_ONLY),
        ("read_telemetry", ActionRisk.READ_ONLY),
    ]


def test_connectivity_action_returns_environment_observation() -> None:
    _, environment, registry = make_runtime()

    response = registry.execute(
        make_action(environment, tool_name="check_connectivity", asset_id="ST-02")
    )

    assert response.summary == "Connectivity measurement completed for ST-02."
    assert len(response.observations) == 1
    observation = response.observations[0]
    assert observation.kind is ObservationKind.CONNECTIVITY
    assert observation.values["network_reachable"] is False
    assert environment.observation_count == 1


def test_telemetry_action_returns_environment_observation() -> None:
    _, environment, registry = make_runtime()

    response = registry.execute(
        make_action(environment, tool_name="read_telemetry", asset_id="ST-02")
    )

    observation = response.observations[0]
    assert observation.kind is ObservationKind.METRIC
    assert observation.values["telemetry_available"] is False


def test_same_actions_replay_identical_tool_responses() -> None:
    _, first_environment, first_registry = make_runtime()
    _, second_environment, second_registry = make_runtime()
    first_actions = (
        make_action(first_environment, tool_name="check_connectivity", asset_id="ST-02"),
        make_action(first_environment, tool_name="check_connectivity", asset_id="ST-01"),
        make_action(first_environment, tool_name="read_telemetry", asset_id="ST-02"),
    )
    second_actions = (
        make_action(second_environment, tool_name="check_connectivity", asset_id="ST-02"),
        make_action(second_environment, tool_name="check_connectivity", asset_id="ST-01"),
        make_action(second_environment, tool_name="read_telemetry", asset_id="ST-02"),
    )

    first_responses = tuple(first_registry.execute(action) for action in first_actions)
    second_responses = tuple(second_registry.execute(action) for action in second_actions)

    assert first_responses == second_responses


def test_action_for_different_incident_cannot_read_environment() -> None:
    _, environment, registry = make_runtime()

    with pytest.raises(IncidentScopeError, match="does not match environment incident"):
        registry.execute(
            make_action(
                environment,
                tool_name="check_connectivity",
                incident_id="INC-OTHER",
            )
        )

    assert environment.observation_count == 0


def test_invalid_tool_parameter_does_not_measure_environment() -> None:
    _, environment, registry = make_runtime()
    incident = environment.brief.incident
    action = Action(
        action_id="ACT-invalid",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Attempt an invalid measurement.",
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10),
        parameters={"asset_id": 2},
    )

    with pytest.raises(ToolParameterError, match="asset_id must be string"):
        registry.execute(action)

    assert environment.observation_count == 0


def test_unknown_asset_failure_does_not_advance_environment() -> None:
    _, environment, registry = make_runtime()

    with pytest.raises(KeyError, match="unknown asset_id: ST-99"):
        registry.execute(
            make_action(environment, tool_name="check_connectivity", asset_id="ST-99")
        )

    assert environment.observation_count == 0
