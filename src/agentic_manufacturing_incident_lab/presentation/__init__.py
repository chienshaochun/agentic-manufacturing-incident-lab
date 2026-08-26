"""Framework-independent presentation models for UI adapters."""

from agentic_manufacturing_incident_lab.presentation.builders import (
    build_benchmark_presentation,
    build_case_presentation,
)
from agentic_manufacturing_incident_lab.presentation.models import (
    ActionAttemptView,
    BenchmarkPresentation,
    BenchmarkRow,
    CasePresentation,
    EvidenceView,
    FailureView,
    HandoffView,
    MetricCard,
    ReportView,
    SafetyView,
)

__all__ = [
    "ActionAttemptView",
    "BenchmarkPresentation",
    "BenchmarkRow",
    "CasePresentation",
    "EvidenceView",
    "FailureView",
    "HandoffView",
    "MetricCard",
    "ReportView",
    "SafetyView",
    "build_benchmark_presentation",
    "build_case_presentation",
]
