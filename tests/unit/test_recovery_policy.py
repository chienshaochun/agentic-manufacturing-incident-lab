from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.recovery import (
    RecoveryDisposition,
    RuleBasedRecoveryPolicy,
)
from agentic_manufacturing_incident_lab.runtime import ActionExecutor, RetryPolicy
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


def make_failed_execution(fault: InjectedFault):
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    incident = environment.brief.incident
    tool = FaultInjectingTool(ConnectivityTool(environment), (fault,))
    registry = ToolRegistry((tool, TelemetryTool(environment)))
    action = Action(
        action_id=f"{incident.incident_id}-ACT-001",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Measure affected-station connectivity.",
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10),
        parameters={"asset_id": incident.asset_id},
    )
    record = ActionExecutor(
        registry,
        retry_policy=RetryPolicy(max_attempts=1),
    ).execute(action)
    return record, registry


def assess(fault: InjectedFault):
    record, registry = make_failed_execution(fault)
    assessment = RuleBasedRecoveryPolicy().assess(
        record,
        available_tools=registry.specs,
        prior_executions=(record,),
        assessed_at=record.result.completed_at + timedelta(seconds=1),
    )
    return record, assessment


@pytest.mark.parametrize(
    "fault",
    [InjectedFault.TIMEOUT, InjectedFault.TRANSIENT],
)
def test_retryable_failure_selects_independent_diagnostic_channel(
    fault: InjectedFault,
) -> None:
    record, assessment = assess(fault)

    assert assessment.action_id == record.action.action_id
    assert assessment.disposition is RecoveryDisposition.TRY_ALTERNATIVE
    assert assessment.alternative_tool_name == "read_telemetry"
    assert assessment.alternative_parameters == record.action.parameters


def test_permanent_failure_selects_safe_stop() -> None:
    _, assessment = assess(InjectedFault.PERMANENT)

    assert assessment.disposition is RecoveryDisposition.SAFE_STOP
    assert assessment.alternative_tool_name is None
    assert assessment.alternative_parameters == {}


def test_recovery_rejects_successful_execution() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    incident = environment.brief.incident
    registry = ToolRegistry((ConnectivityTool(environment), TelemetryTool(environment)))
    action = Action(
        action_id=f"{incident.incident_id}-ACT-001",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Measure affected-station connectivity.",
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10),
        parameters={"asset_id": incident.asset_id},
    )
    record = ActionExecutor(registry).execute(action)
    assert record.result.status is ActionResultStatus.SUCCEEDED

    with pytest.raises(ValueError, match="unsuccessful execution"):
        RuleBasedRecoveryPolicy().assess(
            record,
            available_tools=registry.specs,
            prior_executions=(record,),
            assessed_at=record.result.completed_at + timedelta(seconds=1),
        )


def test_already_attempted_alternative_selects_safe_stop() -> None:
    record, registry = make_failed_execution(InjectedFault.TIMEOUT)
    telemetry_action = Action(
        action_id=f"{record.action.incident_id}-ACT-000",
        incident_id=record.action.incident_id,
        tool_name="read_telemetry",
        rationale="Earlier telemetry attempt.",
        risk=ActionRisk.READ_ONLY,
        requested_at=record.action.requested_at - timedelta(seconds=5),
        parameters=record.action.parameters,
    )
    telemetry_record = ActionExecutor(registry).execute(telemetry_action)

    assessment = RuleBasedRecoveryPolicy().assess(
        record,
        available_tools=registry.specs,
        prior_executions=(telemetry_record, record),
        assessed_at=record.result.completed_at + timedelta(seconds=1),
    )

    assert assessment.disposition is RecoveryDisposition.SAFE_STOP
