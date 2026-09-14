"""Controlled A/B evaluation of rule-based and hypothesis-driven planners."""

from dataclasses import dataclass

from agentic_manufacturing_incident_lab.agent import (
    HypothesisDrivenPlanner,
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.evaluation.agent_metrics import (
    measure_agent_operations,
)
from agentic_manufacturing_incident_lab.evaluation.catalog import (
    BenchmarkCase,
    build_controlled_benchmark_catalog,
)
from agentic_manufacturing_incident_lab.hypotheses import (
    ConnectivityHypothesisPolicy,
)
from agentic_manufacturing_incident_lab.simulation import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


@dataclass(frozen=True, slots=True)
class PlannerComparisonRow:
    """Comparable outputs from two planners on one immutable scenario."""

    case: str
    rule_status: str
    hypothesis_status: str
    rule_actions: int
    hypothesis_actions: int
    action_delta: int
    same_tool_sequence: bool
    same_evidence: bool
    hypothesis_resolution: float | None


def _default_cases() -> tuple[BenchmarkCase, ...]:
    return tuple(
        case
        for case in build_controlled_benchmark_catalog()
        if case.scenario.scenario_id
        in {
            "station-connectivity-isolation",
            "station-connectivity-shared-infrastructure",
            "station-telemetry-path-ambiguous",
        }
        and case.case_id != "action-budget-safe-stop-seed-43"
    )


def run_planner_comparison(
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> tuple[PlannerComparisonRow, ...]:
    """Run both planners in isolated simulators with identical public inputs."""
    selected = _default_cases() if cases is None else tuple(cases)
    if not selected:
        raise ValueError("planner comparison requires at least one case")

    rows = []
    for case in selected:
        rule_environment = SimulatedEnvironment(case.scenario)
        hypothesis_environment = SimulatedEnvironment(case.scenario)
        brief = case.scenario.to_brief()
        rule_run = SingleAgentRunner(
            policy=RuleBasedPlanner(),
            registry=build_diagnostic_registry(rule_environment),
            action_limit=case.action_limit,
        ).run(
            incident=brief.incident,
            known_asset_ids=brief.known_asset_ids,
        )
        hypothesis_run = SingleAgentRunner(
            policy=HypothesisDrivenPlanner(),
            registry=build_diagnostic_registry(hypothesis_environment),
            hypothesis_policy=ConnectivityHypothesisPolicy(),
            action_limit=case.action_limit,
        ).run(
            incident=brief.incident,
            known_asset_ids=brief.known_asset_ids,
        )
        rule_tools = tuple(item.action.tool_name for item in rule_run.executions)
        hypothesis_tools = tuple(
            item.action.tool_name for item in hypothesis_run.executions
        )
        rule_claims = tuple(item.claim for item in rule_run.evidence)
        hypothesis_claims = tuple(item.claim for item in hypothesis_run.evidence)
        rule_actions = len(rule_run.executions)
        hypothesis_actions = len(hypothesis_run.executions)
        rows.append(
            PlannerComparisonRow(
                case=case.case_id,
                rule_status=rule_run.final_state.status.value,
                hypothesis_status=hypothesis_run.final_state.status.value,
                rule_actions=rule_actions,
                hypothesis_actions=hypothesis_actions,
                action_delta=hypothesis_actions - rule_actions,
                same_tool_sequence=rule_tools == hypothesis_tools,
                same_evidence=rule_claims == hypothesis_claims,
                hypothesis_resolution=measure_agent_operations(
                    hypothesis_run
                ).hypothesis_resolution_rate,
            )
        )
    return tuple(rows)
