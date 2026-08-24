"""Factory functions for environment-bound tool registries."""

from agentic_manufacturing_incident_lab.simulation.environment import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools.diagnostics import (
    ConnectivityTool,
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
