import csv
from dataclasses import replace
from io import StringIO
import json

from agentic_manufacturing_incident_lab.evaluation import (
    build_phase7_benchmark_catalog,
    run_benchmark_case,
    run_phase7_benchmark,
)
from agentic_manufacturing_incident_lab.presentation import (
    benchmark_csv,
    benchmark_json,
    build_benchmark_presentation,
    build_case_presentation,
    case_json,
    case_report_markdown,
)


def _case_view(case_id: str = "isolated-station-seed-43"):
    case = next(
        case for case in build_phase7_benchmark_catalog() if case.case_id == case_id
    )
    return build_case_presentation(run_benchmark_case(case))


def test_case_json_contains_grounded_nested_products() -> None:
    document = json.loads(case_json(_case_view()))

    assert document["case_id"] == "isolated-station-seed-43"
    assert document["safety"]["outcome"] == "approved"
    assert document["report"]["evidence_ids"]
    assert len(document["handoffs"]) == 6


def test_case_report_markdown_handles_completed_and_missing_report() -> None:
    view = _case_view()
    completed = case_report_markdown(view)
    contained = case_report_markdown(replace(view, report=None))

    assert "# 事件調查報告：INC-CONNECTIVITY-0043" in completed
    assert "## 證據 Evidence" in completed
    assert "**結論：**" in completed
    assert "本次執行沒有產生正式報告" in contained


def test_benchmark_exports_have_all_cases_and_stable_columns() -> None:
    view = build_benchmark_presentation(run_phase7_benchmark())
    document = json.loads(benchmark_json(view))
    rows = list(csv.DictReader(StringIO(benchmark_csv(view))))

    assert len(document["rows"]) == 11
    assert len(rows) == 11
    assert tuple(rows[0]) == (
        "case",
        "workflow",
        "diagnostic",
        "precision",
        "recall",
        "tool_calls",
        "handoffs",
        "failure",
        "passed",
    )
    assert all(row["passed"] == "True" for row in rows)
