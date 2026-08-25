"""Immutable expectations and metrics for controlled agent benchmarks."""

from dataclasses import dataclass

from agentic_manufacturing_incident_lab.collaboration import (
    CollaborationFailureKind,
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.domain._validation import require_text
from agentic_manufacturing_incident_lab.domain.task import TaskStatus


def _require_non_negative_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_score(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number between 0.0 and 1.0")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def _validated_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(values)
    for value in normalized:
        require_text(value, field_name)
    return normalized


@dataclass(frozen=True, slots=True)
class BenchmarkExpectation:
    """Answer key and resource limits for one controlled benchmark case."""

    case_id: str
    scenario_id: str
    seed: int
    incident_id: str
    expected_multi_status: MultiAgentStatus
    expected_diagnostic_status: TaskStatus | None
    expected_tool_sequence: tuple[str, ...]
    expected_evidence_claims: tuple[str, ...]
    expected_safety_outcome: SafetyReviewOutcome | None
    expect_report: bool
    expected_failure_kinds: tuple[CollaborationFailureKind, ...] = ()
    max_tool_calls: int = 32
    max_handoffs: int = 6

    def __post_init__(self) -> None:
        for field_name in ("case_id", "scenario_id", "incident_id"):
            require_text(getattr(self, field_name), field_name)
        _require_non_negative_int(self.seed, "seed")
        tool_sequence = _validated_text_tuple(
            self.expected_tool_sequence,
            "expected_tool_sequence",
        )
        evidence_claims = _validated_text_tuple(
            self.expected_evidence_claims,
            "expected_evidence_claims",
        )
        failure_kinds = tuple(self.expected_failure_kinds)
        _require_non_negative_int(self.max_tool_calls, "max_tool_calls")
        _require_non_negative_int(self.max_handoffs, "max_handoffs")
        if len(tool_sequence) > self.max_tool_calls:
            raise ValueError("expected tool sequence exceeds max_tool_calls")

        if self.expected_diagnostic_status is None:
            if tool_sequence or evidence_claims:
                raise ValueError(
                    "missing diagnostic outcome cannot expect tools or evidence"
                )
            if self.expected_safety_outcome is not None or self.expect_report:
                raise ValueError(
                    "missing diagnostic outcome cannot expect review or report"
                )

        if self.expect_report:
            if self.expected_multi_status is not MultiAgentStatus.COMPLETED:
                raise ValueError("expected report requires completed multi-agent status")
            if self.expected_diagnostic_status is not TaskStatus.COMPLETED:
                raise ValueError("expected report requires completed diagnostic status")
            if self.expected_safety_outcome is not SafetyReviewOutcome.APPROVED:
                raise ValueError("expected report requires approved safety review")
            if not evidence_claims:
                raise ValueError("expected report requires at least one evidence claim")

        if self.expected_multi_status is MultiAgentStatus.COMPLETED:
            if not self.expect_report:
                raise ValueError("completed multi-agent status must expect a report")
            if failure_kinds:
                raise ValueError("completed benchmark case cannot expect failures")
        elif self.expect_report:
            raise ValueError("safe-stopped benchmark case cannot expect a report")

        object.__setattr__(self, "expected_tool_sequence", tool_sequence)
        object.__setattr__(self, "expected_evidence_claims", evidence_claims)
        object.__setattr__(self, "expected_failure_kinds", failure_kinds)


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """Correctness, safety, and resource measurements for one benchmark run."""

    status_correct: bool
    tool_sequence_correct: bool
    evidence_precision: float
    evidence_recall: float
    evidence_grounding_correct: bool
    safety_outcome_correct: bool
    report_outcome_correct: bool
    failure_signature_correct: bool
    tool_call_count: int
    handoff_count: int
    collaboration_failure_count: int
    tool_budget_met: bool
    handoff_budget_met: bool

    def __post_init__(self) -> None:
        for field_name in (
            "status_correct",
            "tool_sequence_correct",
            "evidence_grounding_correct",
            "safety_outcome_correct",
            "report_outcome_correct",
            "failure_signature_correct",
            "tool_budget_met",
            "handoff_budget_met",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        _require_score(self.evidence_precision, "evidence_precision")
        _require_score(self.evidence_recall, "evidence_recall")
        for field_name in (
            "tool_call_count",
            "handoff_count",
            "collaboration_failure_count",
        ):
            _require_non_negative_int(getattr(self, field_name), field_name)

    @property
    def passed(self) -> bool:
        """Return true only when correctness, safety, and budgets all pass."""
        return all(
            (
                self.status_correct,
                self.tool_sequence_correct,
                self.evidence_precision == 1.0,
                self.evidence_recall == 1.0,
                self.evidence_grounding_correct,
                self.safety_outcome_correct,
                self.report_outcome_correct,
                self.failure_signature_correct,
                self.tool_budget_met,
                self.handoff_budget_met,
            )
        )
