from dataclasses import replace
from datetime import timedelta

from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningPolicy,
    RuleBasedPlanner,
    StepBudget,
    StopDecision,
    StopReason,
    WorkingMemory,
)
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.runtime import (
    ActionExecutionRecord,
    ActionExecutor,
)
from agentic_manufacturing_incident_lab.simulation import (
    ScenarioDefinition,
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import ToolRegistry, build_diagnostic_registry


def make_scenario(
    *,
    affected_reachable: bool = False,
    affected_telemetry: bool = False,
    peer_reachable: bool = True,
) -> ScenarioDefinition:
    scenario = build_station_connectivity_scenario(seed=43)
    assets = tuple(
        replace(
            asset,
            network_reachable=(
                affected_reachable
                if asset.asset_id == "ST-02"
                else peer_reachable if asset.asset_id == "ST-01" else asset.network_reachable
            ),
            telemetry_available=(
                affected_telemetry
                if asset.asset_id == "ST-02"
                else asset.telemetry_available
            ),
        )
        for asset in scenario.assets
    )
    return replace(scenario, assets=assets)


def make_runtime(
    scenario: ScenarioDefinition | None = None,
) -> tuple[SimulatedEnvironment, ToolRegistry, ActionExecutor]:
    environment = SimulatedEnvironment(scenario or make_scenario())
    registry = build_diagnostic_registry(environment)
    return environment, registry, ActionExecutor(registry)


def make_context(
    environment: SimulatedEnvironment,
    registry: ToolRegistry,
    *,
    executions: tuple[ActionExecutionRecord, ...] = (),
    known_asset_ids: tuple[str, ...] | None = None,
) -> AgentContext:
    brief = environment.brief
    incident = brief.incident
    updated_at = max(
        (record.result.completed_at for record in executions),
        default=incident.reported_at + timedelta(seconds=1),
    )
    return AgentContext(
        incident=incident,
        known_asset_ids=known_asset_ids or brief.known_asset_ids,
        task_state=TaskState(
            task_id="TASK-001",
            incident_id=incident.incident_id,
            status=TaskStatus.INVESTIGATING,
            revision=1,
            updated_at=incident.reported_at + timedelta(seconds=1),
            reason="Investigation started.",
        ),
        available_tools=registry.specs,
        working_memory=WorkingMemory(
            task_id="TASK-001",
            incident_id=incident.incident_id,
            revision=0,
            facts=(),
            open_questions=(),
            step_budget=StepBudget(
                action_limit=10,
                actions_used=len(executions),
            ),
            updated_at=updated_at,
        ),
        executions=executions,
    )


def execute_decision(
    environment: SimulatedEnvironment,
    registry: ToolRegistry,
    executor: ActionExecutor,
    decision: ActionDecision,
    *,
    sequence: int,
) -> ActionExecutionRecord:
    incident = environment.brief.incident
    action = Action(
        action_id=f"ACT-{sequence:03d}",
        incident_id=incident.incident_id,
        tool_name=decision.tool_name,
        rationale=decision.rationale,
        risk=registry.spec_for(decision.tool_name).risk,
        requested_at=incident.reported_at + timedelta(seconds=sequence * 10),
        parameters=decision.parameters,
    )
    return executor.execute(action)


def advance(
    planner: RuleBasedPlanner,
    environment: SimulatedEnvironment,
    registry: ToolRegistry,
    executor: ActionExecutor,
    executions: tuple[ActionExecutionRecord, ...],
) -> tuple[ActionDecision, tuple[ActionExecutionRecord, ...]]:
    decision = planner.decide(
        make_context(environment, registry, executions=executions)
    )
    assert isinstance(decision, ActionDecision)
    record = execute_decision(
        environment,
        registry,
        executor,
        decision,
        sequence=len(executions) + 1,
    )
    return decision, (*executions, record)


def test_rule_based_planner_satisfies_policy_protocol() -> None:
    assert isinstance(RuleBasedPlanner(), PlanningPolicy)
    assert RuleBasedPlanner.name == "station_connectivity_rule_based_v1"


def test_first_decision_measures_affected_station_connectivity() -> None:
    environment, registry, _ = make_runtime()

    decision = RuleBasedPlanner().decide(make_context(environment, registry))

    assert isinstance(decision, ActionDecision)
    assert decision.tool_name == "check_connectivity"
    assert decision.parameters == {"asset_id": "ST-02"}


def test_unreachable_affected_station_causes_peer_comparison() -> None:
    environment, registry, executor = make_runtime()
    planner = RuleBasedPlanner()
    _, executions = advance(planner, environment, registry, executor, ())

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, ActionDecision)
    assert decision.tool_name == "check_connectivity"
    assert decision.parameters == {"asset_id": "ST-01"}


