from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab import Action
from agentic_manufacturing_incident_lab.agent import (
    StepBudgetExceeded,
    complete_working_memory,
    initialize_working_memory,
    prepare_action_memory,
    record_action_memory,
)
from agentic_manufacturing_incident_lab.domain.models import ActionRisk
from agentic_manufacturing_incident_lab.runtime import ActionExecutor
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


def make_runtime(*, action_limit: int = 3):
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    registry = build_diagnostic_registry(environment)
    incident = environment.brief.incident
    memory = initialize_working_memory(
        task_id=f"TASK-{incident.incident_id}",
        incident=incident,
        action_limit=action_limit,
        updated_at=incident.reported_at + timedelta(seconds=1),
    )
    return environment, registry, ActionExecutor(registry), memory


def make_action(environment: SimulatedEnvironment, *, risk=ActionRisk.READ_ONLY):
    incident = environment.brief.incident
    return Action(
        action_id=f"{incident.incident_id}-ACT-001",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Determine whether the affected station is reachable.",
        risk=risk,
        requested_at=incident.reported_at + timedelta(seconds=2),
        parameters={"asset_id": incident.asset_id},
    )


def test_initial_memory_contains_goal_question_and_unused_budget() -> None:
    environment, _, _, memory = make_runtime()

    assert memory.revision == 0
    assert memory.open_questions[0].question_id == "Q-GOAL"
    assert memory.open_questions[0].prompt == environment.brief.incident.goal
    assert memory.facts == ()
    assert memory.step_budget.actions_remaining == 3


def test_preparing_action_opens_question_and_consumes_budget() -> None:
    environment, _, _, memory = make_runtime()
    action = make_action(environment)

    prepared = prepare_action_memory(memory, action)

    assert prepared.revision == 1
    assert prepared.step_budget.actions_used == 1
    assert prepared.open_questions[-1].question_id == f"Q-{action.action_id}"
    assert prepared.open_questions[-1].prompt == action.rationale
    assert memory.step_budget.actions_used == 0


def test_successful_execution_adds_fact_and_closes_action_question() -> None:
    environment, _, executor, memory = make_runtime()
    action = make_action(environment)
    prepared = prepare_action_memory(memory, action)

    record = executor.execute(action)
    recorded = record_action_memory(prepared, record)

    assert recorded.revision == 2
    assert len(recorded.facts) == 1
    assert recorded.facts[0].statement == record.observations[0].summary
    assert recorded.facts[0].observation_ids == (
        record.observations[0].observation_id,
    )
    assert [question.question_id for question in recorded.open_questions] == [
        "Q-GOAL"
    ]


def test_failed_execution_keeps_action_question_open() -> None:
    environment, _, executor, memory = make_runtime()
    action = make_action(environment, risk=ActionRisk.HIGH_IMPACT)
    prepared = prepare_action_memory(memory, action)

    recorded = record_action_memory(prepared, executor.execute(action))

    assert recorded.facts == ()
    assert [question.question_id for question in recorded.open_questions] == [
        "Q-GOAL",
        f"Q-{action.action_id}",
    ]


def test_completion_closes_all_remaining_questions() -> None:
    environment, _, executor, memory = make_runtime()
    action = make_action(environment)
    prepared = prepare_action_memory(memory, action)
    recorded = record_action_memory(prepared, executor.execute(action))

    completed = complete_working_memory(
        recorded,
        updated_at=recorded.updated_at + timedelta(seconds=1),
    )

    assert completed.revision == 3
    assert completed.open_questions == ()
    assert completed.facts == recorded.facts


def test_exhausted_budget_blocks_action_preparation() -> None:
    environment, _, executor, memory = make_runtime(action_limit=1)
    first_action = make_action(environment)
    prepared = prepare_action_memory(memory, first_action)
    recorded = record_action_memory(prepared, executor.execute(first_action))
    second_action = Action(
        action_id=f"{environment.brief.incident.incident_id}-ACT-002",
        incident_id=environment.brief.incident.incident_id,
        tool_name="read_telemetry",
        rationale="Attempt another measurement.",
        risk=ActionRisk.READ_ONLY,
        requested_at=recorded.updated_at + timedelta(seconds=1),
        parameters={"asset_id": environment.brief.incident.asset_id},
    )

    with pytest.raises(StepBudgetExceeded, match="exhausted"):
        prepare_action_memory(recorded, second_action)


def test_memory_transition_rejects_cross_incident_action() -> None:
    environment, _, _, memory = make_runtime()
    action = make_action(environment)
    other_action = Action(
        action_id=action.action_id,
        incident_id="INC-OTHER",
        tool_name=action.tool_name,
        rationale=action.rationale,
        risk=action.risk,
        requested_at=action.requested_at,
        parameters=action.parameters,
    )

    with pytest.raises(ValueError, match="match the memory incident"):
        prepare_action_memory(memory, other_action)
