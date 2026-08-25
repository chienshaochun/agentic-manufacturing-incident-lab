"""Structured multi-agent roles and handoff records."""

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
    HandoffLedger,
)
from agentic_manufacturing_incident_lab.collaboration.diagnostic import DiagnosticAgent
from agentic_manufacturing_incident_lab.collaboration.products import (
    DiagnosticWorkProduct,
    SafetyReviewOutcome,
    SafetyReviewProduct,
)
from agentic_manufacturing_incident_lab.collaboration.safety_reviewer import (
    SafetyReviewerAgent,
)

__all__ = [
    "AgentHandoff",
    "AgentRole",
    "DiagnosticAgent",
    "DiagnosticWorkProduct",
    "HandoffKind",
    "HandoffLedger",
    "SafetyReviewOutcome",
    "SafetyReviewProduct",
    "SafetyReviewerAgent",
]
