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
from agentic_manufacturing_incident_lab.presentation.localization import (
    localize_benchmark_summary,
    localize_text,
    localize_trace,
)


def _case_metrics(result: BenchmarkCaseResult) -> tuple[MetricCard, ...]:
    metrics = result.metrics
    return (
        MetricCard(
            label="工作流 Workflow",
            value=result.run.status.value,
            help_text="多 Agent 協作流程的最終狀態。",
        ),
        MetricCard(
            label="診斷狀態 Diagnostic",
            value=(
                result.run.diagnostic.run.final_state.status.value
                if result.run.diagnostic is not None
                else "none"
            ),
            help_text="Diagnostic Agent 回傳的最終狀態。",
        ),
        MetricCard(
            label="實際呼叫 Physical calls",
            value=str(metrics.tool_call_count),
            help_text="工具實際執行次數，包含重試。",
        ),
        MetricCard(
            label="交接次數 Handoffs",
            value=str(metrics.handoff_count),
            help_text="跨越 Agent 責任邊界的結構化訊息數量。",
        ),
        MetricCard(
            label="證據精確率 Precision",
            value=f"{metrics.evidence_precision:.3f}",
            help_text="產生的主張中，符合預期答案的比例。",
        ),
        MetricCard(
            label="證據召回率 Recall",
            value=f"{metrics.evidence_recall:.3f}",
            help_text="預期主張中，被診斷流程成功找出的比例。",
        ),
        MetricCard(
            label="基準結果 Benchmark",
            value="PASS" if result.passed else "FAIL",
            help_text="正確性、安全性與資源限制的綜合驗收結果。",
        ),
    )


def _handoffs(result: BenchmarkCaseResult) -> tuple[HandoffView, ...]:
    return tuple(
        HandoffView(
            sequence=index,
            sender=handoff.sender.value,
            recipient=handoff.recipient.value,
            kind=handoff.kind.value,
            purpose=localize_text(handoff.purpose),
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
            f"{localize_text(observation.summary)} values={dict(observation.values)}"
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
                    rationale=localize_text(record.action.rationale),
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
                    rationale=localize_text(record.action.rationale),
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
            claim=localize_text(evidence.claim),
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
        rationale=localize_text(result.run.safety_review.rationale),
        findings=tuple(
            localize_text(finding) for finding in result.run.safety_review.findings
        ),
    )


def _report(result: BenchmarkCaseResult) -> ReportView | None:
    if result.run.report is None:
        return None
    report = result.run.report.report
    return ReportView(
        report_id=report.report_id,
        title=localize_text(report.title),
        executive_summary=localize_text(report.executive_summary),
        conclusion=localize_text(report.conclusion),
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
            detail=localize_text(failure.detail),
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
        trace_text=localize_trace(render_benchmark_trace(result)),
    )


def build_benchmark_presentation(
    summary: BenchmarkSummary,
) -> BenchmarkPresentation:
    """Build dashboard cards and rows from aggregate benchmark output."""
    metrics = (
        MetricCard("案例數 Cases", str(summary.case_count), "受控案例總數。"),
        MetricCard("通過 Passed", str(summary.passed_count), "通過所有閘門的案例數。"),
        MetricCard("通過率 Pass rate", f"{summary.pass_rate:.3f}", "通過案例數／總案例數。"),
        MetricCard(
            "平均精確率 Mean precision",
            f"{summary.mean_evidence_precision:.3f}",
            "所有案例的 Evidence precision 巨觀平均。",
        ),
        MetricCard(
            "平均召回率 Mean recall",
            f"{summary.mean_evidence_recall:.3f}",
            "所有案例的 Evidence recall 巨觀平均。",
        ),
        MetricCard(
            "實際呼叫 Physical calls",
            str(summary.total_tool_calls),
            "所有案例的工具實際執行次數。",
        ),
        MetricCard(
            "交接次數 Handoffs",
            str(summary.total_handoffs),
            "所有案例的結構化 Agent 交接數量。",
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
        summary_text=localize_benchmark_summary(render_benchmark_summary(summary)),
    )
