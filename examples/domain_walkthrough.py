"""Manually walk through the Phase 1 domain records without an agent or simulator."""

from datetime import UTC, datetime, timedelta

from agentic_manufacturing_incident_lab import (
    Action,
    ActionResult,
    ActionResultStatus,
    ActionRisk,
    Evidence,
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
    TaskState,
    TaskStatus,
    transition_task,
)


def main() -> None:
    """Create one complete, deterministic investigation record and print its summary."""
    reported_at = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    incident = Incident(
        incident_id="INC-001",
        title="Station connectivity failure",
        description="ST-02 cannot reach the simulated telemetry gateway.",
        asset_id="ST-02",
        severity=IncidentSeverity.WARNING,
        reported_at=reported_at,
        goal="Determine whether the failure is isolated to one station.",
    )

    created = TaskState(
        task_id="TASK-001",
        incident_id=incident.incident_id,
        status=TaskStatus.CREATED,
        revision=0,
        updated_at=reported_at,
        reason="Incident accepted for investigation.",
    )
    investigating = transition_task(
        created,
        TaskStatus.INVESTIGATING,
        reason="Initial triage started.",
        updated_at=reported_at + timedelta(minutes=1),
    )

    action = Action(
        action_id="ACT-001",
        incident_id=incident.incident_id,
        tool_name="connectivity_probe",
        rationale="Compare the affected station with a healthy peer.",
        risk=ActionRisk.READ_ONLY,
        requested_at=reported_at + timedelta(minutes=2),
        parameters={"target": "ST-02", "reference": "ST-01"},
    )
    observation = Observation(
        observation_id="OBS-001",
        incident_id=incident.incident_id,
        source=action.tool_name,
        kind=ObservationKind.CONNECTIVITY,
        summary="ST-02 was unreachable while ST-01 remained reachable.",
        observed_at=reported_at + timedelta(minutes=3),
        values={"target_reachable": False, "reference_reachable": True},
    )
    result = ActionResult(
        result_id="RES-001",
        action_id=action.action_id,
        incident_id=incident.incident_id,
        status=ActionResultStatus.SUCCEEDED,
        summary="The simulated connectivity comparison completed.",
        completed_at=reported_at + timedelta(minutes=3),
        observation_ids=(observation.observation_id,),
    )
    evidence = Evidence(
        evidence_id="EVD-001",
        incident_id=incident.incident_id,
        claim="The connectivity failure is isolated to ST-02.",
        observation_ids=(observation.observation_id,),
        confidence=0.85,
        created_at=reported_at + timedelta(minutes=4),
    )
    completed = transition_task(
        investigating,
        TaskStatus.COMPLETED,
        reason="The investigation goal is supported by recorded evidence.",
        updated_at=reported_at + timedelta(minutes=5),
    )

    print("Phase 1 domain walkthrough")
    print(f"Incident: {incident.incident_id} | asset={incident.asset_id}")
    print(f"Task: {created.status} -> {investigating.status} -> {completed.status}")
    print(f"Action: {action.tool_name} | risk={action.risk}")
    print(f"Result: {result.status} | observations={','.join(result.observation_ids)}")
    print(f"Evidence: {evidence.claim} | confidence={evidence.confidence:.2f}")


if __name__ == "__main__":
    main()
