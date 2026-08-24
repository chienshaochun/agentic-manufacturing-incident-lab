from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.runtime import (
    deserialize_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry
from agentic_manufacturing_incident_lab.workflows import (
    ResumeEnvironmentMismatch,
    replay_environment_to_run,
)


def make_runner(environment: SimulatedEnvironment, *, action_limit: int = 32):
    return SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
        action_limit=action_limit,
    )


def make_partial_run(*, pause_after_actions: int = 1, action_limit: int = 32):
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    brief = environment.brief
    run = make_runner(environment, action_limit=action_limit).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
        pause_after_actions=pause_after_actions,
    )
    return scenario, run


def test_agent_pauses_with_investigating_state_and_partial_memory() -> None:
    _, partial = make_partial_run()

    assert partial.final_state.status is TaskStatus.INVESTIGATING
    assert len(partial.executions) == 1
    assert partial.evidence == ()
    assert partial.final_memory is not None
    assert partial.final_memory.step_budget.actions_used == 1
    assert len(partial.final_memory.facts) == 1
    assert partial.final_memory.open_questions[0].question_id == "Q-GOAL"


def test_checkpoint_resume_matches_uninterrupted_run_exactly() -> None:
    scenario, partial = make_partial_run()
    restored = deserialize_checkpoint(serialize_checkpoint(partial))
    resumed_environment = replay_environment_to_run(scenario, restored)
    resumed = make_runner(resumed_environment).resume(
        restored,
        known_asset_ids=resumed_environment.brief.known_asset_ids,
    )

    uninterrupted_environment = SimulatedEnvironment(scenario)
    uninterrupted = make_runner(uninterrupted_environment).run(
        incident=uninterrupted_environment.brief.incident,
        known_asset_ids=uninterrupted_environment.brief.known_asset_ids,
    )

    assert resumed == uninterrupted
    assert resumed.final_state.status is TaskStatus.COMPLETED
    assert len(resumed.executions) == 3


def test_environment_replay_advances_observation_sequence() -> None:
    scenario, partial = make_partial_run()

    environment = replay_environment_to_run(scenario, partial)

    assert environment.observation_count == 1
    assert environment.current_time == partial.observations[-1].observed_at


def test_pause_before_first_action_can_be_resumed() -> None:
    scenario, partial = make_partial_run(pause_after_actions=0)

    assert partial.executions == ()
    assert partial.final_memory is not None
    assert partial.final_memory.revision == 0

    environment = replay_environment_to_run(scenario, partial)
    resumed = make_runner(environment).resume(
        partial,
        known_asset_ids=environment.brief.known_asset_ids,
    )

    assert resumed.final_state.status is TaskStatus.COMPLETED


def test_resume_can_pause_again_at_later_total_action_count() -> None:
    scenario, first_pause = make_partial_run(pause_after_actions=1)
    environment = replay_environment_to_run(scenario, first_pause)

    second_pause = make_runner(environment).resume(
        first_pause,
        known_asset_ids=environment.brief.known_asset_ids,
        pause_after_actions=2,
    )

    assert second_pause.final_state.status is TaskStatus.INVESTIGATING
    assert len(second_pause.executions) == 2
    assert second_pause.final_memory is not None
    assert second_pause.final_memory.step_budget.actions_used == 2


def test_different_scenario_is_rejected_before_resume() -> None:
    _, partial = make_partial_run()
    different_scenario = build_station_connectivity_scenario(seed=42)

    with pytest.raises(ResumeEnvironmentMismatch, match="incident does not match"):
        replay_environment_to_run(different_scenario, partial)


def test_changed_scenario_truth_is_rejected_during_replay() -> None:
    scenario, partial = make_partial_run()
    changed_assets = tuple(
        replace(asset, network_reachable=True)
        if asset.asset_id == scenario.incident.asset_id
        else asset
        for asset in scenario.assets
    )
    changed_scenario = replace(scenario, assets=changed_assets)

    with pytest.raises(ResumeEnvironmentMismatch, match="does not match"):
        replay_environment_to_run(changed_scenario, partial)


def test_completed_run_cannot_be_resumed() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    completed = make_runner(environment).run(
        incident=environment.brief.incident,
        known_asset_ids=environment.brief.known_asset_ids,
    )
    replayed_environment = replay_environment_to_run(scenario, completed)

    with pytest.raises(ValueError, match="only an investigating run"):
        make_runner(replayed_environment).resume(
            completed,
            known_asset_ids=replayed_environment.brief.known_asset_ids,
        )


def test_resume_requires_same_action_limit() -> None:
    scenario, partial = make_partial_run(action_limit=4)
    environment = replay_environment_to_run(scenario, partial)

    with pytest.raises(ValueError, match="action_limit must match"):
        make_runner(environment, action_limit=5).resume(
            partial,
            known_asset_ids=environment.brief.known_asset_ids,
        )


def test_resume_requires_same_planning_policy() -> None:
    class RenamedPolicy(RuleBasedPlanner):
        name = "different_policy"

    scenario, partial = make_partial_run()
    environment = replay_environment_to_run(scenario, partial)
    runner = SingleAgentRunner(
        policy=RenamedPolicy(),
        registry=build_diagnostic_registry(environment),
    )

    with pytest.raises(ValueError, match="policy must match"):
        runner.resume(
            partial,
            known_asset_ids=environment.brief.known_asset_ids,
        )


@pytest.mark.parametrize("invalid_pause", [-1, True, 1.5])
def test_pause_after_actions_must_be_non_negative_integer(
    invalid_pause: object,
) -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)

    with pytest.raises(ValueError, match="non-negative integer"):
        make_runner(environment).run(
            incident=environment.brief.incident,
            known_asset_ids=environment.brief.known_asset_ids,
            pause_after_actions=invalid_pause,  # type: ignore[arg-type]
        )
