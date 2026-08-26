"""Convert evaluation products into framework-independent presentation data."""

from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkCaseResult,
    BenchmarkSummary,
    render_benchmark_summary,
    render_benchmark_trace,
)
from agentic_manufacturing_incident_lab.presentation.models import (
    ActionAttemptView,
    BenchmarkPresentation,
    BenchmarkRow,
    CasePresentation,
    EvidenceView,
    FailureView,
    HandoffView,
    MetricCard,
    ReportView,
    SafetyView,
)


def _case_metrics(result: BenchmarkCaseResult) -> tuple[MetricCard, ...]:
    metrics = result.metrics
    return (
        MetricCard(
            label="Workflow",
            value=result.run.status.value,
            help_text="Terminal status of the coordinated multi-agent workflow.",
        ),
        MetricCard(
            label="Diagnostic",
            value=(
                result.run.diagnostic.run.final_state.status.value
                if result.run.diagnostic is not None
                else "none"
            ),
            help_text="Terminal status returned by the Diagnostic specialist.",
        ),
        MetricCard(
            label="Physical calls",
            value=str(metrics.tool_call_count),
            help_text="Actual tool attempts, including retries.",
        ),
        MetricCard(
            label="Handoffs",
            value=str(metrics.handoff_count),
            help_text="Structured messages crossing agent responsibility boundaries.",
        ),
        MetricCard(
            label="Precision",
            value=f"{metrics.evidence_precision:.3f}",
            help_text="Expected claims divided by all claims that were produced.",
        ),
        MetricCard(
            label="Recall",
            value=f"{metrics.evidence_recall:.3f}",
            help_text="Expected claims that were found by the diagnostic path.",
        ),
        MetricCard(
            label="Benchmark",
            value="PASS" if result.passed else "FAIL",
            help_text="All correctness, safety, and resource gates combined.",
        ),
    )


def _handoffs(result: BenchmarkCaseResult) -> tuple[HandoffView, ...]:
    return tuple(
        HandoffView(
            sequence=index,
            sender=handoff.sender.value,
            recipient=handoff.recipient.value,
            kind=handoff.kind.value,
            purpose=handoff.purpose,
            reply_to=handoff.in_reply_to or "",
        )
        for index, handoff in enumerate(result.run.ledger.handoffs, start=1)
    )


def _action_attempts(result: BenchmarkCaseResult) -> tuple[ActionAttemptView, ...]:
    if result.run.diagnostic is None:
        return ()
    views: list[ActionAttemptView] = []
    for action_sequence, record in enumerate(
        result.run.diagnostic.run.executions,
        start=1,
    ):
        observation_text = " | ".join(
            f"{observation.summary} values={dict(observation.values)}"
            for observation in record.observations
        )
        if not record.attempts:
            views.append(
                ActionAttemptView(
                    action_sequence=action_sequence,
                    action_id=record.action.action_id,
                    tool=record.action.tool_name,
                    parameters=str(dict(record.action.parameters)),
                    risk=record.action.risk.value,
                    rationale=record.action.rationale,
                    attempt=None,
                    status=record.result.status.value,
                    error_code=record.result.error_code or "",
                    observations=observation_text,
                )
            )
            continue
        for attempt in record.attempts:
            views.append(
                ActionAttemptView(
                    action_sequence=action_sequence,
                    action_id=record.action.action_id,
                    tool=record.action.tool_name,
                    parameters=str(dict(record.action.parameters)),
                    risk=record.action.risk.value,
                    rationale=record.action.rationale,
                    attempt=attempt.attempt_number,
                    status=attempt.status.value,
                    error_code=attempt.error_code or "",
                    observations=observation_text
                    if attempt is record.attempts[-1]
                    else "",
                )
            )
    return tuple(views)


