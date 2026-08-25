"""Execute controlled cases and score multi-agent correctness and cost."""

from dataclasses import dataclass, replace

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner
from agentic_manufacturing_incident_lab.collaboration import (
    CoordinatorAgent,
    DiagnosticAgent,
    MultiAgentRun,
    ReporterAgent,
    SafetyReviewOutcome,
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.evaluation.catalog import (
    BenchmarkCase,
    SpecialistFault,
    build_controlled_benchmark_catalog,
    build_phase7_benchmark_catalog,
)
from agentic_manufacturing_incident_lab.evaluation.contracts import (
    BenchmarkExpectation,
    BenchmarkMetrics,
)
from agentic_manufacturing_incident_lab.simulation import SimulatedEnvironment
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


class _RaisingDiagnostic:
    def handle(self, request, *, incident, known_asset_ids):
        raise RuntimeError("injected diagnostic specialist failure")


class _InvalidDiagnostic:
    def handle(self, request, *, incident, known_asset_ids):
        return None


class _RaisingSafetyReviewer:
    def handle(self, request, *, diagnostic):
        raise RuntimeError("injected safety reviewer failure")


class _RaisingReporter:
    def handle(self, request, *, diagnostic, safety_review):
        raise RuntimeError("injected reporter failure")


class _ContradictorySafetyReviewer:
    def handle(self, request, *, diagnostic):
        review = SafetyReviewerAgent().handle(request, diagnostic=diagnostic)
        return replace(
            review,
            outcome=SafetyReviewOutcome.APPROVED,
            rationale="Injected approval of an incomplete diagnostic run.",
            findings=("Contradictory approval injected by benchmark.",),
        )


def _tool_call_count(run: MultiAgentRun) -> int:
    if run.diagnostic is None:
        return 0
    return sum(
        max(1, len(record.attempts))
        for record in run.diagnostic.run.executions
    )


def _claim_scores(
    expected_claims: tuple[str, ...],
    actual_claims: tuple[str, ...],
) -> tuple[float, float]:
    expected = set(expected_claims)
    actual = set(actual_claims)
    intersection_count = len(expected & actual)
    precision = intersection_count / len(actual) if actual else 1.0
    recall = intersection_count / len(expected) if expected else 1.0
    return precision, recall


def _evidence_is_grounded(run: MultiAgentRun) -> bool:
    if run.diagnostic is None:
        return True
    diagnostic = run.diagnostic.run
    observation_ids = {
        observation.observation_id for observation in diagnostic.observations
    }
    return all(
        set(evidence.observation_ids).issubset(observation_ids)
        for evidence in diagnostic.evidence
    )


@dataclass(frozen=True, slots=True)
class BenchmarkCaseResult:
    """One benchmark execution paired with its answer key and measurements."""

    expectation: BenchmarkExpectation
    run: MultiAgentRun
    metrics: BenchmarkMetrics

    def __post_init__(self) -> None:
        if self.run.ledger.incident_id != self.expectation.incident_id:
            raise ValueError("benchmark result run must match expectation incident")
        if self.metrics.tool_call_count != _tool_call_count(self.run):
            raise ValueError("metrics tool_call_count must match the run")
        if self.metrics.handoff_count != len(self.run.ledger.handoffs):
            raise ValueError("metrics handoff_count must match the run")
        if self.metrics.collaboration_failure_count != len(self.run.failures):
            raise ValueError(
                "metrics collaboration_failure_count must match the run"
            )

    @property
    def case_id(self) -> str:
        return self.expectation.case_id

    @property
    def passed(self) -> bool:
        return self.metrics.passed


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Aggregate metrics across a non-empty set of benchmark results."""

    results: tuple[BenchmarkCaseResult, ...]

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if not results:
            raise ValueError("benchmark summary requires at least one result")
        case_ids = tuple(result.case_id for result in results)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("benchmark summary case_id values must be unique")
        object.__setattr__(self, "results", results)

    @property
    def case_count(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def failed_count(self) -> int:
        return self.case_count - self.passed_count

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.case_count

    @property
    def mean_evidence_precision(self) -> float:
        return sum(
            result.metrics.evidence_precision for result in self.results
        ) / self.case_count

    @property
    def mean_evidence_recall(self) -> float:
        return sum(
            result.metrics.evidence_recall for result in self.results
        ) / self.case_count

    @property
    def total_tool_calls(self) -> int:
        return sum(result.metrics.tool_call_count for result in self.results)

    @property
    def total_handoffs(self) -> int:
        return sum(result.metrics.handoff_count for result in self.results)

    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0


def evaluate_benchmark_run(
    expectation: BenchmarkExpectation,
    run: MultiAgentRun,
) -> BenchmarkCaseResult:
    """Compare one actual multi-agent run with a controlled answer key."""
    if run.ledger.incident_id != expectation.incident_id:
        raise ValueError("benchmark run must match expectation incident")

    diagnostic = run.diagnostic.run if run.diagnostic is not None else None
    actual_diagnostic_status = (
        diagnostic.final_state.status if diagnostic is not None else None
    )
    actual_tool_sequence = (
        tuple(record.action.tool_name for record in diagnostic.executions)
        if diagnostic is not None
        else ()
    )
    actual_evidence_claims = (
        tuple(evidence.claim for evidence in diagnostic.evidence)
        if diagnostic is not None
        else ()
    )
    evidence_precision, evidence_recall = _claim_scores(
        expectation.expected_evidence_claims,
        actual_evidence_claims,
    )
    actual_safety_outcome = (
        run.safety_review.outcome if run.safety_review is not None else None
    )
    actual_failure_kinds = tuple(failure.kind for failure in run.failures)
    tool_call_count = _tool_call_count(run)
    handoff_count = len(run.ledger.handoffs)

    metrics = BenchmarkMetrics(
        status_correct=(
            run.status is expectation.expected_multi_status
            and actual_diagnostic_status is expectation.expected_diagnostic_status
        ),
        tool_sequence_correct=(
            actual_tool_sequence == expectation.expected_tool_sequence
        ),
        evidence_precision=evidence_precision,
        evidence_recall=evidence_recall,
        evidence_grounding_correct=_evidence_is_grounded(run),
        safety_outcome_correct=(
            actual_safety_outcome is expectation.expected_safety_outcome
        ),
        report_outcome_correct=(
            (run.report is not None) is expectation.expect_report
        ),
        failure_signature_correct=(
            actual_failure_kinds == expectation.expected_failure_kinds
        ),
        tool_call_count=tool_call_count,
        handoff_count=handoff_count,
        collaboration_failure_count=len(run.failures),
        tool_budget_met=tool_call_count <= expectation.max_tool_calls,
        handoff_budget_met=handoff_count <= expectation.max_handoffs,
    )
    return BenchmarkCaseResult(
        expectation=expectation,
        run=run,
        metrics=metrics,
    )


def run_benchmark_case(case: BenchmarkCase) -> BenchmarkCaseResult:
    """Execute one case without exposing hidden scenario truth to specialists."""
    environment = SimulatedEnvironment(case.scenario)
    brief = environment.brief
    diagnostic = DiagnosticAgent(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
        action_limit=case.action_limit,
    )
    safety_reviewer = SafetyReviewerAgent()
    reporter = ReporterAgent()
    if case.specialist_fault is SpecialistFault.DIAGNOSTIC_ERROR:
        diagnostic = _RaisingDiagnostic()
    elif case.specialist_fault is SpecialistFault.DIAGNOSTIC_INVALID_RESPONSE:
        diagnostic = _InvalidDiagnostic()
    elif case.specialist_fault is SpecialistFault.SAFETY_REVIEWER_ERROR:
        safety_reviewer = _RaisingSafetyReviewer()
    elif case.specialist_fault is SpecialistFault.REPORTER_ERROR:
        reporter = _RaisingReporter()
    elif case.specialist_fault is SpecialistFault.CONTRADICTORY_APPROVAL:
        safety_reviewer = _ContradictorySafetyReviewer()

    run = CoordinatorAgent(
        diagnostic=diagnostic,
        safety_reviewer=safety_reviewer,
        reporter=reporter,
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    return evaluate_benchmark_run(case.expectation, run)


def run_controlled_benchmark(
    cases: tuple[BenchmarkCase, ...] | None = None,
) -> BenchmarkSummary:
    """Execute the default catalog or a caller-provided non-empty case subset."""
    selected_cases = (
        build_controlled_benchmark_catalog() if cases is None else tuple(cases)
    )
    if not selected_cases:
        raise ValueError("controlled benchmark requires at least one case")
    case_ids = tuple(case.case_id for case in selected_cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("controlled benchmark case_id values must be unique")
    return BenchmarkSummary(
        results=tuple(run_benchmark_case(case) for case in selected_cases)
    )


def run_phase7_benchmark() -> BenchmarkSummary:
    """Execute all controlled behavior and specialist failure cases."""
    return run_controlled_benchmark(build_phase7_benchmark_catalog())
