from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    CompleteDecision,
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.runtime import (
    deserialize_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.safety import (
    ApprovalOutcome,
    SafetyDisposition,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
    ToolResponse,
    ToolSpec,
    build_diagnostic_registry,
)


class SyntheticOperationTool:
    """Test tool whose call count proves whether authorization was enforced."""

    def __init__(
        self,
        environment: SimulatedEnvironment,
        *,
        name: str,
        risk: ActionRisk,
    ) -> None:
        self._environment = environment
        self.call_count = 0
        self.spec = ToolSpec(
            name=name,
            description="Perform one synthetic operation for authorization tests.",
            risk=risk,
            parameters=(
                ToolParameter(
                    name="asset_id",
                    description="Synthetic asset identifier.",
                    value_type=ToolParameterType.STRING,
                ),
            ),
        )

    def invoke(self, action: Action) -> ToolResponse:
        self.call_count += 1
        asset_id = action.parameters["asset_id"]
        assert isinstance(asset_id, str)
        observation = self._environment.measure_telemetry(asset_id)
        return ToolResponse(
            summary=f"Synthetic operation completed for {asset_id}.",
            observations=(observation,),
        )


class OneOperationPolicy:
    def __init__(self, tool_name: str) -> None:
        self.name = f"one_{tool_name}_policy"
        self._tool_name = tool_name

    def decide(self, context):
        if not context.executions:
            return ActionDecision(
                tool_name=self._tool_name,
                rationale="Perform the proposed synthetic operation.",
                parameters={"asset_id": context.incident.asset_id},
            )
        observation = context.observations[-1]
        return CompleteDecision(
            rationale="The approved synthetic operation produced an observation.",
            claim="The controlled synthetic operation completed.",
            observation_ids=(observation.observation_id,),
            confidence=1.0,
        )


def make_operation_runtime(risk: ActionRisk):
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    name = "apply_synthetic_setting"
    tool = SyntheticOperationTool(environment, name=name, risk=risk)
    runner = SingleAgentRunner(
        policy=OneOperationPolicy(name),
        registry=ToolRegistry((tool,)),
    )
    return environment, tool, runner


def start_operation(risk: ActionRisk):
    environment, tool, runner = make_operation_runtime(risk)
    brief = environment.brief
    run = runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    return environment, tool, runner, run


def test_controlled_write_waits_without_invoking_tool_or_consuming_budget() -> None:
    environment, tool, _, waiting = start_operation(ActionRisk.CONTROLLED_WRITE)

    assert waiting.final_state.status is TaskStatus.WAITING_APPROVAL
    assert waiting.executions == ()
    assert waiting.final_memory is not None
    assert waiting.final_memory.step_budget.actions_used == 0
    assert tool.call_count == 0
    assert environment.observation_count == 0
    assert len(waiting.safety_assessments) == 1
    assert (
        waiting.safety_assessments[0].disposition
        is SafetyDisposition.REQUIRE_APPROVAL
    )
    assert waiting.pending_approval is waiting.approval_requests[0]


def test_approved_controlled_write_executes_once_and_completes() -> None:
    environment, tool, runner, waiting = start_operation(
        ActionRisk.CONTROLLED_WRITE
    )

    completed = runner.resolve_approval(
        waiting,
        outcome=ApprovalOutcome.APPROVED,
        decided_by="operator-01",
        rationale="Synthetic maintenance window confirmed.",
        known_asset_ids=environment.brief.known_asset_ids,
    )

    assert completed.final_state.status is TaskStatus.COMPLETED
    assert [state.status for state in completed.task_states] == [
        TaskStatus.CREATED,
        TaskStatus.INVESTIGATING,
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.INVESTIGATING,
        TaskStatus.COMPLETED,
    ]
    assert len(completed.executions) == 1
    assert tool.call_count == 1
    assert environment.observation_count == 1
    assert completed.final_memory is not None
    assert completed.final_memory.step_budget.actions_used == 1
    assert completed.approval_decisions[0].outcome is ApprovalOutcome.APPROVED
    assert completed.pending_approval is None
    assert completed.executions[0].action.action_id == (
        completed.approval_requests[0].action.action_id
    )


def test_rejected_controlled_write_safe_stops_without_execution() -> None:
    environment, tool, runner, waiting = start_operation(
        ActionRisk.CONTROLLED_WRITE
    )

    stopped = runner.resolve_approval(
        waiting,
        outcome=ApprovalOutcome.REJECTED,
        decided_by="operator-01",
        rationale="No approved maintenance window.",
        known_asset_ids=environment.brief.known_asset_ids,
    )

    assert stopped.final_state.status is TaskStatus.SAFE_STOPPED
    assert stopped.executions == ()
    assert tool.call_count == 0
    assert environment.observation_count == 0
    assert stopped.final_memory is not None
    assert stopped.final_memory.step_budget.actions_used == 0
    assert stopped.approval_decisions[0].outcome is ApprovalOutcome.REJECTED
    assert stopped.pending_approval is None


def test_high_impact_action_is_denied_without_request_or_execution() -> None:
    environment, tool, _, stopped = start_operation(ActionRisk.HIGH_IMPACT)

    assert stopped.final_state.status is TaskStatus.SAFE_STOPPED
    assert stopped.executions == ()
    assert stopped.approval_requests == ()
    assert stopped.approval_decisions == ()
    assert tool.call_count == 0
    assert environment.observation_count == 0
    assert stopped.final_memory is not None
    assert stopped.final_memory.step_budget.actions_used == 0
    assert stopped.safety_assessments[0].disposition is SafetyDisposition.DENY


def test_waiting_approval_checkpoint_round_trips_with_pending_action() -> None:
    _, _, _, waiting = start_operation(ActionRisk.CONTROLLED_WRITE)

    restored = deserialize_checkpoint(serialize_checkpoint(waiting))

    assert restored == waiting
    assert restored.final_state.status is TaskStatus.WAITING_APPROVAL
    assert restored.pending_approval == waiting.pending_approval


def test_approved_run_checkpoint_round_trips_with_audit_records() -> None:
    environment, _, runner, waiting = start_operation(ActionRisk.CONTROLLED_WRITE)
    completed = runner.resolve_approval(
        waiting,
        outcome=ApprovalOutcome.APPROVED,
        decided_by="operator-01",
        rationale="Synthetic maintenance window confirmed.",
        known_asset_ids=environment.brief.known_asset_ids,
    )

    restored = deserialize_checkpoint(serialize_checkpoint(completed))

    assert restored == completed
    assert restored.approval_requests == completed.approval_requests
    assert restored.approval_decisions == completed.approval_decisions


def test_read_only_agent_records_allow_assessment_for_every_action() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief

    run = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    assert len(run.safety_assessments) == len(run.executions) == 3
    assert all(
        assessment.disposition is SafetyDisposition.ALLOW
        for assessment in run.safety_assessments
    )
    assert run.approval_requests == ()
    assert run.approval_decisions == ()
