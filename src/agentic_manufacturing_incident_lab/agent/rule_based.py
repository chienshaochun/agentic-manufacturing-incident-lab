"""Deterministic planning policy for the station connectivity scenario."""

from agentic_manufacturing_incident_lab.agent.contracts import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningDecision,
    StopDecision,
    StopReason,
)
from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.domain.models import Observation


class RuleBasedPlanner:
    """Choose the next diagnostic step using only agent-visible evidence."""

    name = "station_connectivity_rule_based_v1"

    _CONNECTIVITY_TOOL = "check_connectivity"
    _TELEMETRY_TOOL = "read_telemetry"

    def decide(self, context: AgentContext) -> PlanningDecision:
        """Return one evidence-driven action, completion, or controlled stop."""
        affected_asset_id = context.incident.asset_id
        affected_connectivity = self._successful_observation(
            context,
            tool_name=self._CONNECTIVITY_TOOL,
            asset_id=affected_asset_id,
        )
        if affected_connectivity is None:
            return self._action_or_stop(
                context,
                tool_name=self._CONNECTIVITY_TOOL,
                asset_id=affected_asset_id,
                rationale="Measure connectivity of the incident's affected station first.",
            )

        affected_reachable = affected_connectivity.values.get("network_reachable")
        if not isinstance(affected_reachable, bool):
            return self._insufficient(
                "The affected station connectivity observation has no boolean "
                "network_reachable value."
            )

        if affected_reachable:
            affected_telemetry = self._successful_observation(
                context,
                tool_name=self._TELEMETRY_TOOL,
                asset_id=affected_asset_id,
            )
            if affected_telemetry is None:
                return self._action_or_stop(
                    context,
                    tool_name=self._TELEMETRY_TOOL,
                    asset_id=affected_asset_id,
                    rationale=(
                        "Connectivity is healthy, so measure the affected station's "
                        "telemetry path next."
                    ),
                )
            return self._insufficient(
                "Connectivity is healthy, but the available read-only tools cannot "
                "localize the remaining telemetry-path condition safely."
            )

        peer_asset_id = self._select_station_peer(context, affected_asset_id)
        if peer_asset_id is None:
            return StopDecision(
                reason=StopReason.NO_SAFE_ACTION,
                rationale=(
                    "No other known station is available for a comparison measurement."
                ),
            )

        peer_connectivity = self._successful_observation(
            context,
            tool_name=self._CONNECTIVITY_TOOL,
            asset_id=peer_asset_id,
        )
        if peer_connectivity is None:
            return self._action_or_stop(
                context,
                tool_name=self._CONNECTIVITY_TOOL,
                asset_id=peer_asset_id,
                rationale=(
                    "Compare a peer station to distinguish an isolated fault from "
                    "shared infrastructure failure."
                ),
            )

        peer_reachable = peer_connectivity.values.get("network_reachable")
        if not isinstance(peer_reachable, bool):
            return self._insufficient(
                "The peer connectivity observation has no boolean "
                "network_reachable value."
            )
        if not peer_reachable:
            return self._insufficient(
                "Both the affected and peer stations are unreachable, so the evidence "
                "does not support an isolated-station conclusion."
            )

        affected_telemetry = self._successful_observation(
            context,
            tool_name=self._TELEMETRY_TOOL,
            asset_id=affected_asset_id,
        )
        if affected_telemetry is None:
            return self._action_or_stop(
                context,
                tool_name=self._TELEMETRY_TOOL,
                asset_id=affected_asset_id,
                rationale=(
                    "Confirm that telemetry is also unavailable on the isolated "
                    "unreachable station."
                ),
            )

        telemetry_available = affected_telemetry.values.get("telemetry_available")
        if not isinstance(telemetry_available, bool):
            return self._insufficient(
                "The telemetry observation has no boolean telemetry_available value."
            )
        if telemetry_available:
            return self._insufficient(
                "The affected station is unreachable while telemetry remains available; "
                "the observations conflict with the supported isolation pattern."
            )

        return CompleteDecision(
            rationale=(
                "The affected station is unreachable and has no telemetry while a peer "
                "station remains reachable."
            ),
            claim=f"The observed connectivity failure is isolated to {affected_asset_id}.",
            observation_ids=(
                affected_connectivity.observation_id,
                peer_connectivity.observation_id,
                affected_telemetry.observation_id,
            ),
            confidence=0.95,
        )

    @classmethod
    def _action_or_stop(
        cls,
        context: AgentContext,
        *,
        tool_name: str,
        asset_id: str,
        rationale: str,
    ) -> PlanningDecision:
        if tool_name not in {spec.name for spec in context.available_tools}:
            return StopDecision(
                reason=StopReason.NO_SAFE_ACTION,
                rationale=f"Required allowlisted tool is unavailable: {tool_name}.",
            )
        if cls._was_attempted(context, tool_name=tool_name, asset_id=asset_id):
            return cls._insufficient(
                f"The previous {tool_name} attempt for {asset_id} produced no usable "
                "observation; the policy will not repeat it automatically."
            )
        return ActionDecision(
            tool_name=tool_name,
            rationale=rationale,
            parameters={"asset_id": asset_id},
        )

    @staticmethod
    def _successful_observation(
        context: AgentContext,
        *,
        tool_name: str,
        asset_id: str,
    ) -> Observation | None:
        for record in reversed(context.executions):
            if (
                record.action.tool_name == tool_name
                and record.action.parameters.get("asset_id") == asset_id
                and record.result.status is ActionResultStatus.SUCCEEDED
                and len(record.observations) == 1
            ):
                return record.observations[0]
        return None

    @staticmethod
    def _was_attempted(
        context: AgentContext,
        *,
        tool_name: str,
        asset_id: str,
    ) -> bool:
        return any(
            record.action.tool_name == tool_name
            and record.action.parameters.get("asset_id") == asset_id
            for record in context.executions
        )

    @staticmethod
    def _select_station_peer(
        context: AgentContext,
        affected_asset_id: str,
    ) -> str | None:
        station_peers = sorted(
            asset_id
            for asset_id in context.known_asset_ids
            if asset_id.startswith("ST-") and asset_id != affected_asset_id
        )
        return station_peers[0] if station_peers else None

    @staticmethod
    def _insufficient(rationale: str) -> StopDecision:
        return StopDecision(
            reason=StopReason.INSUFFICIENT_EVIDENCE,
            rationale=rationale,
        )
