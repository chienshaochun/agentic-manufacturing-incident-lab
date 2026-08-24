from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    CompleteDecision,
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    ConnectivityTool,
    ToolRegistry,
    build_diagnostic_registry,
)


def make_environment(*, healthy_affected_station: bool = False):
    scenario = build_station_connectivity_scenario(seed=43)
    if healthy_affected_station:
        assets = tuple(
            replace(
                asset,
                network_reachable=True,
                telemetry_available=True,
                alarm_codes=(),
            )
            if asset.asset_id == scenario.incident.asset_id
            else asset
            for asset in scenario.assets
        )
        scenario = replace(scenario, assets=assets)
    return SimulatedEnvironment(scenario)


def run_rule_based_agent(*, healthy_affected_station: bool = False):
    environment = make_environment(
        healthy_affected_station=healthy_affected_station
    )
    brief = environment.brief
    runner = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    )
    return runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )


def test_agent_completes_supported_investigation_through_three_decisions() -> None:
    run = run_rule_based_agent()

    assert run.final_state.status is TaskStatus.COMPLETED
    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "check_connectivity",
        "read_telemetry",
    ]
    assert [record.action.parameters["asset_id"] for record in run.executions] == [
        "ST-02",
        "ST-01",
        "ST-02",
    ]


def test_agent_turns_completion_decision_into_traceable_evidence() -> None:
    run = run_rule_based_agent()

    assert len(run.evidence) == 1
    assert run.evidence[0].claim == (
        "The observed connectivity failure is isolated to ST-02."
    )
    assert run.evidence[0].observation_ids == tuple(
        observation.observation_id for observation in run.observations
    )


def test_agent_preserves_task_lifecycle_and_audit_timestamps() -> None:
    run = run_rule_based_agent()

    assert [state.status for state in run.task_states] == [
        TaskStatus.CREATED,
        TaskStatus.INVESTIGATING,
        TaskStatus.COMPLETED,
    ]
    assert [state.revision for state in run.task_states] == [0, 1, 2]
    assert all(
        later.updated_at > earlier.updated_at
        for earlier, later in zip(run.task_states, run.task_states[1:])
    )


def test_agent_adapts_path_and_stops_when_pattern_is_unsupported() -> None:
    run = run_rule_based_agent(healthy_affected_station=True)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(run.executions) == 2
    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "read_telemetry",
    ]
    assert run.evidence == ()


def test_agent_stops_when_planner_needs_an_unavailable_tool() -> None:
    environment = make_environment()
    brief = environment.brief
    registry = ToolRegistry((ConnectivityTool(environment),))

    run = SingleAgentRunner(policy=RuleBasedPlanner(), registry=registry).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(run.executions) == 2
    assert "unavailable" in run.final_state.reason


def test_agent_rejects_planner_tool_outside_runtime_allowlist() -> None:
    class UnknownToolPolicy:
        name = "unknown_tool_test"

        def decide(self, context):
            return ActionDecision(
                tool_name="run_shell",
                rationale="Attempt an unregistered operation.",
            )

    environment = make_environment()
    brief = environment.brief
    run = SingleAgentRunner(
        policy=UnknownToolPolicy(),
        registry=build_diagnostic_registry(environment),
    ).run(incident=brief.incident, known_asset_ids=brief.known_asset_ids)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert run.executions == ()
    assert "outside the runtime allowlist" in run.final_state.reason


def test_agent_rejects_completion_with_unknown_observation_reference() -> None:
    class UnsupportedCompletionPolicy:
        name = "unsupported_completion_test"

        def decide(self, context):
            return CompleteDecision(
                rationale="Claim completion without collecting evidence.",
                claim="An unsupported diagnosis.",
                observation_ids=("OBS-NOT-COLLECTED",),
                confidence=1.0,
            )

    environment = make_environment()
    brief = environment.brief
    run = SingleAgentRunner(
        policy=UnsupportedCompletionPolicy(),
        registry=build_diagnostic_registry(environment),
    ).run(incident=brief.incident, known_asset_ids=brief.known_asset_ids)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert run.evidence == ()
    assert "were not collected" in run.final_state.reason


def test_hard_safety_limit_stops_a_nonterminating_policy() -> None:
    class RepeatingPolicy:
        name = "repeating_test"

        def decide(self, context):
            return ActionDecision(
                tool_name="check_connectivity",
                rationale="Repeat a safe but nonterminating measurement.",
                parameters={"asset_id": context.incident.asset_id},
            )

    environment = make_environment()
    brief = environment.brief
    run = SingleAgentRunner(
        policy=RepeatingPolicy(),
        registry=build_diagnostic_registry(environment),
        safety_action_limit=2,
    ).run(incident=brief.incident, known_asset_ids=brief.known_asset_ids)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(run.executions) == 2
    assert "Hard safety action limit" in run.final_state.reason


def test_same_scenario_and_policy_replay_identical_agent_run() -> None:
    assert run_rule_based_agent() == run_rule_based_agent()


@pytest.mark.parametrize("invalid_limit", [0, -1, True, 1.5])
def test_agent_requires_positive_integer_safety_limit(invalid_limit: object) -> None:
    environment = make_environment()

    with pytest.raises(ValueError, match="positive integer"):
        SingleAgentRunner(
            policy=RuleBasedPlanner(),
            registry=build_diagnostic_registry(environment),
            safety_action_limit=invalid_limit,  # type: ignore[arg-type]
        )
