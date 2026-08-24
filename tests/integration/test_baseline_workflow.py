from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.runtime import InvestigationRun
from agentic_manufacturing_incident_lab.simulation import (
    AssetRole,
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.workflows import (
    BaselineConfigurationError,
    run_station_connectivity_baseline,
)


def run_baseline(seed: int = 43) -> InvestigationRun:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=seed))
    return run_station_connectivity_baseline(environment)


def test_baseline_completes_fixed_three_action_sop() -> None:
    run = run_baseline()

    assert run.final_state.status is TaskStatus.COMPLETED
    assert len(run.executions) == 3
    assert all(
        record.result.status is ActionResultStatus.SUCCEEDED
        for record in run.executions
    )
    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "check_connectivity",
        "read_telemetry",
    ]


def test_baseline_compares_reported_station_with_a_peer() -> None:
    run = run_baseline(seed=43)

    assert [record.action.parameters["asset_id"] for record in run.executions] == [
        "ST-02",
        "ST-01",
        "ST-02",
    ]


@pytest.mark.parametrize("seed", [42, 43, 44])
def test_baseline_handles_each_possible_affected_station(seed: int) -> None:
    run = run_baseline(seed=seed)
    affected_asset_id = run.incident.asset_id
    compared_asset_id = run.executions[1].action.parameters["asset_id"]

    assert run.final_state.status is TaskStatus.COMPLETED
    assert compared_asset_id != affected_asset_id


def test_baseline_evidence_references_every_recorded_observation() -> None:
    run = run_baseline()

    assert len(run.evidence) == 1
    evidence = run.evidence[0]
    assert evidence.claim == "The connectivity failure is isolated to ST-02."
    assert evidence.confidence == 0.95
    assert evidence.observation_ids == tuple(
        observation.observation_id for observation in run.observations
    )


def test_baseline_preserves_contiguous_task_state_history() -> None:
    run = run_baseline()

    assert [state.revision for state in run.task_states] == [0, 1, 2]
    assert [state.status for state in run.task_states] == [
        TaskStatus.CREATED,
        TaskStatus.INVESTIGATING,
        TaskStatus.COMPLETED,
    ]
    assert all(
        later.updated_at > earlier.updated_at
        for earlier, later in zip(run.task_states, run.task_states[1:])
    )


def test_same_seed_replays_identical_investigation_run() -> None:
    assert run_baseline(seed=43) == run_baseline(seed=43)


def test_baseline_fails_when_observations_do_not_match_expected_pattern() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    healthy_assets = tuple(
        replace(
            asset,
            network_reachable=True,
            telemetry_available=True,
            alarm_codes=(),
        )
        for asset in scenario.assets
    )
    environment = SimulatedEnvironment(replace(scenario, assets=healthy_assets))

    run = run_station_connectivity_baseline(environment)

    assert run.final_state.status is TaskStatus.FAILED
    assert run.evidence == ()


def test_baseline_requires_another_station_for_comparison() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    reduced_assets = tuple(
        asset
        for asset in scenario.assets
        if asset.asset_id == scenario.incident.asset_id
        or asset.role is AssetRole.TELEMETRY_GATEWAY
    )
    environment = SimulatedEnvironment(replace(scenario, assets=reduced_assets))

    with pytest.raises(BaselineConfigurationError, match="peer station"):
        run_station_connectivity_baseline(environment)


def test_investigation_run_rejects_evidence_from_unknown_observation() -> None:
    run = run_baseline()
    invalid_evidence = replace(run.evidence[0], observation_ids=("OBS-UNKNOWN",))

    with pytest.raises(ValueError, match="only reference observations in the run"):
        InvestigationRun(
            incident=run.incident,
            task_states=run.task_states,
            executions=run.executions,
            evidence=(invalid_evidence,),
        )
