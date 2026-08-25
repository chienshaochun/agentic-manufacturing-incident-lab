from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.recovery import RecoveryDisposition
from agentic_manufacturing_incident_lab.runtime import (
    RetryPolicy,
    deserialize_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.safety import SafetyDisposition
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


def make_runner(
    *,
    connectivity_faults: tuple[InjectedFault, ...],
    telemetry_faults: tuple[InjectedFault, ...] = (),
):
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        connectivity_faults,
    )
    telemetry = FaultInjectingTool(
        TelemetryTool(environment),
        telemetry_faults,
    )
    runner = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=ToolRegistry((connectivity, telemetry)),
        retry_policy=RetryPolicy(max_attempts=2),
    )
    return environment, connectivity, telemetry, runner


def start(runner, environment, *, pause_after_actions=None):
    brief = environment.brief
    return runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
        pause_after_actions=pause_after_actions,
    )


def test_retry_exhaustion_uses_one_alternative_then_stops_without_evidence() -> None:
    environment, connectivity, telemetry, runner = make_runner(
        connectivity_faults=(InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
    )

    run = start(runner, environment)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert [record.action.tool_name for record in run.executions] == [
        "check_connectivity",
        "read_telemetry",
    ]
    assert connectivity.attempt_count == 2
    assert telemetry.attempt_count == 1
    assert len(run.recovery_assessments) == 1
    assert (
        run.recovery_assessments[0].disposition
        is RecoveryDisposition.TRY_ALTERNATIVE
    )
    assert len(run.safety_assessments) == 2
    assert all(
        assessment.disposition is SafetyDisposition.ALLOW
        for assessment in run.safety_assessments
    )
    assert run.evidence == ()


def test_failed_alternative_safe_stops_without_cycling_back() -> None:
    environment, connectivity, telemetry, runner = make_runner(
        connectivity_faults=(InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
        telemetry_faults=(InjectedFault.TRANSIENT, InjectedFault.TRANSIENT),
    )

    run = start(runner, environment)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(run.executions) == 2
    assert connectivity.attempt_count == 2
    assert telemetry.attempt_count == 2
    assert [item.disposition for item in run.recovery_assessments] == [
        RecoveryDisposition.TRY_ALTERNATIVE,
        RecoveryDisposition.SAFE_STOP,
    ]
    assert "No untried allowlisted alternative" in run.final_state.reason
    assert run.evidence == ()


def test_permanent_failure_safe_stops_without_trying_alternative() -> None:
    environment, connectivity, telemetry, runner = make_runner(
        connectivity_faults=(InjectedFault.PERMANENT,),
    )

    run = start(runner, environment)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(run.executions) == 1
    assert connectivity.attempt_count == 1
    assert telemetry.attempt_count == 0
    assert run.recovery_assessments[0].disposition is RecoveryDisposition.SAFE_STOP


def test_paused_failure_can_resume_into_recovery_path() -> None:
    environment, _, _, runner = make_runner(
        connectivity_faults=(InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
    )
    partial = start(runner, environment, pause_after_actions=1)

    assert partial.final_state.status is TaskStatus.INVESTIGATING
    assert partial.recovery_assessments == ()
    restored = deserialize_checkpoint(serialize_checkpoint(partial))

    resumed = runner.resume(
        restored,
        known_asset_ids=environment.brief.known_asset_ids,
    )

    assert resumed.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(resumed.executions) == 2
    assert (
        resumed.recovery_assessments[0].disposition
        is RecoveryDisposition.TRY_ALTERNATIVE
    )


def test_completed_recovery_audit_round_trips_through_checkpoint() -> None:
    environment, _, _, runner = make_runner(
        connectivity_faults=(InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
        telemetry_faults=(InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
    )
    run = start(runner, environment)

    restored = deserialize_checkpoint(serialize_checkpoint(run))

    assert restored == run
    assert restored.recovery_assessments == run.recovery_assessments
