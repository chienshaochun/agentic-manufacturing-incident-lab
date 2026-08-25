"""Deterministic text rendering for benchmark summaries and audit traces."""

from agentic_manufacturing_incident_lab.evaluation.runner import (
    BenchmarkCaseResult,
    BenchmarkSummary,
)


def _table(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    widths = tuple(
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    )

    def format_row(row: tuple[str, ...]) -> str:
        return " | ".join(
            value.ljust(widths[index]) for index, value in enumerate(row)
        )

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join((format_row(headers), separator, *(format_row(row) for row in rows)))


def render_benchmark_summary(summary: BenchmarkSummary) -> str:
    """Render one compact result table followed by aggregate measurements."""
    headers = (
        "Case",
        "Workflow",
        "Diagnostic",
        "Precision",
        "Recall",
        "Calls",
        "Handoffs",
        "Failure",
        "Pass",
    )
    rows = tuple(
        (
            result.case_id,
            result.run.status.value,
            result.run.diagnostic.run.final_state.status.value
            if result.run.diagnostic is not None
            else "none",
            f"{result.metrics.evidence_precision:.2f}",
            f"{result.metrics.evidence_recall:.2f}",
            str(result.metrics.tool_call_count),
            str(result.metrics.handoff_count),
            ",".join(failure.kind.value for failure in result.run.failures)
            or "none",
            "yes" if result.passed else "no",
        )
        for result in summary.results
    )
    aggregate = (
        "Aggregate\n"
        f"- cases: {summary.case_count}\n"
        f"- passed: {summary.passed_count}\n"
        f"- failed: {summary.failed_count}\n"
        f"- pass rate: {summary.pass_rate:.3f}\n"
        f"- mean evidence precision: {summary.mean_evidence_precision:.3f}\n"
        f"- mean evidence recall: {summary.mean_evidence_recall:.3f}\n"
        f"- physical tool calls: {summary.total_tool_calls}\n"
        f"- coordination handoffs: {summary.total_handoffs}\n"
        f"- all passed: {'yes' if summary.all_passed else 'no'}"
    )
    return f"{_table(headers, rows)}\n\n{aggregate}"


def render_benchmark_trace(result: BenchmarkCaseResult) -> str:
    """Render the full observable record for one benchmark case."""
    expectation = result.expectation
    run = result.run
    lines = [
        f"Benchmark trace: {result.case_id}",
        f"Incident: {expectation.incident_id}",
        f"Scenario: {expectation.scenario_id} | seed={expectation.seed}",
        f"Workflow status: {run.status.value}",
        "",
        "Handoffs:",
    ]
    for index, handoff in enumerate(run.ledger.handoffs, start=1):
        reply = f" | reply_to={handoff.in_reply_to}" if handoff.in_reply_to else ""
        lines.extend(
            (
                f"{index}. {handoff.sender.value} -> {handoff.recipient.value} "
                f"| {handoff.kind.value}{reply}",
                f"   purpose: {handoff.purpose}",
            )
        )

    lines.extend(("", "Diagnostic actions and physical attempts:"))
    diagnostic = run.diagnostic.run if run.diagnostic is not None else None
    if diagnostic is None:
        lines.append("- none: DiagnosticAgent returned no work product.")
    else:
        for index, record in enumerate(diagnostic.executions, start=1):
            action = record.action
            lines.append(
                f"{index}. {action.action_id} | {action.tool_name}"
                f"({dict(action.parameters)}) | risk={action.risk.value}"
            )
            lines.append(f"   rationale: {action.rationale}")
            if not record.attempts:
                lines.append("   attempts: legacy record has no attempt detail")
            for attempt in record.attempts:
                error = f" | error={attempt.error_code}" if attempt.error_code else ""
                lines.append(
                    f"   attempt {attempt.attempt_number}: "
                    f"{attempt.status.value}{error}"
                )
            for observation in record.observations:
                lines.append(
                    f"   observe {observation.observation_id}: "
                    f"{observation.summary} values={dict(observation.values)}"
                )

    lines.extend(("", "Evidence:"))
    if diagnostic is None or not diagnostic.evidence:
        lines.append("- none")
    else:
        for evidence in diagnostic.evidence:
            lines.extend(
                (
                    f"- {evidence.evidence_id}: {evidence.claim}",
                    f"  confidence: {evidence.confidence:.2f}",
                    "  observations: " + ", ".join(evidence.observation_ids),
                )
            )

    lines.extend(("", "Safety review:"))
    if run.safety_review is None:
        lines.append("- none")
    else:
        lines.extend(
            (
                f"- outcome: {run.safety_review.outcome.value}",
                f"- rationale: {run.safety_review.rationale}",
            )
        )
        for finding in run.safety_review.findings:
            lines.append(f"- finding: {finding}")

    lines.extend(("", "Report:"))
    if run.report is None:
        lines.append("- none")
    else:
        report = run.report.report
        lines.extend(
            (
                f"- report_id: {report.report_id}",
                f"- summary: {report.executive_summary}",
                f"- conclusion: {report.conclusion}",
                "- evidence: " + ", ".join(report.evidence_ids),
            )
        )

    lines.extend(("", "Collaboration failures:"))
    if not run.failures:
        lines.append("- none")
    else:
        for failure in run.failures:
            lines.extend(
                (
                    f"- {failure.failure_id}",
                    f"  stage: {failure.stage.value}",
                    f"  role: {failure.role.value}",
                    f"  kind: {failure.kind.value}",
                    f"  request: {failure.related_request_id}",
                    f"  detail: {failure.detail}",
                )
            )

    metrics = result.metrics
    lines.extend(
        (
            "",
            "Evaluation:",
            f"- status correct: {'yes' if metrics.status_correct else 'no'}",
            f"- tool sequence correct: {'yes' if metrics.tool_sequence_correct else 'no'}",
            f"- evidence precision: {metrics.evidence_precision:.3f}",
            f"- evidence recall: {metrics.evidence_recall:.3f}",
            "- evidence grounding correct: "
            f"{'yes' if metrics.evidence_grounding_correct else 'no'}",
            f"- safety outcome correct: {'yes' if metrics.safety_outcome_correct else 'no'}",
            f"- report outcome correct: {'yes' if metrics.report_outcome_correct else 'no'}",
            "- failure signature correct: "
            f"{'yes' if metrics.failure_signature_correct else 'no'}",
            f"- physical tool calls: {metrics.tool_call_count}",
            f"- coordination handoffs: {metrics.handoff_count}",
            f"- passed: {'yes' if result.passed else 'no'}",
        )
    )
    return "\n".join(lines)
