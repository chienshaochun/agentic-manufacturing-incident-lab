from dataclasses import replace
from datetime import timedelta
from typing import Mapping

import pytest

from agentic_manufacturing_incident_lab import Action, ActionRisk
from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.models import ScalarValue
from agentic_manufacturing_incident_lab.runtime import (
    ActionExecutionRecord,
    ActionExecutor,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


def make_runtime():
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    executor = ActionExecutor(build_diagnostic_registry(environment))
    return environment, executor


def make_action(
    environment: SimulatedEnvironment,
    *,
    action_id: str = "ACT-001",
    tool_name: str = "check_connectivity",
    incident_id: str | None = None,
    risk: ActionRisk = ActionRisk.READ_ONLY,
    parameters: Mapping[str, ScalarValue] | None = None,
    requested_offset_seconds: int = 10,
) -> Action:
    incident = environment.brief.incident
    return Action(
        action_id=action_id,
        incident_id=incident.incident_id if incident_id is None else incident_id,
        tool_name=tool_name,
        rationale="Collect a diagnostic measurement.",
        risk=risk,
        requested_at=incident.reported_at + timedelta(seconds=requested_offset_seconds),
        parameters={"asset_id": "ST-02"} if parameters is None else parameters,
    )


def test_successful_tool_response_becomes_auditable_action_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(make_action(environment))

    assert record.result.result_id == "RES-ACT-001"
    assert record.result.status is ActionResultStatus.SUCCEEDED
    assert record.result.error_code is None
    assert record.result.observation_ids == (record.observations[0].observation_id,)
    assert record.result.completed_at == record.observations[0].observed_at


def test_completion_time_never_precedes_action_request() -> None:
    environment, executor = make_runtime()
    action = make_action(environment, requested_offset_seconds=600)

    record = executor.execute(action)

    assert record.result.completed_at == action.requested_at + timedelta(seconds=1)


def test_unknown_tool_becomes_denied_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(make_action(environment, tool_name="run_shell"))

    assert record.result.status is ActionResultStatus.DENIED
    assert record.result.error_code == "tool_not_allowed"
    assert record.observations == ()
    assert environment.observation_count == 0


def test_invalid_parameters_become_denied_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(make_action(environment, parameters={"asset_id": 2}))

    assert record.result.status is ActionResultStatus.DENIED
    assert record.result.error_code == "invalid_parameters"
    assert environment.observation_count == 0


def test_risk_mismatch_becomes_denied_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(make_action(environment, risk=ActionRisk.HIGH_IMPACT))

    assert record.result.status is ActionResultStatus.DENIED
    assert record.result.error_code == "risk_mismatch"
    assert environment.observation_count == 0


def test_incident_scope_mismatch_becomes_denied_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(make_action(environment, incident_id="INC-OTHER"))

    assert record.result.status is ActionResultStatus.DENIED
    assert record.result.error_code == "incident_scope_mismatch"
    assert environment.observation_count == 0


def test_unknown_asset_becomes_failed_result() -> None:
    environment, executor = make_runtime()

    record = executor.execute(
        make_action(environment, parameters={"asset_id": "ST-99"})
    )

    assert record.result.status is ActionResultStatus.FAILED
    assert record.result.error_code == "unknown_asset"
    assert environment.observation_count == 0


def test_same_action_and_environment_replay_identical_record() -> None:
    first_environment, first_executor = make_runtime()
    second_environment, second_executor = make_runtime()

    first = first_executor.execute(make_action(first_environment))
    second = second_executor.execute(make_action(second_environment))

    assert first == second


def test_execution_record_rejects_mismatched_result_action() -> None:
    environment, executor = make_runtime()
    record = executor.execute(make_action(environment))
    mismatched_result = replace(record.result, action_id="ACT-OTHER")

    with pytest.raises(ValueError, match="result action_id must match"):
        ActionExecutionRecord(
            action=record.action,
            result=mismatched_result,
            observations=record.observations,
        )


def test_execution_record_rejects_mismatched_observation_ids() -> None:
    environment, executor = make_runtime()
    record = executor.execute(make_action(environment))
    mismatched_result = replace(record.result, observation_ids=())

    with pytest.raises(ValueError, match="observation_ids must match"):
        ActionExecutionRecord(
            action=record.action,
            result=mismatched_result,
            observations=record.observations,
        )