def _evidence(result: BenchmarkCaseResult) -> tuple[EvidenceView, ...]:
    if result.run.diagnostic is None:
        return ()
    return tuple(
        EvidenceView(
            evidence_id=evidence.evidence_id,
            claim=evidence.claim,
            confidence=evidence.confidence,
            observation_ids=", ".join(evidence.observation_ids),
        )
        for evidence in result.run.diagnostic.run.evidence
    )


def _safety(result: BenchmarkCaseResult) -> SafetyView | None:
    if result.run.safety_review is None:
        return None
    return SafetyView(
        outcome=result.run.safety_review.outcome.value,
        rationale=result.run.safety_review.rationale,
        findings=result.run.safety_review.findings,
    )


def _report(result: BenchmarkCaseResult) -> ReportView | None:
    if result.run.report is None:
        return None
    report = result.run.report.report
    return ReportView(
        report_id=report.report_id,
        title=report.title,
        executive_summary=report.executive_summary,
        conclusion=report.conclusion,
        evidence_ids=", ".join(report.evidence_ids),
    )


def _failures(result: BenchmarkCaseResult) -> tuple[FailureView, ...]:
    return tuple(
        FailureView(
            failure_id=failure.failure_id,
            stage=failure.stage.value,
            role=failure.role.value,
            kind=failure.kind.value,
            request_id=failure.related_request_id,
            detail=failure.detail,
        )
        for failure in result.run.failures
    )


def build_case_presentation(result: BenchmarkCaseResult) -> CasePresentation:
    """Build all cards and tables required by the single-case UI."""
    return CasePresentation(
        case_id=result.case_id,
        incident_id=result.expectation.incident_id,
        scenario_id=result.expectation.scenario_id,
        seed=result.expectation.seed,
        workflow_status=result.run.status.value,
        diagnostic_status=(
            result.run.diagnostic.run.final_state.status.value
            if result.run.diagnostic is not None
            else "none"
        ),
        passed=result.passed,
        metrics=_case_metrics(result),
        handoffs=_handoffs(result),
        action_attempts=_action_attempts(result),
        evidence=_evidence(result),
        safety=_safety(result),
        report=_report(result),
        failures=_failures(result),
        trace_text=render_benchmark_trace(result),
    )


def build_benchmark_presentation(
    summary: BenchmarkSummary,
) -> BenchmarkPresentation:
    """Build dashboard cards and rows from aggregate benchmark output."""
    metrics = (
        MetricCard("Cases", str(summary.case_count), "Total controlled cases."),
        MetricCard("Passed", str(summary.passed_count), "Cases passing every gate."),
        MetricCard("Pass rate", f"{summary.pass_rate:.3f}", "Passed cases / cases."),
        MetricCard(
            "Mean precision",
            f"{summary.mean_evidence_precision:.3f}",
            "Macro-average evidence precision.",
        ),
        MetricCard(
            "Mean recall",
            f"{summary.mean_evidence_recall:.3f}",
            "Macro-average evidence recall.",
        ),
        MetricCard(
            "Physical calls",
            str(summary.total_tool_calls),
            "All physical tool attempts across cases.",
        ),
        MetricCard(
            "Handoffs",
            str(summary.total_handoffs),
            "All structured agent messages across cases.",
        ),
    )
    rows = tuple(
        BenchmarkRow(
            case=result.case_id,
            workflow=result.run.status.value,
            diagnostic=(
                result.run.diagnostic.run.final_state.status.value
                if result.run.diagnostic is not None
                else "none"
            ),
            precision=result.metrics.evidence_precision,
            recall=result.metrics.evidence_recall,
            tool_calls=result.metrics.tool_call_count,
            handoffs=result.metrics.handoff_count,
            failure=(
                ",".join(failure.kind.value for failure in result.run.failures)
                or "none"
            ),
            passed=result.passed,
        )
        for result in summary.results
    )
    return BenchmarkPresentation(
        metrics=metrics,
        rows=rows,
        summary_text=render_benchmark_summary(summary),
    )
