from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.collaboration import (
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkCaseResult,
    BenchmarkSummary,
    build_controlled_benchmark_catalog,
    evaluate_benchmark_run,
    run_benchmark_case,
    run_controlled_benchmark,
)


def result_by_id(summary: BenchmarkSummary, case_id: str) -> BenchmarkCaseResult:
    return next(result for result in summary.results if result.case_id == case_id)


def test_default_controlled_benchmark_passes_all_six_cases() -> None:
    summary = run_controlled_benchmark()

    assert summary.case_count == 6
    assert summary.passed_count == 6
    assert summary.failed_count == 0
    assert summary.pass_rate == 1.0
    assert summary.all_passed is True
    assert all(result.passed for result in summary.results)


def test_summary_reports_evidence_and_resource_aggregates() -> None:
    summary = run_controlled_benchmark()

    assert summary.mean_evidence_precision == 1.0
    assert summary.mean_evidence_recall == 1.0
    assert summary.total_tool_calls == 14
    assert summary.total_handoffs == 30


def test_completed_case_has_exact_correctness_and_cost_metrics() -> None:
    result = run_benchmark_case(build_controlled_benchmark_catalog()[1])
    metrics = result.metrics

    assert result.case_id == "isolated-station-seed-43"
    assert result.run.status is MultiAgentStatus.COMPLETED
    assert metrics.status_correct is True
    assert metrics.tool_sequence_correct is True
    assert metrics.evidence_precision == 1.0
    assert metrics.evidence_recall == 1.0
    assert metrics.evidence_grounding_correct is True
    assert metrics.safety_outcome_correct is True
    assert metrics.report_outcome_correct is True
    assert metrics.failure_signature_correct is True
    assert metrics.tool_call_count == 3
    assert metrics.handoff_count == 6
    assert metrics.collaboration_failure_count == 0
    assert metrics.tool_budget_met is True
    assert metrics.handoff_budget_met is True


def test_shared_infrastructure_case_rewards_correct_silence() -> None:
    summary = run_controlled_benchmark()
    result = result_by_id(summary, "shared-infrastructure-seed-73")

    assert result.run.status is MultiAgentStatus.SAFE_STOPPED
    assert result.run.safety_review is not None
    assert (
        result.run.safety_review.outcome
        is SafetyReviewOutcome.REQUIRES_ATTENTION
    )
    assert result.run.diagnostic is not None
    assert result.run.diagnostic.run.evidence == ()
    assert result.metrics.evidence_precision == 1.0
    assert result.metrics.evidence_recall == 1.0
    assert result.metrics.report_outcome_correct is True
    assert result.passed is True


def test_actual_wrong_claim_lowers_precision_and_recall() -> None:
    case = build_controlled_benchmark_catalog()[0]
    result = run_benchmark_case(case)
    wrong_expectation = replace(
        case.expectation,
        expected_evidence_claims=("A different expected conclusion.",),
    )

    rescored = evaluate_benchmark_run(wrong_expectation, result.run)

    assert rescored.metrics.evidence_precision == 0.0
    assert rescored.metrics.evidence_recall == 0.0
    assert rescored.passed is False


def test_tighter_expectation_detects_tool_and_handoff_budget_overrun() -> None:
    cases = build_controlled_benchmark_catalog()
    normal = run_benchmark_case(cases[1])
    budget_expectation = cases[-1].expectation

    rescored = evaluate_benchmark_run(budget_expectation, normal.run)

    assert rescored.metrics.tool_call_count == 3
    assert rescored.metrics.tool_budget_met is False
    assert rescored.metrics.handoff_count == 6
    assert rescored.metrics.handoff_budget_met is False
    assert rescored.passed is False


def test_custom_case_subset_runs_without_default_catalog() -> None:
    cases = build_controlled_benchmark_catalog()
    summary = run_controlled_benchmark((cases[3], cases[4]))

    assert tuple(result.case_id for result in summary.results) == (
        "shared-infrastructure-seed-73",
        "telemetry-path-seed-91",
    )
    assert summary.case_count == 2
    assert summary.all_passed is True


def test_controlled_benchmark_replay_is_deterministic() -> None:
    assert run_controlled_benchmark() == run_controlled_benchmark()


def test_runner_rejects_empty_or_duplicate_case_selection() -> None:
    case = build_controlled_benchmark_catalog()[0]

    with pytest.raises(ValueError, match="at least one case"):
        run_controlled_benchmark(())
    with pytest.raises(ValueError, match="case_id values must be unique"):
        run_controlled_benchmark((case, case))


def test_evaluator_rejects_different_incident() -> None:
    cases = build_controlled_benchmark_catalog()
    run = run_benchmark_case(cases[0]).run

    with pytest.raises(ValueError, match="must match expectation incident"):
        evaluate_benchmark_run(cases[1].expectation, run)


def test_case_result_rejects_metrics_not_derived_from_run() -> None:
    result = run_benchmark_case(build_controlled_benchmark_catalog()[0])

    with pytest.raises(ValueError, match="tool_call_count must match"):
        replace(
            result,
            metrics=replace(result.metrics, tool_call_count=999),
        )


def test_summary_rejects_empty_or_duplicate_results() -> None:
    result = run_benchmark_case(build_controlled_benchmark_catalog()[0])

    with pytest.raises(ValueError, match="at least one result"):
        BenchmarkSummary(results=())
    with pytest.raises(ValueError, match="case_id values must be unique"):
        BenchmarkSummary(results=(result, result))
