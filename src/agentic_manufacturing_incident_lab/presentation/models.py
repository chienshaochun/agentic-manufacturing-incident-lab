"""Immutable, UI-safe view models for the incident workbench."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricCard:
    label: str
    value: str
    help_text: str


@dataclass(frozen=True, slots=True)
class HandoffView:
    sequence: int
    sender: str
    recipient: str
    kind: str
    purpose: str
    reply_to: str


@dataclass(frozen=True, slots=True)
class ActionAttemptView:
    action_sequence: int
    action_id: str
    tool: str
    parameters: str
    risk: str
    rationale: str
    attempt: int | None
    status: str
    error_code: str
    observations: str


@dataclass(frozen=True, slots=True)
class EvidenceView:
    evidence_id: str
    claim: str
    confidence: float
    observation_ids: str


@dataclass(frozen=True, slots=True)
class SafetyView:
    outcome: str
    rationale: str
    findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportView:
    report_id: str
    title: str
    executive_summary: str
    conclusion: str
    evidence_ids: str


@dataclass(frozen=True, slots=True)
class FailureView:
    failure_id: str
    stage: str
    role: str
    kind: str
    request_id: str
    detail: str


@dataclass(frozen=True, slots=True)
class CasePresentation:
    case_id: str
    incident_id: str
    scenario_id: str
    seed: int
    workflow_status: str
    diagnostic_status: str
    passed: bool
    metrics: tuple[MetricCard, ...]
    handoffs: tuple[HandoffView, ...]
    action_attempts: tuple[ActionAttemptView, ...]
    evidence: tuple[EvidenceView, ...]
    safety: SafetyView | None
    report: ReportView | None
    failures: tuple[FailureView, ...]
    trace_text: str


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    case: str
    workflow: str
    diagnostic: str
    precision: float
    recall: float
    tool_calls: int
    handoffs: int
    failure: str
    passed: bool


@dataclass(frozen=True, slots=True)
class BenchmarkPresentation:
    metrics: tuple[MetricCard, ...]
    rows: tuple[BenchmarkRow, ...]
    summary_text: str
