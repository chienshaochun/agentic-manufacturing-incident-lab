from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningDecision,
    PlanningPolicy,
    StopDecision,
    StopReason,
)
from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
)
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.runtime import ActionExecutionRecord
from agentic_manufacturing_incident_lab.tools import (
    ToolParameter,
    ToolParameterType,
    ToolSpec,
)

REPORTED_AT = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def make_incident() -> Incident:
    return Incident(
        incident_id="INC-001",
        title="Station telemetry connectivity failure",
        description="ST-02 stopped reporting telemetry.",
        asset_id="ST-02",
        severity=IncidentSeverity.WARNING,
        reported_at=REPORTED_AT,
        goal="Determine whether the failure is isolated to one station.",
    )


def make_task(incident: Incident, status: TaskStatus = TaskStatus.INVESTIGATING) -> TaskState:
    return TaskState(
        task_id="TASK-001",
        incident_id=incident.incident_id,
        status=status,
        revision=1,
        updated_at=REPORTED_AT + timedelta(seconds=1),
        reason="Investigation started.",
    )


def make_tool_spec(name: str = "check_connectivity") -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Check a synthetic asset.",
        risk=ActionRisk.READ_ONLY,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset identifier.",
                value_type=ToolParameterType.STRING,
            ),
        ),
    )


def make_execution(incident: Incident) -> ActionExecutionRecord:
    action = Action(
        action_id="ACT-001",
        incident_id=incident.incident_id,
        tool_name="check_connectivity",
        rationale="Check the reported station.",
        risk=ActionRisk.READ_ONLY,
        requested_at=REPORTED_AT + timedelta(seconds=10),
        parameters={"asset_id": "ST-02"},
    )
    observation = Observation(
        observation_id="OBS-001",
        incident_id=incident.incident_id,
        source="simulated_connectivity_sensor",
        kind=ObservationKind.CONNECTIVITY,
        summary="ST-02 is unreachable.",
        observed_at=REPORTED_AT + timedelta(seconds=30),
        values={"asset_id": "ST-02", "network_reachable": False},
    )
    result = ActionResult(
        result_id="RES-ACT-001",
        action_id=action.action_id,
        incident_id=incident.incident_id,
        status=ActionResultStatus.SUCCEEDED,
        summary="Connectivity measurement completed.",
        completed_at=observation.observed_at,
        observation_ids=(observation.observation_id,),
    )
    return ActionExecutionRecord(
        action=action,
        result=result,
        observations=(observation,),
    )


def make_context(*, executions=()) -> AgentContext:
    incident = make_incident()
    return AgentContext(
        incident=incident,
        known_asset_ids=["ST-01", "ST-02", "GW-01"],  # type: ignore[arg-type]
        task_state=make_task(incident),
        available_tools=[make_tool_spec()],  # type: ignore[arg-type]
        executions=executions,
    )


def test_context_exposes_only_public_tools_and_execution_observations() -> None:
    incident = make_incident()
    execution = make_execution(incident)
    context = AgentContext(
        incident=incident,
        known_asset_ids=("ST-01", "ST-02", "GW-01"),
        task_state=make_task(incident),
        available_tools=(make_tool_spec(),),
        executions=[execution],  # type: ignore[arg-type]
    )

    assert context.step_number == 1
    assert context.observations == execution.observations
    assert context.available_tools[0].name == "check_connectivity"
    assert not hasattr(context.available_tools[0], "invoke")


def test_context_requires_investigating_task() -> None:
    incident = make_incident()

    with pytest.raises(ValueError, match="requires an investigating task"):
        AgentContext(
            incident=incident,
            known_asset_ids=("ST-01", "ST-02"),
            task_state=make_task(incident, TaskStatus.COMPLETED),
            available_tools=(make_tool_spec(),),
        )


def test_context_rejects_duplicate_available_tools() -> None:
    incident = make_incident()
    spec = make_tool_spec()

    with pytest.raises(ValueError, match="available tools must have unique names"):
        AgentContext(
            incident=incident,
            known_asset_ids=("ST-01", "ST-02"),
            task_state=make_task(incident),
            available_tools=(spec, spec),
        )


def test_context_rejects_execution_from_another_incident() -> None:
    incident = make_incident()
    other_incident = replace(incident, incident_id="INC-OTHER")
    execution = make_execution(other_incident)

    with pytest.raises(ValueError, match="executions must match"):
        AgentContext(
            incident=incident,
            known_asset_ids=("ST-01", "ST-02"),
            task_state=make_task(incident),
            available_tools=(make_tool_spec(),),
            executions=(execution,),
        )


def test_action_decision_copies_parameters_and_cannot_set_risk() -> None:
    parameters = {"asset_id": "ST-02"}
    decision = ActionDecision(
        tool_name="check_connectivity",
        rationale="Check the reported station.",
        parameters=parameters,
    )

    parameters["asset_id"] = "ST-01"

    assert decision.parameters["asset_id"] == "ST-02"
    assert not hasattr(decision, "risk")
    with pytest.raises(TypeError):
        decision.parameters["asset_id"] = "ST-01"  # type: ignore[index]


def test_complete_decision_records_supported_claim() -> None:
    decision = CompleteDecision(
        rationale="Affected station failed while the peer remained reachable.",
        claim="The failure is isolated to ST-02.",
        observation_ids=["OBS-001", "OBS-002"],  # type: ignore[arg-type]
        confidence=0.95,
    )

    assert decision.observation_ids == ("OBS-001", "OBS-002")


def test_complete_decision_requires_observation_reference() -> None:
    with pytest.raises(ValueError, match="at least one observation"):
        CompleteDecision(
            rationale="No evidence was collected.",
            claim="Unsupported claim.",
            observation_ids=(),
            confidence=0.5,
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True])
def test_complete_decision_rejects_invalid_confidence(confidence: object) -> None:
    with pytest.raises(ValueError, match="confidence must be between"):
        CompleteDecision(
            rationale="Evidence was evaluated.",
            claim="The failure is isolated.",
            observation_ids=("OBS-001",),
            confidence=confidence,  # type: ignore[arg-type]
        )


def test_stop_decision_requires_controlled_reason() -> None:
    decision = StopDecision(
        reason=StopReason.INSUFFICIENT_EVIDENCE,
        rationale="Available observations do not support a safe conclusion.",
    )

    assert decision.reason is StopReason.INSUFFICIENT_EVIDENCE


def test_structural_policy_satisfies_planning_protocol() -> None:
    class FirstToolPolicy:
        name = "first_tool"

        def decide(self, context: AgentContext) -> PlanningDecision:
            return ActionDecision(
                tool_name=context.available_tools[0].name,
                rationale="Use the first available tool.",
                parameters={"asset_id": context.incident.asset_id},
            )

    policy = FirstToolPolicy()

    assert isinstance(policy, PlanningPolicy)
    assert isinstance(policy.decide(make_context()), ActionDecision)
