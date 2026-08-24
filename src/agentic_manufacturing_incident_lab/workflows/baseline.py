"""Fixed diagnostic SOP used as the non-agent baseline."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk, Evidence
from agentic_manufacturing_incident_lab.domain.task import (
    TaskState,
    TaskStatus,
    transition_task,
)
from agentic_manufacturing_incident_lab.runtime import (
    ActionExecutionRecord,
    ActionExecutor,
    InvestigationRun,
)
from agentic_manufacturing_incident_lab.simulation import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


class BaselineConfigurationError(ValueError):
    """Raised when a scenario cannot satisfy this workflow's fixed assumptions."""


def _select_reference_station(environment: SimulatedEnvironment) -> str:
    affected_asset_id = environment.brief.incident.asset_id
    candidates = sorted(
        asset_id
        for asset_id in environment.brief.known_asset_ids
        if asset_id.startswith("ST-") and asset_id != affected_asset_id
    )
    if not candidates:
        raise BaselineConfigurationError("a healthy peer station candidate is required")
    return candidates[0]


def _make_action(
    environment: SimulatedEnvironment,
    *,
    sequence: int,
    tool_name: str,
    asset_id: str,
    rationale: str,
) -> Action:
    incident = environment.brief.incident
    return Action(
        action_id=f"{incident.incident_id}-ACT-{sequence:03d}",
        incident_id=incident.incident_id,
        tool_name=tool_name,
        rationale=rationale,
        risk=ActionRisk.READ_ONLY,
        requested_at=incident.reported_at + timedelta(seconds=10 + (sequence - 1) * 30),
        parameters={"asset_id": asset_id},
    )


def _supports_isolated_station_failure(
    executions: tuple[ActionExecutionRecord, ...],
) -> bool:
    if any(
        record.result.status is not ActionResultStatus.SUCCEEDED
        or len(record.observations) != 1
        for record in executions
    ):
        return False
    affected_connectivity, reference_connectivity, affected_telemetry = (
        record.observations[0] for record in executions
    )
    return (
        affected_connectivity.values.get("network_reachable") is False
        and reference_connectivity.values.get("network_reachable") is True
        and affected_telemetry.values.get("telemetry_available") is False
    )


def run_station_connectivity_baseline(
    environment: SimulatedEnvironment,
) -> InvestigationRun:
    """Run a fixed three-step SOP without any planner or agent decisions."""
    incident = environment.brief.incident
    created = TaskState(
        task_id=f"TASK-{incident.incident_id}",
        incident_id=incident.incident_id,
        status=TaskStatus.CREATED,
        revision=0,
        updated_at=incident.reported_at,
        reason="Baseline investigation task created.",
    )
    investigating = transition_task(
        created,
        TaskStatus.INVESTIGATING,
        reason="Fixed diagnostic SOP started.",
        updated_at=incident.reported_at + timedelta(seconds=1),
    )

    affected_asset_id = incident.asset_id
    reference_asset_id = _select_reference_station(environment)
    actions = (
        _make_action(
            environment,
            sequence=1,
            tool_name="check_connectivity",
            asset_id=affected_asset_id,
            rationale="Measure connectivity for the reported station.",
        ),
        _make_action(
            environment,
            sequence=2,
            tool_name="check_connectivity",
            asset_id=reference_asset_id,
            rationale="Compare connectivity with another known station.",
        ),
        _make_action(
            environment,
            sequence=3,
            tool_name="read_telemetry",
            asset_id=affected_asset_id,
            rationale="Confirm telemetry availability for the reported station.",
        ),
    )
    executor = ActionExecutor(build_diagnostic_registry(environment))
    executions = tuple(executor.execute(action) for action in actions)
    latest_completion = max(record.result.completed_at for record in executions)

    if _supports_isolated_station_failure(executions):
        evidence = (
            Evidence(
                evidence_id=f"EVD-{incident.incident_id}-001",
                incident_id=incident.incident_id,
                claim=f"The connectivity failure is isolated to {affected_asset_id}.",
                observation_ids=tuple(
                    observation.observation_id
                    for record in executions
                    for observation in record.observations
                ),
                confidence=0.95,
                created_at=latest_completion + timedelta(seconds=1),
            ),
        )
        final_state = transition_task(
            investigating,
            TaskStatus.COMPLETED,
            reason="The fixed SOP produced evidence for an isolated station failure.",
            updated_at=latest_completion + timedelta(seconds=2),
        )
    else:
        evidence = ()
        final_state = transition_task(
            investigating,
            TaskStatus.FAILED,
            reason="The fixed SOP did not produce its expected diagnostic pattern.",
            updated_at=latest_completion + timedelta(seconds=1),
        )

    return InvestigationRun(
        incident=incident,
        task_states=(created, investigating, final_state),
        executions=executions,
        evidence=evidence,
    )
