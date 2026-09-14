"""Factory functions for environment-bound tool registries."""

from agentic_manufacturing_incident_lab.simulation.environment import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools.diagnostics import (
    AlarmHistoryTool,
    ConfigurationTool,
    ConnectivityTool,
    MaintenanceRecordTool,
    SensorFreshnessTool,
    TelemetryTool,
)
from agentic_manufacturing_incident_lab.tools.registry import ToolRegistry


def build_diagnostic_registry(environment: SimulatedEnvironment) -> ToolRegistry:
    """Build the default allowlist of read-only simulated diagnostic tools."""
    return ToolRegistry(
        [
            ConnectivityTool(environment),
            TelemetryTool(environment),
        ]
    )


def build_manufacturing_diagnostic_registry(
    environment: SimulatedEnvironment,
) -> ToolRegistry:
    """Build the multi-source read-only manufacturing diagnostic allowlist."""
    return ToolRegistry(
        [
            AlarmHistoryTool(environment),
            ConnectivityTool(environment),
            TelemetryTool(environment),
            ConfigurationTool(environment),
            MaintenanceRecordTool(environment),
            SensorFreshnessTool(environment),
        ]
    )
