"""Read-only diagnostic tools backed by the deterministic simulation environment."""

from typing import cast

from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk
from agentic_manufacturing_incident_lab.simulation.environment import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools.contracts import (
    ToolParameter,
    ToolParameterType,
    ToolResponse,
    ToolSpec,
)


class IncidentScopeError(ValueError):
    """Raised when an action targets a different incident than the environment."""


def _require_matching_incident(action: Action, environment: SimulatedEnvironment) -> None:
    expected_incident_id = environment.brief.incident.incident_id
    if action.incident_id != expected_incident_id:
        raise IncidentScopeError(
            f"action incident {action.incident_id} does not match environment incident "
            f"{expected_incident_id}"
        )


class ConnectivityTool:
    """Expose the environment's connectivity sensor through a tool contract."""

    __slots__ = ("_environment",)

    spec = ToolSpec(
        name="check_connectivity",
        description="Check whether one synthetic asset is reachable on the network.",
        risk=ActionRisk.READ_ONLY,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset identifier to measure.",
                value_type=ToolParameterType.STRING,
            ),
        ),
    )

    def __init__(self, environment: SimulatedEnvironment) -> None:
        self._environment = environment

    def invoke(self, action: Action) -> ToolResponse:
        _require_matching_incident(action, self._environment)
        asset_id = cast(str, action.parameters["asset_id"])
        observation = self._environment.measure_connectivity(asset_id)
        return ToolResponse(
            summary=f"Connectivity measurement completed for {asset_id}.",
            observations=(observation,),
        )


class TelemetryTool:
    """Expose the environment's telemetry sensor through a tool contract."""

    __slots__ = ("_environment",)

    spec = ToolSpec(
        name="read_telemetry",
        description="Check whether telemetry is available for one synthetic asset.",
        risk=ActionRisk.READ_ONLY,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset identifier to measure.",
                value_type=ToolParameterType.STRING,
            ),
        ),
    )

    def __init__(self, environment: SimulatedEnvironment) -> None:
        self._environment = environment

    def invoke(self, action: Action) -> ToolResponse:
        _require_matching_incident(action, self._environment)
        asset_id = cast(str, action.parameters["asset_id"])
        observation = self._environment.measure_telemetry(asset_id)
        return ToolResponse(
            summary=f"Telemetry measurement completed for {asset_id}.",
            observations=(observation,),
        )
