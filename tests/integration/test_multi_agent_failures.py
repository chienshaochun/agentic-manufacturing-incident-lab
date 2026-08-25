from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner
from agentic_manufacturing_incident_lab.collaboration import (
    AgentRole,
    CollaborationFailureKind,
    CollaborationStage,
    CoordinatorAgent,
    DiagnosticAgent,
    MultiAgentStatus,
    ReporterAgent,
    SafetyReviewOutcome,
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.runtime import RetryPolicy
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    ConnectivityTool,
    FaultInjectingTool,
    InjectedFault,
    TelemetryTool,
    ToolRegistry,
    build_diagnostic_registry,
)


class RaisingDiagnostic:
    def handle(self, request, *, incident, known_asset_ids):
        raise RuntimeError("diagnostic service unavailable")


class InvalidDiagnostic:
    def handle(self, request, *, incident, known_asset_ids):
        return None


class RaisingSafetyReviewer:
    def handle(self, request, *, diagnostic):
        raise RuntimeError("safety reviewer unavailable")


class ContradictorySafetyReviewer:
    def handle(self, request, *, diagnostic):
        review = SafetyReviewerAgent().handle(request, diagnostic=diagnostic)
        return replace(
            review,
            outcome=SafetyReviewOutcome.APPROVED,
            rationale="Approved despite an incomplete diagnostic run.",
            findings=("Contradictory approval injected for testing.",),
        )


class RaisingReporter:
    def handle(self, request, *, diagnostic, safety_review):
        raise RuntimeError("reporter unavailable")


def make_environment():
    return SimulatedEnvironment(build_station_connectivity_scenario(seed=43))


def make_diagnostic(environment, *, fail_permanently=False):
    registry = build_diagnostic_registry(environment)
    retry_policy = None
    if fail_permanently:
        registry = ToolRegistry(
            (
                FaultInjectingTool(
                    ConnectivityTool(environment),
                    (InjectedFault.PERMANENT,),
                ),
                TelemetryTool(environment),
            )
        )
        retry_policy = RetryPolicy(max_attempts=1)
    return DiagnosticAgent(
        policy=RuleBasedPlanner(),
        registry=registry,
        retry_policy=retry_policy,
    )


def run_with(*, diagnostic, safety_reviewer, reporter):
    environment = make_environment()
    brief = environment.brief
    result = CoordinatorAgent(
        diagnostic=diagnostic(environment) if callable(diagnostic) else diagnostic,
        safety_reviewer=safety_reviewer,
        reporter=reporter,
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    return result


def test_diagnostic_exception_becomes_auditable_safe_stop() -> None:
    result = run_with(
        diagnostic=RaisingDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.diagnostic is None
    assert result.safety_review is None
    assert result.report is None
    assert len(result.ledger.handoffs) == 1
    assert result.ledger.pending_requests == result.ledger.handoffs
    failure = result.failures[0]
    assert failure.stage is CollaborationStage.DIAGNOSTIC
    assert failure.role is AgentRole.DIAGNOSTIC
    assert failure.kind is CollaborationFailureKind.SPECIALIST_ERROR
    assert "RuntimeError: diagnostic service unavailable" == failure.detail


def test_invalid_diagnostic_response_becomes_safe_stop() -> None:
    result = run_with(
        diagnostic=InvalidDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.failures[0].kind is CollaborationFailureKind.INVALID_RESPONSE
    assert result.failures[0].related_request_id == result.ledger.handoffs[0].handoff_id


def test_safety_reviewer_exception_preserves_diagnostic_result() -> None:
    result = run_with(
        diagnostic=make_diagnostic,
        safety_reviewer=RaisingSafetyReviewer(),
        reporter=ReporterAgent(),
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.diagnostic is not None
    assert result.safety_review is None
    assert result.report is None
    assert len(result.ledger.handoffs) == 3
    assert result.ledger.pending_requests == (result.ledger.handoffs[-1],)
    assert result.failures[0].stage is CollaborationStage.SAFETY_REVIEW


def test_reporter_exception_preserves_approved_review() -> None:
    result = run_with(
        diagnostic=make_diagnostic,
        safety_reviewer=SafetyReviewerAgent(),
        reporter=RaisingReporter(),
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.diagnostic is not None
    assert result.safety_review is not None
    assert result.safety_review.outcome is SafetyReviewOutcome.APPROVED
    assert result.report is None
    assert len(result.ledger.handoffs) == 5
    assert result.ledger.pending_requests == (result.ledger.handoffs[-1],)
    assert result.failures[0].stage is CollaborationStage.REPORTING


def test_contradictory_approval_is_classified_and_stopped() -> None:
    result = run_with(
        diagnostic=lambda environment: make_diagnostic(
            environment,
            fail_permanently=True,
        ),
        safety_reviewer=ContradictorySafetyReviewer(),
        reporter=ReporterAgent(),
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.safety_review is not None
    assert result.safety_review.outcome is SafetyReviewOutcome.APPROVED
    assert result.report is None
    assert result.ledger.pending_requests == ()
    assert result.failures[0].kind is CollaborationFailureKind.CONFLICTING_RESULT


def test_failure_replay_is_deterministic() -> None:
    first = run_with(
        diagnostic=RaisingDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )
    second = run_with(
        diagnostic=RaisingDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )

    assert first == second


def test_pending_request_requires_a_failure_record() -> None:
    result = run_with(
        diagnostic=RaisingDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )

    with pytest.raises(ValueError, match="pending requests must be explained"):
        replace(result, failures=())


def test_failure_must_reference_a_known_request() -> None:
    environment = make_environment()
    brief = environment.brief
    result = CoordinatorAgent(
        diagnostic=make_diagnostic(environment, fail_permanently=True),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    failed_diagnostic = run_with(
        diagnostic=RaisingDiagnostic(),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )
    unknown_request = replace(
        failed_diagnostic.failures[0],
        related_request_id="HND-UNKNOWN",
    )

    with pytest.raises(ValueError, match="must reference a ledger request"):
        replace(result, failures=(unknown_request,))
