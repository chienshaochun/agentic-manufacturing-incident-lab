"""Allowlisted tool contracts and registry infrastructure."""

from agentic_manufacturing_incident_lab.tools.contracts import (
    Tool,
    ToolParameter,
    ToolParameterError,
    ToolParameterType,
    ToolResponse,
    ToolSpec,
)
from agentic_manufacturing_incident_lab.tools.diagnostics import (
    ConnectivityTool,
    IncidentScopeError,
    TelemetryTool,
)
from agentic_manufacturing_incident_lab.tools.registry import (
    DuplicateToolError,
    ToolRegistry,
    ToolRiskMismatchError,
    UnknownToolError,
)
from agentic_manufacturing_incident_lab.tools.catalog import build_diagnostic_registry

__all__ = [
    "ConnectivityTool",
    "DuplicateToolError",
    "IncidentScopeError",
    "Tool",
    "ToolParameter",
    "ToolParameterError",
    "ToolParameterType",
    "ToolRegistry",
    "ToolResponse",
    "ToolRiskMismatchError",
    "ToolSpec",
    "TelemetryTool",
    "UnknownToolError",
    "build_diagnostic_registry",
]
