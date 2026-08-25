from dataclasses import replace
from datetime import timedelta

import pytest

from agentic_manufacturing_incident_lab.agent import (
    ActionDecision,
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.collaboration import (
    AgentHandoff,
    AgentRole,
    DiagnosticAgent,
    DiagnosticWorkProduct,
    HandoffKind,
    HandoffLedger,
    SafetyReviewOutcome,
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Incident,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.runtime import RetryPolicy
from agentic_manufacturing_incident_lab.safety import (
    ApprovalOutcome,
    SafetyDisposition,
)
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
    ToolResponse,
    ToolSpec,
    build_diagnostic_registry,
)


class ControlledTool:
    spec = ToolSpec(
        name="controlled_test_operation",
        description="Synthetic controlled operation that diagnostics must not own.",
        risk=ActionRisk.CONTROLLED_WRITE,
    )

    def invoke(self, action: Action) -> ToolResponse:
        return ToolResponse(summary="Controlled operation completed.")


class ControlledPolicy:
    name = "controlled_review_test"

    def decide(self, context):
        return ActionDecision(
            tool_name="controlled_test_operation",
            rationale="Propose one controlled operation for review.",
        )


def make_request(incident: Incident) -> AgentHandoff:
    return AgentHandoff(
        handoff_id=f"HND-{incident.incident_id}-INVESTIGATE",
        incident_id=incident.incident_id,
        kind=HandoffKind.INVESTIGATION_REQUEST,
        sender=AgentRole.COORDINATOR,
        recipient=AgentRole.DIAGNOSTIC,
        purpose=incident.goal,
        created_at=incident.reported_at,
    )


def make_safety_request(diagnostic: DiagnosticWorkProduct) -> AgentHandoff:
    return AgentHandoff(
        handoff_id=(
            f"HND-{diagnostic.run.incident.incident_id}-SAFETY-REVIEW"
        ),
        incident_id=diagnostic.run.incident.incident_id,
        kind=HandoffKind.SAFETY_REVIEW_REQUEST,
        sender=AgentRole.COORDINATOR,
        recipient=AgentRole.SAFETY_REVIEWER,
        purpose="Review every diagnostic action and evidence reference.",
        created_at=diagnostic.handoff.created_at + timedelta(seconds=1),
        observation_ids=diagnostic.handoff.observation_ids,
        action_ids=diagnostic.handoff.action_ids,
    )


def run_diagnostic():
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    request = make_request(brief.incident)
    diagnostic = DiagnosticAgent(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    ).handle(
        request,
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    return environment, request, diagnostic


def test_diagnostic_agent_returns_complete_referenced_work_product() -> None:
    _, request, diagnostic = run_diagnostic()

    assert diagnostic.run.final_state.status is TaskStatus.COMPLETED
    assert diagnostic.handoff.kind is HandoffKind.DIAGNOSTIC_RESULT
    assert diagnostic.handoff.in_reply_to == request.handoff_id
    assert len(diagnostic.handoff.action_ids) == 3
    assert len(diagnostic.handoff.observation_ids) == 3
    assert diagnostic.handoff.action_ids == tuple(
        record.action.action_id for record in diagnostic.run.executions
    )


def test_diagnostic_agent_rejects_non_diagnostic_request() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    wrong_request = AgentHandoff(
        handoff_id="HND-SAFETY",
        incident_id=brief.incident.incident_id,
        kind=HandoffKind.SAFETY_REVIEW_REQUEST,
        sender=AgentRole.COORDINATOR,
        recipient=AgentRole.SAFETY_REVIEWER,
        purpose="This belongs to the safety reviewer.",
        created_at=brief.incident.reported_at,
    )
    agent = DiagnosticAgent(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    )

    with pytest.raises(ValueError, match="requires investigation_request"):
        agent.handle(
            wrong_request,
            incident=brief.incident,
            known_asset_ids=brief.known_asset_ids,
        )


def test_diagnostic_agent_cannot_receive_controlled_write_tool() -> None:
    with pytest.raises(ValueError, match="only receive read-only tools"):
        DiagnosticAgent(
            policy=RuleBasedPlanner(),
            registry=ToolRegistry((ControlledTool(),)),
        )


def test_diagnostic_work_product_rejects_omitted_action_reference() -> None:
    _, _, diagnostic = run_diagnostic()
    incomplete_handoff = replace(
        diagnostic.handoff,
        action_ids=diagnostic.handoff.action_ids[:-1],
    )

    with pytest.raises(ValueError, match="reference every run action"):
        DiagnosticWorkProduct(
            run=diagnostic.run,
            handoff=incomplete_handoff,
        )


def test_safety_reviewer_approves_authorized_evidence_backed_run() -> None:
    environment, investigation_request, diagnostic = run_diagnostic()
    safety_request = make_safety_request(diagnostic)
    observation_count_before_review = environment.observation_count

    review = SafetyReviewerAgent().handle(
        safety_request,
        diagnostic=diagnostic,
    )

    assert review.outcome is SafetyReviewOutcome.APPROVED
    assert review.handoff.in_reply_to == safety_request.handoff_id
    assert review.handoff.action_ids == diagnostic.handoff.action_ids
    assert environment.observation_count == observation_count_before_review
    ledger = HandoffLedger(
        diagnostic.run.incident.incident_id,
        (
            investigation_request,
            diagnostic.handoff,
            safety_request,
            review.handoff,
        ),
    )
    assert ledger.pending_requests == ()


def test_safety_reviewer_rejects_incomplete_review_scope() -> None:
    _, _, diagnostic = run_diagnostic()
    incomplete_request = replace(
        make_safety_request(diagnostic),
        action_ids=diagnostic.handoff.action_ids[:-1],
    )

    with pytest.raises(ValueError, match="include every diagnostic action"):
        SafetyReviewerAgent().handle(
            incomplete_request,
            diagnostic=diagnostic,
        )


def test_safety_reviewer_requires_attention_for_incomplete_diagnosis() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    connectivity = FaultInjectingTool(
        ConnectivityTool(environment),
        (InjectedFault.PERMANENT,),
    )
    registry = ToolRegistry((connectivity, TelemetryTool(environment)))
    brief = environment.brief
    request = make_request(brief.incident)
    diagnostic = DiagnosticAgent(
        policy=RuleBasedPlanner(),
        registry=registry,
        retry_policy=RetryPolicy(max_attempts=1),
    ).handle(
        request,
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    review = SafetyReviewerAgent().handle(
        make_safety_request(diagnostic),
        diagnostic=diagnostic,
    )

    assert diagnostic.run.final_state.status is TaskStatus.SAFE_STOPPED
    assert review.outcome is SafetyReviewOutcome.REQUIRES_ATTENTION
    assert "does not support a final report" in review.rationale


def test_safety_reviewer_rejects_execution_marked_as_denied() -> None:
    _, _, diagnostic = run_diagnostic()
    denied_assessment = replace(
        diagnostic.run.safety_assessments[0],
        disposition=SafetyDisposition.DENY,
    )
    tampered_run = replace(
        diagnostic.run,
        safety_assessments=(
            denied_assessment,
            *diagnostic.run.safety_assessments[1:],
        ),
    )
    tampered_product = DiagnosticWorkProduct(
        run=tampered_run,
        handoff=diagnostic.handoff,
    )

    review = SafetyReviewerAgent().handle(
        make_safety_request(tampered_product),
        diagnostic=tampered_product,
    )

    assert review.outcome is SafetyReviewOutcome.REJECTED
    assert "without valid authorization" in review.findings[0]


def test_safety_reviewer_treats_rejected_unexecuted_action_as_safe_control() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    investigation_request = make_request(brief.incident)
    runner = SingleAgentRunner(
        policy=ControlledPolicy(),
        registry=ToolRegistry((ControlledTool(),)),
    )
    waiting = runner.run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )
    stopped = runner.resolve_approval(
        waiting,
        outcome=ApprovalOutcome.REJECTED,
        decided_by="operator-01",
        rationale="No maintenance window.",
        known_asset_ids=brief.known_asset_ids,
    )
    diagnostic_handoff = AgentHandoff(
        handoff_id=f"HND-{brief.incident.incident_id}-DIAGNOSTIC-RESULT",
        incident_id=brief.incident.incident_id,
        kind=HandoffKind.DIAGNOSTIC_RESULT,
        sender=AgentRole.DIAGNOSTIC,
        recipient=AgentRole.COORDINATOR,
        purpose="Controlled action was rejected and remained unexecuted.",
        created_at=stopped.final_state.updated_at + timedelta(seconds=1),
        in_reply_to=investigation_request.handoff_id,
    )
    diagnostic = DiagnosticWorkProduct(
        run=stopped,
        handoff=diagnostic_handoff,
    )

    review = SafetyReviewerAgent().handle(
        make_safety_request(diagnostic),
        diagnostic=diagnostic,
    )

    assert review.outcome is SafetyReviewOutcome.REQUIRES_ATTENTION
    assert "remained unexecuted as required" in review.findings[0]
