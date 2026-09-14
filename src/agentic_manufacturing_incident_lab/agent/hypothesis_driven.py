"""Hypothesis-aware planning with explicit utility scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from agentic_manufacturing_incident_lab.agent.contracts import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningDecision,
    StopDecision,
    StopReason,
)
from agentic_manufacturing_incident_lab.agent.rule_based import RuleBasedPlanner
from agentic_manufacturing_incident_lab.domain import (
    ActionRisk,
    HypothesisStatus,
)
from agentic_manufacturing_incident_lab.domain.models import ScalarValue


_RISK_COST = {
    ActionRisk.READ_ONLY: 0.0,
    ActionRisk.CONTROLLED_WRITE: 0.40,
    ActionRisk.HIGH_IMPACT: 1.00,
}


@dataclass(frozen=True, slots=True)
class DiagnosticProbe:
    """One candidate measurement and the hypotheses it can distinguish."""

    tool_name: str
    parameters: Mapping[str, ScalarValue]
    rationale: str
    hypothesis_suffixes: tuple[str, ...]
    information_value: float
    execution_cost: float

    def __post_init__(self) -> None:
        if not self.tool_name.strip() or not self.rationale.strip():
            raise ValueError("probe tool_name and rationale must not be blank")
        suffixes = tuple(self.hypothesis_suffixes)
        if not suffixes or len(set(suffixes)) != len(suffixes):
            raise ValueError("probe hypothesis_suffixes must be non-empty and unique")
        if not 0.0 <= self.information_value <= 1.0:
            raise ValueError("information_value must be between 0.0 and 1.0")
        if not 0.0 <= self.execution_cost <= 1.0:
            raise ValueError("execution_cost must be between 0.0 and 1.0")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "hypothesis_suffixes", suffixes)


@dataclass(frozen=True, slots=True)
class ProbeScore:
    """Auditable utility decomposition for one available probe."""

    probe: DiagnosticProbe
    unresolved_coverage: float
    risk_cost: float
    repeat_cost: float
    utility: float


def score_probe(context: AgentContext, probe: DiagnosticProbe) -> ProbeScore:
    """Score information coverage after explicit safety and resource costs."""
    unresolved = tuple(
        item
        for item in context.hypotheses
        if item.status in {HypothesisStatus.OPEN, HypothesisStatus.INCONCLUSIVE}
    )
    distinguished = tuple(
        item
        for item in unresolved
        if any(item.hypothesis_id.endswith(suffix) for suffix in probe.hypothesis_suffixes)
    )
    coverage = len(distinguished) / len(unresolved) if unresolved else 0.0
    spec = next(
        (item for item in context.available_tools if item.name == probe.tool_name),
        None,
    )
    risk_cost = _RISK_COST[spec.risk] if spec is not None else 1.0
    repeated = any(
        record.action.tool_name == probe.tool_name
        and dict(record.action.parameters) == dict(probe.parameters)
        for record in context.executions
    )
    repeat_cost = 1.0 if repeated else 0.0
    utility = (
        probe.information_value * coverage
        - probe.execution_cost
        - risk_cost
        - repeat_cost
    )
    return ProbeScore(
        probe=probe,
        unresolved_coverage=coverage,
        risk_cost=risk_cost,
        repeat_cost=repeat_cost,
        utility=utility,
    )


class HypothesisDrivenPlanner:
    """Select the safest high-value probe over unresolved hypotheses."""

    name = "station_hypothesis_utility_v1"

    def __init__(self) -> None:
        self._terminal_policy = RuleBasedPlanner()

    def decide(self, context: AgentContext) -> PlanningDecision:
        """Use legacy completion gates but dynamically rank measurement options."""
        terminal_or_next = self._terminal_policy.decide(context)
        if isinstance(terminal_or_next, (CompleteDecision, StopDecision)):
            return terminal_or_next
        if not context.hypotheses:
            return StopDecision(
                reason=StopReason.INSUFFICIENT_EVIDENCE,
                rationale="Hypothesis-aware planning requires candidate hypotheses.",
            )

        scores = tuple(
            score_probe(context, probe)
            for probe in self._candidate_probes(context)
        )
        eligible = tuple(
            score
            for score in scores
            if score.utility > 0.0 and score.repeat_cost == 0.0
        )
        if not eligible:
            return StopDecision(
                reason=StopReason.NO_SAFE_ACTION,
                rationale=(
                    "No untried diagnostic probe has positive information utility."
                ),
            )
        selected = sorted(
            eligible,
            key=lambda item: (-item.utility, item.probe.tool_name, str(dict(item.probe.parameters))),
        )[0]
        probe = selected.probe
        return ActionDecision(
            tool_name=probe.tool_name,
            parameters=probe.parameters,
            rationale=(
                f"{probe.rationale} Utility={selected.utility:.3f} "
                f"(coverage={selected.unresolved_coverage:.3f}, "
                f"risk={selected.risk_cost:.3f}, cost={probe.execution_cost:.3f})."
            ),
        )

    def _candidate_probes(self, context: AgentContext) -> tuple[DiagnosticProbe, ...]:
        affected = context.incident.asset_id
        observations = context.observations
        affected_connectivity = self._value(
            observations,
            affected,
            "network_reachable",
        )
        peers = sorted(
            item for item in context.known_asset_ids
            if item.startswith("ST-") and item != affected
        )
        probes = [
            DiagnosticProbe(
                tool_name="check_connectivity",
                parameters={"asset_id": affected},
                rationale="Measure connectivity of the incident's affected station first.",
                hypothesis_suffixes=("-STATION", "-SHARED", "-TELEMETRY"),
                information_value=1.0,
                execution_cost=0.05,
            )
        ]
        if affected_connectivity is False and peers:
            probes.append(
                DiagnosticProbe(
                    tool_name="check_connectivity",
                    parameters={"asset_id": peers[0]},
                    rationale=(
                        "Compare a peer station to distinguish an isolated fault "
                        "from shared infrastructure failure."
                    ),
                    hypothesis_suffixes=("-STATION", "-SHARED"),
                    information_value=1.0,
                    execution_cost=0.05,
                )
            )
        if affected_connectivity is not None:
            probes.append(
                DiagnosticProbe(
                    tool_name="read_telemetry",
                    parameters={"asset_id": affected},
                    rationale=(
                        "Measure the affected station telemetry path to distinguish "
                        "station and telemetry hypotheses."
                    ),
                    hypothesis_suffixes=("-STATION", "-TELEMETRY"),
                    information_value=0.85,
                    execution_cost=0.05,
                )
            )
        return tuple(probes)

    @staticmethod
    def _value(observations, asset_id: str, key: str) -> bool | None:
        for observation in reversed(observations):
            if observation.values.get("asset_id") == asset_id:
                value = observation.values.get(key)
                if isinstance(value, bool):
                    return value
        return None
