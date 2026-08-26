from agentic_manufacturing_incident_lab.evaluation import (
    render_benchmark_summary,
    render_benchmark_trace,
    run_phase7_benchmark,
)


def result_by_id(case_id: str):
    summary = run_phase7_benchmark()
    return next(result for result in summary.results if result.case_id == case_id)


def test_summary_renders_all_cases_and_aggregate_metrics() -> None:
    rendered = render_benchmark_summary(run_phase7_benchmark())

    assert "Case" in rendered
    assert "Workflow" in rendered
    assert "isolated-station-seed-42" in rendered
    assert "diagnostic-exception-seed-43" in rendered
    assert "contradictory-approval-seed-43" in rendered
    assert "- cases: 11" in rendered
    assert "- passed: 11" in rendered
    assert "- physical tool calls: 21" in rendered
    assert "- coordination handoffs: 44" in rendered
    assert "- all passed: yes" in rendered


def test_completed_trace_contains_actions_evidence_review_and_report() -> None:
    rendered = render_benchmark_trace(
        result_by_id("isolated-station-seed-43")
    )

    assert "Handoffs:" in rendered
    assert "coordinator -> diagnostic | investigation_request" in rendered
    assert "Diagnostic actions and physical attempts:" in rendered
    assert "check_connectivity({'asset_id': 'ST-02'})" in rendered
    assert "attempt 1: succeeded" in rendered
    assert "Evidence:" in rendered
    assert "The observed connectivity failure is isolated to ST-02." in rendered
    assert "- outcome: approved" in rendered
    assert "- report_id: RPT-INC-CONNECTIVITY-0043" in rendered
    assert "- passed: yes" in rendered


def test_diagnostic_failure_trace_explains_missing_products() -> None:
    rendered = render_benchmark_trace(
        result_by_id("diagnostic-exception-seed-43")
    )

    assert "- none: DiagnosticAgent returned no work product." in rendered
    assert "Evidence:\n- none" in rendered
    assert "Safety review:\n- none" in rendered
    assert "Report:\n- none" in rendered
    assert "stage: diagnostic" in rendered
    assert "kind: specialist_error" in rendered
    assert "physical tool calls: 0" in rendered
    assert "coordination handoffs: 1" in rendered


def test_reporter_failure_trace_preserves_approved_review_and_failure() -> None:
    rendered = render_benchmark_trace(
        result_by_id("reporter-exception-seed-43")
    )

    assert "- outcome: approved" in rendered
    assert "Report:\n- none" in rendered
    assert "stage: reporting" in rendered
    assert "role: reporter" in rendered
    assert "kind: specialist_error" in rendered
    assert "coordination handoffs: 5" in rendered


def test_rendering_is_deterministic() -> None:
    summary = run_phase7_benchmark()

    assert render_benchmark_summary(summary) == render_benchmark_summary(summary)
    assert render_benchmark_trace(summary.results[0]) == render_benchmark_trace(
        summary.results[0]
    )
