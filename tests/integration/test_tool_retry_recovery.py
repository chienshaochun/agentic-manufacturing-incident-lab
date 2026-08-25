from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.runtime import (
    ActionExecutor,
    RetryPolicy,
    deserialize_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    ConnectivityTool,
    FaultInjectingTool,
    InjectedFault,
    TelemetryTool,
    ToolRegistry,
)


def make_environment() -> SimulatedEnvironment:
    return SimulatedEnvironment(build_station_connectivity_scenario(seed=43))


def make_action(environment: SimulatedEnvironment) -> Action:
    incident = environment.brief.incident
    return Action(
        action_id=f"{incident.incident_id}-ACT-001",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Measure connectivity with bounded retries.",
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10),
        parameters={"asset_id": incident.asset_id},
    )


def make_fault_runtime(
    fault_script: tuple[InjectedFault, ...],
    *,
    max_attempts: int = 3,
):
    environment = make_environment()
    tool = FaultInjectingTool(ConnectivityTool(environment), fault_script)
    executor = ActionExecutor(
        ToolRegistry((tool,)),
        retry_policy=RetryPolicy(max_attempts=max_attempts),
    )
    return environment, tool, executor


def test_timeout_and_transient_failure_retry_before_success() -> None:
    environment, tool, executor = make_fault_runtime(
        (InjectedFault.TIMEOUT, InjectedFault.TRANSIENT)
    )

    record = executor.execute(make_action(environment))

    assert record.result.status is ActionResultStatus.SUCCEEDED
    assert [attempt.status for attempt in record.attempts] == [
        ActionResultStatus.TIMED_OUT,
        ActionResultStatus.FAILED,
        ActionResultStatus.SUCCEEDED,
    ]
    assert [attempt.error_code for attempt in record.attempts] == [
        "tool_timeout",
        "transient_tool_error",
        None,
    ]
    assert tool.attempt_count == 3
    assert environment.observation_count == 1


def test_timeout_stops_after_configured_attempt_limit() -> None:
    environment, tool, executor = make_fault_runtime(
        (InjectedFault.TIMEOUT, InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
        max_attempts=2,
    )

    record = executor.execute(make_action(environment))

    assert record.result.status is ActionResultStatus.TIMED_OUT
    assert record.result.error_code == "tool_timeout"
    assert len(record.attempts) == 2
    assert tool.attempt_count == 2
    assert environment.observation_count == 0


def test_permanent_failure_is_not_retried() -> None:
    environment, tool, executor = make_fault_runtime(
        (InjectedFault.PERMANENT, InjectedFault.TRANSIENT),
    )

    record = executor.execute(make_action(environment))

    assert record.result.status is ActionResultStatus.FAILED
    assert record.result.error_code == "permanent_tool_error"
    assert len(record.attempts) == 1
    assert tool.attempt_count == 1
    assert environment.observation_count == 0


def test_identical_fault_scripts_replay_identical_execution_records() -> None:
    first_environment, _, first_executor = make_fault_runtime(
        (InjectedFault.TIMEOUT, InjectedFault.TRANSIENT)
    )
    second_environment, _, second_executor = make_fault_runtime(
        (InjectedFault.TIMEOUT, InjectedFault.TRANSIENT)
    )

    first = first_executor.execute(make_action(first_environment))
    second = second_executor.execute(make_action(second_environment))

    assert first == second


def test_agent_budget_counts_one_action_while_executor_records_two_attempts() -> None:
    environment = make_environment()
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.TIMEOUT,),
    )
    registry = ToolRegistry((connectivity, TelemetryTool(environment)))
    brief = environment.brief

    run = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=registry,
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    assert run.final_memory is not None
    assert run.final_memory.step_budget.actions_used == 3
    assert len(run.executions) == 3
    assert len(run.executions[0].attempts) == 2
    assert len(run.executions[1].attempts) == 1
    assert connectivity.attempt_count == 3


def test_agent_accepts_a_custom_retry_limit() -> None:
    environment = make_environment()
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.TIMEOUT, InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
    )
    brief = environment.brief

    run = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=ToolRegistry((connectivity, TelemetryTool(environment))),
        action_limit=1,
        retry_policy=RetryPolicy(max_attempts=2),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    assert len(run.executions) == 1
    assert len(run.executions[0].attempts) == 2
    assert run.executions[0].result.status is ActionResultStatus.TIMED_OUT
    assert connectivity.attempt_count == 2


def test_checkpoint_preserves_attempt_level_audit_history() -> None:
    environment = make_environment()
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.TRANSIENT,),
    )
    brief = environment.brief
    run = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=ToolRegistry((connectivity, TelemetryTool(environment))),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    restored = deserialize_checkpoint(serialize_checkpoint(run))

    assert restored == run
    assert restored.executions[0].attempts == run.executions[0].attempts


@pytest.mark.parametrize("invalid_attempts", [0, -1, True, 1.5])
def test_retry_policy_requires_positive_integer(invalid_attempts: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        RetryPolicy(max_attempts=invalid_attempts)  # type: ignore[arg-type]
