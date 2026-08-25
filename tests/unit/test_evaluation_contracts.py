from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.collaboration import (
    CollaborationFailureKind,
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkExpectation,
    BenchmarkMetrics,
)


def completed_expectation() -> BenchmarkExpectation:
    return BenchmarkExpectation(
        case_id="connectivity-seed-43",
        scenario_id="station-connectivity-isolation",
        seed=43,
        incident_id="INC-CONNECTIVITY-0043",
        expected_multi_status=MultiAgentStatus.COMPLETED,
        expected_diagnostic_status=TaskStatus.COMPLETED,
        expected_tool_sequence=(
            "check_connectivity",
            "check_connectivity",
            "read_telemetry",
        ),
        expected_evidence_claims=(
            "The observed connectivity failure is isolated to ST-02.",
        ),
        expected_safety_outcome=SafetyReviewOutcome.APPROVED,
        expect_report=True,
        max_tool_calls=3,
        max_handoffs=6,
    )


def passing_metrics() -> BenchmarkMetrics:
    return BenchmarkMetrics(
        status_correct=True,
        tool_sequence_correct=True,
        evidence_precision=1.0,
        evidence_recall=1.0,
        evidence_grounding_correct=True,
        safety_outcome_correct=True,
        report_outcome_correct=True,
        failure_signature_correct=True,
        tool_call_count=3,
        handoff_count=6,
        collaboration_failure_count=0,
        tool_budget_met=True,
        handoff_budget_met=True,
    )


def test_completed_expectation_preserves_answer_key_and_limits() -> None:
    expectation = completed_expectation()

    assert expectation.expected_multi_status is MultiAgentStatus.COMPLETED
    assert expectation.expected_diagnostic_status is TaskStatus.COMPLETED
    assert expectation.expected_safety_outcome is SafetyReviewOutcome.APPROVED
    assert expectation.max_tool_calls == 3
    assert expectation.max_handoffs == 6


def test_failure_expectation_can_stop_before_diagnostic_result() -> None:
    expectation = BenchmarkExpectation(
        case_id="diagnostic-error",
        scenario_id="station-connectivity-isolation",
        seed=43,
        incident_id="INC-CONNECTIVITY-0043",
        expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
        expected_diagnostic_status=None,
        expected_tool_sequence=(),
        expected_evidence_claims=(),
        expected_safety_outcome=None,
        expect_report=False,
        expected_failure_kinds=(
            CollaborationFailureKind.SPECIALIST_ERROR,
        ),
        max_tool_calls=0,
        max_handoffs=1,
    )

    assert expectation.expected_failure_kinds == (
        CollaborationFailureKind.SPECIALIST_ERROR,
    )


@pytest.mark.parametrize("field_name", ["case_id", "scenario_id", "incident_id"])
def test_expectation_rejects_blank_identity(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        replace(completed_expectation(), **{field_name: " "})


@pytest.mark.parametrize("seed", [-1, True, 1.5])
def test_expectation_rejects_invalid_seed(seed) -> None:
    with pytest.raises(ValueError, match="seed must be a non-negative integer"):
        replace(completed_expectation(), seed=seed)


def test_expectation_rejects_tool_sequence_above_limit() -> None:
    with pytest.raises(ValueError, match="exceeds max_tool_calls"):
        replace(completed_expectation(), max_tool_calls=2)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"expected_tool_sequence": ("check_connectivity",)}, "tools or evidence"),
        ({"expected_evidence_claims": ("unsupported",)}, "tools or evidence"),
        ({"expected_safety_outcome": SafetyReviewOutcome.APPROVED}, "review or report"),
        ({"expect_report": True}, "review or report"),
    ],
)
def test_missing_diagnostic_rejects_downstream_expectations(changes, message) -> None:
    failure = BenchmarkExpectation(
        case_id="diagnostic-error",
        scenario_id="station-connectivity-isolation",
        seed=43,
        incident_id="INC-CONNECTIVITY-0043",
        expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
        expected_diagnostic_status=None,
        expected_tool_sequence=(),
        expected_evidence_claims=(),
        expected_safety_outcome=None,
        expect_report=False,
        max_tool_calls=3,
        max_handoffs=1,
    )

    with pytest.raises(ValueError, match=message):
        replace(failure, **changes)


def test_completed_expectation_requires_report() -> None:
    with pytest.raises(ValueError, match="must expect a report"):
        replace(completed_expectation(), expect_report=False)


def test_completed_expectation_rejects_failure_signature() -> None:
    with pytest.raises(ValueError, match="cannot expect failures"):
        replace(
            completed_expectation(),
            expected_failure_kinds=(CollaborationFailureKind.INVALID_RESPONSE,),
        )


def test_expected_report_requires_completed_diagnostic() -> None:
    with pytest.raises(ValueError, match="completed diagnostic status"):
        replace(
            completed_expectation(),
            expected_diagnostic_status=TaskStatus.SAFE_STOPPED,
        )


def test_expected_report_requires_approved_review() -> None:
    with pytest.raises(ValueError, match="approved safety review"):
        replace(
            completed_expectation(),
            expected_safety_outcome=SafetyReviewOutcome.REQUIRES_ATTENTION,
        )


def test_expected_report_requires_evidence() -> None:
    with pytest.raises(ValueError, match="at least one evidence claim"):
        replace(completed_expectation(), expected_evidence_claims=())


def test_passing_metrics_pass() -> None:
    assert passing_metrics().passed is True


@pytest.mark.parametrize(
    "field_name",
    [
        "status_correct",
        "tool_sequence_correct",
        "evidence_grounding_correct",
        "safety_outcome_correct",
        "report_outcome_correct",
        "failure_signature_correct",
        "tool_budget_met",
        "handoff_budget_met",
    ],
)
def test_each_failed_gate_fails_benchmark(field_name: str) -> None:
    assert replace(passing_metrics(), **{field_name: False}).passed is False


@pytest.mark.parametrize("field_name", ["evidence_precision", "evidence_recall"])
@pytest.mark.parametrize("value", [-0.01, 1.01, True, "1.0"])
def test_metrics_reject_invalid_evidence_score(field_name: str, value) -> None:
    with pytest.raises(ValueError, match=field_name):
        replace(passing_metrics(), **{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    ["tool_call_count", "handoff_count", "collaboration_failure_count"],
)
@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_metrics_reject_invalid_counts(field_name: str, value) -> None:
    with pytest.raises(ValueError, match=field_name):
        replace(passing_metrics(), **{field_name: value})


def test_imperfect_precision_or_recall_fails_benchmark() -> None:
    assert replace(passing_metrics(), evidence_precision=0.5).passed is False
    assert replace(passing_metrics(), evidence_recall=0.5).passed is False
