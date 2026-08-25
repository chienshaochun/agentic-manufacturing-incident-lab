from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner
from agentic_manufacturing_incident_lab.collaboration import (
    AgentHandoff,
    AgentRole,
    CoordinatorAgent,
    DiagnosticAgent,
    HandoffKind,
    MultiAgentRun,
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


def make_coordinator(
    environment: SimulatedEnvironment,
    *,
    registry: ToolRegistry | None = None,
    retry_policy: RetryPolicy | None = None,
) -> CoordinatorAgent:
    return CoordinatorAgent(
        diagnostic=DiagnosticAgent(
            policy=RuleBasedPlanner(),
            registry=registry or build_diagnostic_registry(environment),
            retry_policy=retry_policy,
        ),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    )


def run_workflow():
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    result = make_coordinator(environment).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    return environment, result


def test_coordinator_completes_six_handoff_specialist_workflow() -> None:
    environment, result = run_workflow()

    assert result.status is MultiAgentStatus.COMPLETED
    assert [handoff.kind for handoff in result.ledger.handoffs] == [
        HandoffKind.INVESTIGATION_REQUEST,
        HandoffKind.DIAGNOSTIC_RESULT,
        HandoffKind.SAFETY_REVIEW_REQUEST,
        HandoffKind.SAFETY_REVIEW_RESULT,
        HandoffKind.REPORT_REQUEST,
        HandoffKind.REPORT_RESULT,
    ]
    assert result.ledger.pending_requests == ()
    assert result.safety_review.outcome is SafetyReviewOutcome.APPROVED
    assert result.report is not None
    assert environment.observation_count == 3


def test_report_is_bound_to_diagnostic_actions_observations_and_evidence() -> None:
    _, result = run_workflow()
    assert result.report is not None
    report = result.report.report

    assert report.action_ids == result.diagnostic.handoff.action_ids
    assert report.observation_ids == result.diagnostic.handoff.observation_ids
    assert report.evidence_ids == tuple(
        evidence.evidence_id for evidence in result.diagnostic.run.evidence
    )
    assert report.conclusion == result.diagnostic.run.evidence[0].claim
    assert "independent safety reviewer approved" in report.executive_summary


def test_coordinator_replay_is_deterministic() -> None:
    _, first = run_workflow()
    _, second = run_workflow()

    assert first == second


def test_handoff_timestamps_move_forward_across_all_roles() -> None:
    _, result = run_workflow()
    timestamps = tuple(
        handoff.created_at for handoff in result.ledger.handoffs
    )

    assert all(
        later > earlier
        for earlier, later in zip(timestamps, timestamps[1:])
    )


def test_coordinator_stops_before_report_when_review_needs_attention() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.PERMANENT,),
    )
    registry = ToolRegistry((connectivity, TelemetryTool(environment)))
    brief = environment.brief

    result = make_coordinator(
        environment,
        registry=registry,
        retry_policy=RetryPolicy(max_attempts=1),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    assert result.status is MultiAgentStatus.SAFE_STOPPED
    assert result.safety_review.outcome is SafetyReviewOutcome.REQUIRES_ATTENTION
    assert result.report is None
    assert result.failures == ()
    assert [handoff.kind for handoff in result.ledger.handoffs] == [
        HandoffKind.INVESTIGATION_REQUEST,
        HandoffKind.DIAGNOSTIC_RESULT,
        HandoffKind.SAFETY_REVIEW_REQUEST,
        HandoffKind.SAFETY_REVIEW_RESULT,
    ]
    assert HandoffKind.REPORT_REQUEST not in {
        handoff.kind for handoff in result.ledger.handoffs
    }


def test_reporter_rejects_unapproved_safety_review() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.PERMANENT,),
    )
    registry = ToolRegistry((connectivity, TelemetryTool(environment)))
    brief = environment.brief
    stopped = make_coordinator(
        environment,
        registry=registry,
        retry_policy=RetryPolicy(max_attempts=1),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    request = AgentHandoff(
        handoff_id="HND-FORCED-REPORT",
        incident_id=brief.incident.incident_id,
        kind=HandoffKind.REPORT_REQUEST,
        sender=AgentRole.COORDINATOR,
        recipient=AgentRole.REPORTER,
        purpose="Attempt to bypass safety review.",
        created_at=stopped.safety_review.handoff.created_at.replace(
            microsecond=1
        ),
        action_ids=stopped.diagnostic.handoff.action_ids,
        observation_ids=stopped.diagnostic.handoff.observation_ids,
    )

    with pytest.raises(ValueError, match="requires an approved safety review"):
        ReporterAgent().handle(
            request,
            diagnostic=stopped.diagnostic,
            safety_review=stopped.safety_review,
        )


def test_completed_aggregate_rejects_missing_report() -> None:
    _, result = run_workflow()

    with pytest.raises(ValueError, match="requires a report"):
        MultiAgentRun(
            status=MultiAgentStatus.COMPLETED,
            ledger=result.ledger,
            diagnostic=result.diagnostic,
            safety_review=result.safety_review,
        )


def test_safe_stop_without_failure_requires_nonapproved_review() -> None:
    _, result = run_workflow()

    with pytest.raises(ValueError, match="requires a non-approved safety review"):
        MultiAgentRun(
            status=MultiAgentStatus.SAFE_STOPPED,
            ledger=result.ledger,
            diagnostic=result.diagnostic,
            safety_review=result.safety_review,
        )


def test_report_work_product_rejects_omitted_observation() -> None:
    _, result = run_workflow()
    assert result.report is not None
    incomplete_report = replace(
        result.report.report,
        observation_ids=result.report.report.observation_ids[:-1],
    )

    with pytest.raises(ValueError, match="reference every report observation"):
        replace(result.report, report=incomplete_report)


def test_reporter_rejects_approval_from_different_incident() -> None:
    _, result = run_workflow()
    assert result.report is not None
    report_request = result.ledger.handoffs[-2]
    foreign_review = replace(
        result.safety_review,
        handoff=replace(
            result.safety_review.handoff,
            incident_id="INC-OTHER",
        ),
    )

    with pytest.raises(ValueError, match="must match the diagnostic incident"):
        ReporterAgent().handle(
            report_request,
            diagnostic=result.diagnostic,
            safety_review=foreign_review,
        )
