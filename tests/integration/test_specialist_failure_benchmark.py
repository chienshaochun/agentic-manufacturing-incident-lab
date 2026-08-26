from agentic_manufacturing_incident_lab.collaboration import (
    CollaborationFailureKind,
    CollaborationStage,
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkSummary,
    build_phase7_benchmark_catalog,
    build_specialist_failure_catalog,
    run_controlled_benchmark,
    run_phase7_benchmark,
)


def result_by_id(summary: BenchmarkSummary, case_id: str):
    return next(result for result in summary.results if result.case_id == case_id)


def test_specialist_failure_catalog_has_five_unique_fault_profiles() -> None:
    cases = build_specialist_failure_catalog()

    assert len(cases) == 5
    assert len({case.case_id for case in cases}) == 5
    assert len({case.specialist_fault for case in cases}) == 5


def test_all_specialist_failure_cases_pass_expected_safe_stops() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())

    assert summary.case_count == 5
    assert summary.passed_count == 5
    assert summary.all_passed is True
    assert summary.total_tool_calls == 7
    assert summary.total_handoffs == 14


def test_diagnostic_exception_stops_before_any_tool_or_response() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())
    result = result_by_id(summary, "diagnostic-exception-seed-43")

    assert result.run.status is MultiAgentStatus.SAFE_STOPPED
    assert result.run.diagnostic is None
    assert result.run.safety_review is None
    assert result.run.report is None
    assert result.metrics.tool_call_count == 0
    assert result.metrics.handoff_count == 1
    assert result.run.failures[0].stage is CollaborationStage.DIAGNOSTIC
    assert (
        result.run.failures[0].kind
        is CollaborationFailureKind.SPECIALIST_ERROR
    )


def test_invalid_diagnostic_response_is_classified_separately() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())
    result = result_by_id(summary, "diagnostic-invalid-response-seed-43")

    assert result.run.diagnostic is None
    assert result.metrics.tool_call_count == 0
    assert result.metrics.handoff_count == 1
    assert (
        result.run.failures[0].kind
        is CollaborationFailureKind.INVALID_RESPONSE
    )


def test_safety_reviewer_exception_preserves_completed_diagnostic() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())
    result = result_by_id(summary, "safety-reviewer-exception-seed-43")

    assert result.run.diagnostic is not None
    assert result.run.safety_review is None
    assert result.run.report is None
    assert result.metrics.tool_call_count == 3
    assert result.metrics.handoff_count == 3
    assert result.run.failures[0].stage is CollaborationStage.SAFETY_REVIEW


def test_reporter_exception_preserves_diagnostic_and_approved_review() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())
    result = result_by_id(summary, "reporter-exception-seed-43")

    assert result.run.diagnostic is not None
    assert result.run.safety_review is not None
    assert result.run.safety_review.outcome is SafetyReviewOutcome.APPROVED
    assert result.run.report is None
    assert result.metrics.tool_call_count == 3
    assert result.metrics.handoff_count == 5
    assert result.run.failures[0].stage is CollaborationStage.REPORTING


def test_contradictory_approval_is_detected_before_report_request() -> None:
    summary = run_controlled_benchmark(build_specialist_failure_catalog())
    result = result_by_id(summary, "contradictory-approval-seed-43")

    assert result.run.diagnostic is not None
    assert result.run.safety_review is not None
    assert result.run.safety_review.outcome is SafetyReviewOutcome.APPROVED
    assert result.run.report is None
    assert result.metrics.tool_call_count == 1
    assert result.metrics.handoff_count == 4
    assert (
        result.run.failures[0].kind
        is CollaborationFailureKind.CONFLICTING_RESULT
    )


def test_full_phase7_catalog_and_runner_cover_all_eleven_cases() -> None:
    cases = build_phase7_benchmark_catalog()
    summary = run_phase7_benchmark()

    assert len(cases) == 11
    assert summary.case_count == 11
    assert summary.passed_count == 11
    assert summary.mean_evidence_precision == 1.0
    assert summary.mean_evidence_recall == 1.0
    assert summary.total_tool_calls == 21
    assert summary.total_handoffs == 44
    assert summary.all_passed is True


def test_failure_benchmark_replay_is_deterministic() -> None:
    cases = build_specialist_failure_catalog()

    assert run_controlled_benchmark(cases) == run_controlled_benchmark(cases)
