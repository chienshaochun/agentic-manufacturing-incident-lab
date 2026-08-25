"""Run Phase 5 approval and failure-recovery demonstrations from the terminal."""

import argparse

from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    CompleteDecision,
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.recovery import RecoveryDisposition
from agentic_manufacturing_incident_lab.runtime import RetryPolicy
from agentic_manufacturing_incident_lab.safety import ApprovalOutcome
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    ConnectivityTool,
    FaultInjectingTool,
    InjectedFault,
    TelemetryTool,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
    ToolResponse,
    ToolSpec,
)


class ControlledCacheRefreshTool:
    """Synthetic controlled write used only to demonstrate approval gating."""

    spec = ToolSpec(
        name="refresh_diagnostic_cache",
        description="Refresh a synthetic adapter cache, then read telemetry.",
        risk=ActionRisk.CONTROLLED_WRITE,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset whose adapter cache is refreshed.",
                value_type=ToolParameterType.STRING,
            ),
        ),
    )

    def __init__(self, environment: SimulatedEnvironment) -> None:
        self._environment = environment
        self.call_count = 0

    def invoke(self, action: Action) -> ToolResponse:
        self.call_count += 1
        asset_id = action.parameters["asset_id"]
        assert isinstance(asset_id, str)
        observation = self._environment.measure_telemetry(asset_id)
        return ToolResponse(
            summary=f"Synthetic diagnostic cache refreshed for {asset_id}.",
            observations=(observation,),
        )


class CacheRefreshPolicy:
    """Propose one controlled action and finish only after its observation exists."""

    name = "controlled_cache_refresh_demo_v1"

    def decide(self, context):
        if not context.executions:
            return ActionDecision(
                tool_name="refresh_diagnostic_cache",
                rationale=(
                    "Refresh the synthetic diagnostic cache during an approved "
                    "maintenance window."
                ),
                parameters={"asset_id": context.incident.asset_id},
            )
        observation = context.observations[-1]
        return CompleteDecision(
            rationale="The approved operation returned a post-action measurement.",
            claim="The controlled cache refresh produced a telemetry measurement.",
            observation_ids=(observation.observation_id,),
            confidence=1.0,
        )


def run_approval_demo(outcome: ApprovalOutcome) -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    tool = ControlledCacheRefreshTool(environment)
    runner = SingleAgentRunner(
        policy=CacheRefreshPolicy(),
        registry=ToolRegistry((tool,)),
    )
    brief = environment.brief

    waiting = runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    pending = waiting.pending_approval

    print("=== Human approval gate ===")
    print(f"status before decision: {waiting.final_state.status.value}")
    print(f"pending action: {pending.action.action_id if pending else 'none'}")
    print(f"tool calls before decision: {tool.call_count}")
    print(
        "action budget before decision: "
        f"{waiting.final_memory.step_budget.actions_used}"
    )

    resolved = runner.resolve_approval(
        waiting,
        outcome=outcome,
        decided_by="walkthrough-operator",
        rationale=f"Operator selected {outcome.value} in the walkthrough.",
        known_asset_ids=brief.known_asset_ids,
    )

    print(f"operator decision: {outcome.value}")
    print(f"status after decision: {resolved.final_state.status.value}")
    print(f"tool calls after decision: {tool.call_count}")
    print(
        "action budget after decision: "
        f"{resolved.final_memory.step_budget.actions_used}"
    )
    print(f"evidence records: {len(resolved.evidence)}")
    print()


def run_recovery_demo() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.TIMEOUT, InjectedFault.TIMEOUT),
    )
    telemetry = FaultInjectingTool(TelemetryTool(environment), ())
    runner = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=ToolRegistry((connectivity, telemetry)),
        retry_policy=RetryPolicy(max_attempts=2),
    )
    brief = environment.brief
    run = runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    print("=== Bounded retry and recovery ===")
    for number, record in enumerate(run.executions, start=1):
        print(f"action {number}: {record.action.tool_name}")
        for attempt in record.attempts:
            error = f" error={attempt.error_code}" if attempt.error_code else ""
            print(
                f"  attempt {attempt.attempt_number}: "
                f"{attempt.status.value}{error}"
            )
        print(f"  terminal result: {record.result.status.value}")

    print("recovery assessments:")
    for recovery in run.recovery_assessments:
        alternative = (
            f" alternative={recovery.alternative_tool_name}"
            if recovery.disposition is RecoveryDisposition.TRY_ALTERNATIVE
            else ""
        )
        print(
            f"  {recovery.action_id}: {recovery.disposition.value}{alternative}"
        )
        print(f"  reason: {recovery.rationale}")
    print(f"final status: {run.final_state.status.value}")
    print(f"final reason: {run.final_state.reason}")
    print(f"evidence records: {len(run.evidence)}")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demonstrate Phase 5 safety approval and bounded recovery.",
    )
    parser.add_argument(
        "--scenario",
        choices=("all", "approval", "recovery"),
        default="all",
        help="Choose which Phase 5 demonstration to run.",
    )
    parser.add_argument(
        "--approval",
        choices=("approve", "reject"),
        default="approve",
        help="Choose the simulated human decision for the approval scenario.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scenario in {"all", "approval"}:
        outcome = (
            ApprovalOutcome.APPROVED
            if args.approval == "approve"
            else ApprovalOutcome.REJECTED
        )
        run_approval_demo(outcome)
    if args.scenario in {"all", "recovery"}:
        run_recovery_demo()


if __name__ == "__main__":
    main()
