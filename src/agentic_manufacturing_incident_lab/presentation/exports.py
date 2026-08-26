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
        f"# Investigation report: {view.incident_id}",
        "",
        f"- Benchmark case: `{view.case_id}`",
        f"- Scenario: `{view.scenario_id}` (seed `{view.seed}`)",
        f"- Workflow status: `{view.workflow_status}`",
        f"- Diagnostic status: `{view.diagnostic_status}`",
        f"- Acceptance result: `{'PASS' if view.passed else 'FAIL'}`",
        "",
        "## Evidence",
        "",
    ]
    if view.evidence:
        for evidence in view.evidence:
            lines.extend(
                (
                    f"- **{evidence.evidence_id}** — {evidence.claim}",
                    f"  - Confidence: `{evidence.confidence:.2f}`",
                    f"  - Observations: {evidence.observation_ids}",
                )
            )
    else:
        lines.append("No evidence claim was produced.")

    lines.extend(("", "## Safety review", ""))
    if view.safety is None:
        lines.append("No Safety Reviewer work product was returned.")
    else:
        lines.extend(
            (
                f"- Outcome: `{view.safety.outcome}`",
                f"- Rationale: {view.safety.rationale}",
            )
        )
        lines.extend(f"- Finding: {finding}" for finding in view.safety.findings)

    lines.extend(("", "## Formal report", ""))
    if view.report is None:
        lines.append("No formal report was generated for this run.")
    else:
        lines.extend(
            (
                f"### {view.report.title}",
                "",
                view.report.executive_summary,
                "",
                f"**Conclusion:** {view.report.conclusion}",
                "",
                f"**Evidence records:** {view.report.evidence_ids}",
            )
        )

    lines.extend(("", "## Collaboration failures", ""))
    if view.failures:
        for failure in view.failures:
            lines.append(
                f"- `{failure.failure_id}` — {failure.stage} / {failure.role} / "
                f"{failure.kind}: {failure.detail}"
            )
    else:
        lines.append("No collaboration failure was recorded.")
    return "\n".join(lines) + "\n"
