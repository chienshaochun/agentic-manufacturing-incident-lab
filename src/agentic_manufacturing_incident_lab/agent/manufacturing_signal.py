"""Hypothesis-driven planner for multi-source manufacturing signal incidents."""

from agentic_manufacturing_incident_lab.agent.contracts import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningDecision,
    StopDecision,
    StopReason,
)
from agentic_manufacturing_incident_lab.agent.hypothesis_driven import (
    DiagnosticProbe,
    score_probe,
)
from agentic_manufacturing_incident_lab.domain import HypothesisStatus


class ManufacturingSignalPlanner:
    """Investigate flatlined process values across independent data sources."""

    name = "manufacturing_signal_utility_v1"

    def decide(self, context: AgentContext) -> PlanningDecision:
        supported = tuple(
            item for item in context.hypotheses
            if item.status is HypothesisStatus.SUPPORTED
        )
        rejected = tuple(
            item for item in context.hypotheses
            if item.status is HypothesisStatus.REJECTED
        )
        if len(supported) == 1 and len(rejected) == len(context.hypotheses) - 1:
            winner = supported[0]
            return CompleteDecision(
                rationale=(
                    "One cause is supported and every competing hypothesis is rejected "
                    "by independent read-only observations."
                ),
                claim=self._claim(context.incident.asset_id, winner.hypothesis_id),
                observation_ids=tuple(
                    observation.observation_id for observation in context.observations
                ),
                confidence=winner.confidence,
            )

        scores = tuple(
            score_probe(context, probe) for probe in self._probes(context.incident.asset_id)
        )
        eligible = tuple(
            item for item in scores
            if item.utility > 0.0 and item.repeat_cost == 0.0
        )
        if not eligible:
            return StopDecision(
                reason=StopReason.INSUFFICIENT_EVIDENCE,
                rationale=(
                    "Multi-source observations did not isolate exactly one cause, "
                    "and no positive-utility probe remains."
                ),
            )
        selected = sorted(
            eligible,
            key=lambda item: (-item.utility, item.probe.tool_name),
        )[0]
        return ActionDecision(
            tool_name=selected.probe.tool_name,
            parameters=selected.probe.parameters,
            rationale=(
                f"{selected.probe.rationale} Utility={selected.utility:.3f} "
                f"(coverage={selected.unresolved_coverage:.3f}, "
                f"risk={selected.risk_cost:.3f}, "
                f"cost={selected.probe.execution_cost:.3f})."
            ),
        )

    @staticmethod
    def _probes(asset_id: str) -> tuple[DiagnosticProbe, ...]:
        return (
            DiagnosticProbe(
                "read_alarm_history", {"asset_id": asset_id},
                "Read alarm history for an initial symptom fingerprint.",
                ("-SENSOR", "-CONFIG", "-TELEMETRY"), 1.00, 0.10,
            ),
            DiagnosticProbe(
                "check_connectivity", {"asset_id": asset_id},
                "Verify the affected station network path.",
                ("-NETWORK",), 1.00, 0.05,
            ),
            DiagnosticProbe(
                "read_telemetry", {"asset_id": asset_id},
                "Verify that the telemetry transport still returns data.",
                ("-TELEMETRY",), 0.95, 0.05,
            ),
            DiagnosticProbe(
                "inspect_configuration", {"asset_id": asset_id},
                "Compare the active and expected configuration versions.",
                ("-CONFIG",), 0.90, 0.05,
            ),
            DiagnosticProbe(
                "read_maintenance_record", {"asset_id": asset_id},
                "Check whether planned maintenance explains the signal gap.",
                ("-MAINTENANCE",), 0.85, 0.05,
            ),
            DiagnosticProbe(
                "check_sensor_freshness", {"asset_id": asset_id},
                "Measure whether source sensor values are still refreshing.",
                ("-SENSOR",), 0.80, 0.05,
            ),
        )

    @staticmethod
    def _claim(asset_id: str, hypothesis_id: str) -> str:
        if hypothesis_id.endswith("-SENSOR"):
            return f"The flatlined process signal is caused by stale sensor data on {asset_id}."
        if hypothesis_id.endswith("-CONFIG"):
            return f"The flatlined process signal is caused by configuration drift on {asset_id}."
        if hypothesis_id.endswith("-NETWORK"):
            return f"The flatlined process signal is caused by network loss on {asset_id}."
        if hypothesis_id.endswith("-TELEMETRY"):
            return f"The flatlined process signal is caused by telemetry service loss on {asset_id}."
        return f"The flatlined process signal is explained by planned maintenance on {asset_id}."