def test_reachable_affected_station_skips_peer_and_reads_telemetry() -> None:
    environment, registry, executor = make_runtime(
        make_scenario(affected_reachable=True)
    )
    planner = RuleBasedPlanner()
    _, executions = advance(planner, environment, registry, executor, ())

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, ActionDecision)
    assert decision.tool_name == "read_telemetry"
    assert decision.parameters == {"asset_id": "ST-02"}


def test_reachable_peer_causes_affected_telemetry_measurement() -> None:
    environment, registry, executor = make_runtime()
    planner = RuleBasedPlanner()
    executions: tuple[ActionExecutionRecord, ...] = ()
    _, executions = advance(planner, environment, registry, executor, executions)
    _, executions = advance(planner, environment, registry, executor, executions)

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, ActionDecision)
    assert decision.tool_name == "read_telemetry"
    assert decision.parameters == {"asset_id": "ST-02"}


def test_supported_three_observation_pattern_completes_investigation() -> None:
    environment, registry, executor = make_runtime()
    planner = RuleBasedPlanner()
    executions: tuple[ActionExecutionRecord, ...] = ()
    for _ in range(3):
        _, executions = advance(planner, environment, registry, executor, executions)

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, CompleteDecision)
    assert decision.claim == "The observed connectivity failure is isolated to ST-02."
    assert decision.observation_ids == tuple(
        record.observations[0].observation_id for record in executions
    )
    assert decision.confidence == 0.95


def test_unreachable_peer_stops_without_claiming_isolated_failure() -> None:
    environment, registry, executor = make_runtime(make_scenario(peer_reachable=False))
    planner = RuleBasedPlanner()
    executions: tuple[ActionExecutionRecord, ...] = ()
    for _ in range(2):
        _, executions = advance(planner, environment, registry, executor, executions)

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, StopDecision)
    assert decision.reason is StopReason.INSUFFICIENT_EVIDENCE


def test_conflicting_telemetry_stops_without_claiming_completion() -> None:
    environment, registry, executor = make_runtime(
        make_scenario(affected_telemetry=True)
    )
    planner = RuleBasedPlanner()
    executions: tuple[ActionExecutionRecord, ...] = ()
    for _ in range(3):
        _, executions = advance(planner, environment, registry, executor, executions)

    decision = planner.decide(make_context(environment, registry, executions=executions))

    assert isinstance(decision, StopDecision)
    assert decision.reason is StopReason.INSUFFICIENT_EVIDENCE


def test_missing_required_tool_returns_no_safe_action() -> None:
    environment, _, _ = make_runtime()
    empty_registry = ToolRegistry()

    decision = RuleBasedPlanner().decide(make_context(environment, empty_registry))

    assert isinstance(decision, StopDecision)
    assert decision.reason is StopReason.NO_SAFE_ACTION


def test_failed_attempt_is_not_repeated_automatically() -> None:
    environment, registry, executor = make_runtime()
    incident = environment.brief.incident
    failed_record = executor.execute(
        Action(
            action_id="ACT-001",
            incident_id=incident.incident_id,
            tool_name="check_connectivity",
            rationale="Attempt a diagnostic request with a mismatched risk.",
            risk=ActionRisk.HIGH_IMPACT,
            requested_at=incident.reported_at + timedelta(seconds=10),
            parameters={"asset_id": "ST-02"},
        )
    )

    decision = RuleBasedPlanner().decide(
        make_context(environment, registry, executions=(failed_record,))
    )

    assert isinstance(decision, StopDecision)
    assert decision.reason is StopReason.INSUFFICIENT_EVIDENCE


def test_missing_station_peer_returns_no_safe_action() -> None:
    environment, registry, executor = make_runtime()
    planner = RuleBasedPlanner()
    _, executions = advance(planner, environment, registry, executor, ())

    decision = planner.decide(
        make_context(
            environment,
            registry,
            executions=executions,
            known_asset_ids=("ST-02", "GW-01"),
        )
    )

    assert isinstance(decision, StopDecision)
    assert decision.reason is StopReason.NO_SAFE_ACTION
