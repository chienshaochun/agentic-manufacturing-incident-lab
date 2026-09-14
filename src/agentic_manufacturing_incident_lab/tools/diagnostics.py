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


class _AssetReadTool:
    """Shared implementation for single-asset read-only diagnostic tools."""

    __slots__ = ("_environment",)
    spec: ToolSpec
    _method_name: str
    _result_label: str

    def __init__(self, environment: SimulatedEnvironment) -> None:
        self._environment = environment

    def invoke(self, action: Action) -> ToolResponse:
        _require_matching_incident(action, self._environment)
        asset_id = cast(str, action.parameters["asset_id"])
        observation = getattr(self._environment, self._method_name)(asset_id)
        return ToolResponse(
            summary=f"{self._result_label} completed for {asset_id}.",
            observations=(observation,),
        )


def _asset_read_spec(name: str, description: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        risk=ActionRisk.READ_ONLY,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset identifier to inspect.",
                value_type=ToolParameterType.STRING,
            ),
        ),
    )


class AlarmHistoryTool(_AssetReadTool):
    spec = _asset_read_spec("read_alarm_history", "Read recent alarms for one asset.")
    _method_name = "read_alarm_history"
    _result_label = "Alarm history read"


class ConfigurationTool(_AssetReadTool):
    spec = _asset_read_spec(
        "inspect_configuration",
        "Compare actual and expected configuration for one asset.",
    )
    _method_name = "inspect_configuration"
    _result_label = "Configuration inspection"


class MaintenanceRecordTool(_AssetReadTool):
    spec = _asset_read_spec(
        "read_maintenance_record",
        "Read the planned-maintenance state for one asset.",
    )
    _method_name = "read_maintenance_record"
    _result_label = "Maintenance record read"


class SensorFreshnessTool(_AssetReadTool):
    spec = _asset_read_spec(
        "check_sensor_freshness",
        "Check the age and freshness of sensor data for one asset.",
    )
    _method_name = "check_sensor_freshness"
    _result_label = "Sensor freshness measurement"
