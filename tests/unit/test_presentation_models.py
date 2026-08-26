from dataclasses import asdict

from agentic_manufacturing_incident_lab.evaluation import (
    build_phase7_benchmark_catalog,
    run_benchmark_case,
    run_phase7_benchmark,
)
from agentic_manufacturing_incident_lab.presentation import (
    build_benchmark_presentation,
    build_case_presentation,
)


def case_result(case_id: str):
    case = next(
        case
        for case in build_phase7_benchmark_catalog()
        if case.case_id == case_id
    )
    return run_benchmark_case(case)


def test_completed_case_presentation_contains_all_ui_sections() -> None:
    view = build_case_presentation(case_result("isolated-station-seed-43"))

    assert view.case_id == "isolated-station-seed-43"
    assert view.workflow_status == "completed"
    assert view.diagnostic_status == "completed"
    assert view.passed is True
    assert len(view.metrics) == 7
    assert len(view.handoffs) == 6
    assert len(view.action_attempts) == 3
    assert len(view.evidence) == 1
    assert view.safety is not None
    assert view.safety.outcome == "approved"
    assert view.report is not None
    assert "隔離在 ST-02" in view.report.conclusion
    assert view.failures == ()


def test_action_attempt_view_separates_action_and_physical_attempt() -> None:
    view = build_case_presentation(case_result("isolated-station-seed-43"))
    first = view.action_attempts[0]

    assert first.action_sequence == 1
    assert first.tool == "check_connectivity"
    assert first.attempt == 1
    assert first.status == "succeeded"
    assert first.error_code == ""
    assert "network_reachable" in first.observations


def test_diagnostic_failure_presentation_has_failure_but_no_products() -> None:
    view = build_case_presentation(case_result("diagnostic-exception-seed-43"))

    assert view.workflow_status == "safe_stopped"
    assert view.diagnostic_status == "none"
    assert len(view.handoffs) == 1
    assert view.action_attempts == ()
    assert view.evidence == ()
    assert view.safety is None
    assert view.report is None
    assert len(view.failures) == 1
    assert view.failures[0].stage == "diagnostic"
    assert view.failures[0].kind == "specialist_error"


def test_reporter_failure_preserves_review_in_presentation() -> None:
    view = build_case_presentation(case_result("reporter-exception-seed-43"))

    assert view.safety is not None
    assert view.safety.outcome == "approved"
    assert view.report is None
    assert view.failures[0].role == "reporter"
    assert len(view.handoffs) == 5


def test_benchmark_presentation_contains_aggregate_cards_and_rows() -> None:
    view = build_benchmark_presentation(run_phase7_benchmark())

    assert tuple(card.value for card in view.metrics) == (
        "11",
        "11",
        "1.000",
        "1.000",
        "1.000",
        "21",
        "44",
    )
    assert len(view.rows) == 11
    assert all(row.passed for row in view.rows)
    assert view.rows[-1].failure == "conflicting_result"
    assert "- 是否全部通過： yes" in view.summary_text


def test_presentation_models_are_serializable_with_dataclasses_asdict() -> None:
    case_view = build_case_presentation(case_result("isolated-station-seed-43"))
    benchmark_view = build_benchmark_presentation(run_phase7_benchmark())

    case_payload = asdict(case_view)
    benchmark_payload = asdict(benchmark_view)

    assert case_payload["report"]["report_id"] == "RPT-INC-CONNECTIVITY-0043"
    assert benchmark_payload["rows"][0]["case"] == "isolated-station-seed-42"
