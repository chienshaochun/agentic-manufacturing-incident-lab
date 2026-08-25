"""Allowlisted tool contracts and registry infrastructure."""

from agentic_manufacturing_incident_lab.tools.contracts import (
    PermanentToolError,
    Tool,
    ToolInvocationError,
    ToolParameter,
    ToolParameterError,
    ToolParameterType,
    ToolResponse,
    ToolSpec,
    ToolTimeoutError,
    TransientToolError,
)
from agentic_manufacturing_incident_lab.tools.faults import (
    FaultInjectingTool,
    InjectedFault,
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
    "FaultInjectingTool",
    "IncidentScopeError",
    "InjectedFault",
    "PermanentToolError",
    "Tool",
    "ToolInvocationError",
    "ToolParameter",
    "ToolParameterError",
    "ToolParameterType",
    "ToolRegistry",
    "ToolResponse",
    "ToolRiskMismatchError",
    "ToolSpec",
    "ToolTimeoutError",
    "TelemetryTool",
    "TransientToolError",
    "UnknownToolError",
    "build_diagnostic_registry",
]
