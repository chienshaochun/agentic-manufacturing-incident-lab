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
    AlarmHistoryTool,
    ConfigurationTool,
    ConnectivityTool,
    IncidentScopeError,
    MaintenanceRecordTool,
    SensorFreshnessTool,
    TelemetryTool,
)
from agentic_manufacturing_incident_lab.tools.registry import (
    DuplicateToolError,
    ToolRegistry,
    ToolRiskMismatchError,
    UnknownToolError,
)
from agentic_manufacturing_incident_lab.tools.catalog import (
    build_diagnostic_registry,
    build_manufacturing_diagnostic_registry,
)

__all__ = [
    "AlarmHistoryTool",
    "ConfigurationTool",
    "ConnectivityTool",
    "DuplicateToolError",
    "FaultInjectingTool",
    "IncidentScopeError",
    "MaintenanceRecordTool",
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
    "build_manufacturing_diagnostic_registry",
    "SensorFreshnessTool",
]
