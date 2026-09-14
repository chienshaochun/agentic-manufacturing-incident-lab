from dataclasses import replace

from agentic_manufacturing_incident_lab.agent import HypothesisDrivenPlanner
from agentic_manufacturing_incident_lab.domain import HypothesisStatus
from agentic_manufacturing_incident_lab.hypotheses import ConnectivityHypothesisPolicy
from agentic_manufacturing_incident_lab.runtime import InvestigationRun
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_shared_connectivity_scenario,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry
from agentic_manufacturing_incident_lab.agent import SingleAgentRunner


def _run(scenario) -> InvestigationRun:
    environment = SimulatedEnvironment(scenario)
    return SingleAgentRunner(
        policy=HypothesisDrivenPlanner(),
        registry=build_diagnostic_registry(environment),
        hypothesis_policy=ConnectivityHypothesisPolicy(),
    ).run(
        incident=environment.brief.incident,
        known_asset_ids=environment.brief.known_asset_ids,
    )


def test_dynamic_planner_preserves_high_value_isolation_sequence() -> None:
    run = _run(build_station_connectivity_scenario(seed=43))

    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "check_connectivity",
        "read_telemetry",
    ]
    assert "Utility=" in run.executions[0].action.rationale
    assert next(
        item for item in run.hypotheses if item.hypothesis_id.endswith("-STATION")
    ).status is HypothesisStatus.SUPPORTED


def test_dynamic_planner_changes_conclusion_for_shared_failure() -> None:
    run = _run(build_shared_connectivity_scenario())

    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "check_connectivity",
    ]
    assert next(
        item for item in run.hypotheses if item.hypothesis_id.endswith("-SHARED")
    ).status is HypothesisStatus.SUPPORTED
    assert run.evidence == ()


def test_dynamic_planner_uses_telemetry_after_healthy_connectivity() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    scenario = replace(
        scenario,
        assets=tuple(
            replace(asset, network_reachable=True, telemetry_available=False)
            if asset.asset_id == scenario.incident.asset_id
            else asset
            for asset in scenario.assets
        ),
    )
    run = _run(scenario)

    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "read_telemetry",
    ]
