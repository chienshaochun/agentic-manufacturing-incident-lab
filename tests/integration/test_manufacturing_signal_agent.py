import pytest

from agentic_manufacturing_incident_lab.agent import (
    ManufacturingSignalPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.domain import HypothesisStatus, TaskStatus
from agentic_manufacturing_incident_lab.hypotheses import (
    ManufacturingSignalHypothesisPolicy,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_configuration_drift_scenario,
    build_sensor_staleness_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    build_manufacturing_diagnostic_registry,
)


@pytest.mark.parametrize(
    ("scenario_factory", "winner_suffix", "claim_fragment"),
    [
        (build_sensor_staleness_scenario, "-SENSOR", "stale sensor data"),
        (build_configuration_drift_scenario, "-CONFIG", "configuration drift"),
    ],
)
def test_multi_source_agent_isolates_different_causes_for_same_symptom(
    scenario_factory,
    winner_suffix: str,
    claim_fragment: str,
) -> None:
    environment = SimulatedEnvironment(scenario_factory())
    run = SingleAgentRunner(
        policy=ManufacturingSignalPlanner(),
        registry=build_manufacturing_diagnostic_registry(environment),
        hypothesis_policy=ManufacturingSignalHypothesisPolicy(),
    ).run(
        incident=environment.brief.incident,
        known_asset_ids=environment.brief.known_asset_ids,
    )

    assert run.final_state.status is TaskStatus.COMPLETED
    assert [record.action.tool_name for record in run.executions] == [
        "read_alarm_history",
        "check_connectivity",
        "read_telemetry",
        "inspect_configuration",
        "read_maintenance_record",
        "check_sensor_freshness",
    ]
    supported = [
        item for item in run.hypotheses
        if item.status is HypothesisStatus.SUPPORTED
    ]
    assert len(supported) == 1
    assert supported[0].hypothesis_id.endswith(winner_suffix)
    assert all(
        item.status is HypothesisStatus.REJECTED
        for item in run.hypotheses
        if item is not supported[0]
    )
    assert claim_fragment in run.evidence[0].claim
    assert run.evidence[0].observation_ids == tuple(
        observation.observation_id for observation in run.observations
    )
