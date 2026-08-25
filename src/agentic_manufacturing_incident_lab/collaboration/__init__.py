"""Structured multi-agent roles and handoff records."""

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
    HandoffLedger,
)
from agentic_manufacturing_incident_lab.collaboration.coordinator import (
    CoordinatorAgent,
)
from agentic_manufacturing_incident_lab.collaboration.diagnostic import DiagnosticAgent
from agentic_manufacturing_incident_lab.collaboration.products import (
    DiagnosticWorkProduct,
    IncidentReport,
    MultiAgentRun,
    MultiAgentStatus,
    ReportWorkProduct,
    SafetyReviewOutcome,
    SafetyReviewProduct,
)
from agentic_manufacturing_incident_lab.collaboration.reporter import ReporterAgent
from agentic_manufacturing_incident_lab.collaboration.safety_reviewer import (
    SafetyReviewerAgent,
)

__all__ = [
    "AgentHandoff",
    "AgentRole",
    "CoordinatorAgent",
    "DiagnosticAgent",
    "DiagnosticWorkProduct",
    "HandoffKind",
    "HandoffLedger",
    "IncidentReport",
    "MultiAgentRun",
    "MultiAgentStatus",
    "ReporterAgent",
    "ReportWorkProduct",
    "SafetyReviewOutcome",
    "SafetyReviewProduct",
    "SafetyReviewerAgent",
]
