"""Stable text exports for UI presentation models."""

from dataclasses import asdict
import csv
from io import StringIO
import json

from agentic_manufacturing_incident_lab.presentation.models import (
    BenchmarkPresentation,
    CasePresentation,
)


def case_json(view: CasePresentation) -> str:
    """Serialize one investigation view without framework-specific objects."""
    return json.dumps(asdict(view), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def benchmark_json(view: BenchmarkPresentation) -> str:
    """Serialize an aggregate benchmark view as deterministic JSON."""
    return json.dumps(asdict(view), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def benchmark_csv(view: BenchmarkPresentation) -> str:
    """Render one flat, spreadsheet-friendly row per benchmark case."""
    buffer = StringIO(newline="")
    fieldnames = tuple(asdict(view.rows[0])) if view.rows else ()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    if fieldnames:
        writer.writeheader()
        writer.writerows(asdict(row) for row in view.rows)
    return buffer.getvalue()


def case_report_markdown(view: CasePresentation) -> str:
    """Build a concise human-readable incident artifact from grounded output."""
    lines = [
        f"# 事件調查報告：{view.incident_id}",
        "",
        f"- Benchmark 案例：`{view.case_id}`",
        f"- 情境 Scenario：`{view.scenario_id}`（seed `{view.seed}`）",
        f"- 工作流狀態：`{view.workflow_status}`",
        f"- 診斷狀態：`{view.diagnostic_status}`",
        f"- 驗收結果：`{'PASS' if view.passed else 'FAIL'}`",
        "",
        "## 證據 Evidence",
        "",
    ]
    if view.evidence:
        for evidence in view.evidence:
            lines.extend(
                (
                    f"- **{evidence.evidence_id}** — {evidence.claim}",
                    f"  - 信心值：`{evidence.confidence:.2f}`",
                    f"  - 引用的 Observations：{evidence.observation_ids}",
                )
            )
    else:
        lines.append("本次執行沒有產生 Evidence claim。")

    lines.extend(("", "## 安全審查 Safety Review", ""))
    if view.safety is None:
        lines.append("Safety Reviewer 沒有回傳工作產物。")
    else:
        lines.extend(
            (
                f"- 審查結果：`{view.safety.outcome}`",
                f"- 審查理由：{view.safety.rationale}",
            )
        )
        lines.extend(f"- 審查發現：{finding}" for finding in view.safety.findings)

    lines.extend(("", "## 正式報告", ""))
    if view.report is None:
        lines.append("本次執行沒有產生正式報告。")
    else:
        lines.extend(
            (
                f"### {view.report.title}",
                "",
                view.report.executive_summary,
                "",
                f"**結論：** {view.report.conclusion}",
                "",
                f"**引用的 Evidence：** {view.report.evidence_ids}",
            )
        )

    lines.extend(("", "## 協作失敗 Collaboration failures", ""))
    if view.failures:
        for failure in view.failures:
            lines.append(
                f"- `{failure.failure_id}` — {failure.stage} / {failure.role} / "
                f"{failure.kind}: {failure.detail}"
            )
    else:
        lines.append("沒有記錄到 Agent 協作失敗。")
    return "\n".join(lines) + "\n"
