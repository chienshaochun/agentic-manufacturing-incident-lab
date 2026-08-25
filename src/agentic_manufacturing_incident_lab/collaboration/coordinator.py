"""Central coordinator and failure boundary for multi-agent collaboration."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
    HandoffLedger,
)
from agentic_manufacturing_incident_lab.collaboration.diagnostic import DiagnosticAgent
from agentic_manufacturing_incident_lab.collaboration.products import (
    CollaborationFailure,
    CollaborationFailureKind,
    CollaborationStage,
    DiagnosticWorkProduct,
    MultiAgentRun,
    MultiAgentStatus,
    ReportWorkProduct,
    SafetyReviewOutcome,
    SafetyReviewProduct,
)
from agentic_manufacturing_incident_lab.collaboration.reporter import ReporterAgent
from agentic_manufacturing_incident_lab.collaboration.safety_reviewer import (
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.domain.models import Incident
from agentic_manufacturing_incident_lab.domain.task import TaskStatus


class CoordinatorAgent:
    """Route specialists and convert collaboration failures into safe stops."""

    __slots__ = ("_diagnostic", "_reporter", "_safety_reviewer")

    def __init__(
        self,
        *,
        diagnostic: DiagnosticAgent,
        safety_reviewer: SafetyReviewerAgent,
        reporter: ReporterAgent,
    ) -> None:
        self._diagnostic = diagnostic
        self._safety_reviewer = safety_reviewer
        self._reporter = reporter

    def run(
        self,
        *,
        incident: Incident,
        known_asset_ids: tuple[str, ...],
    ) -> MultiAgentRun:
        """Run specialists synchronously while containing expected role failures."""
        ledger = HandoffLedger(incident_id=incident.incident_id)
        investigation_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-INVESTIGATE",
            incident_id=incident.incident_id,
            kind=HandoffKind.INVESTIGATION_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.DIAGNOSTIC,
            purpose=incident.goal,
            created_at=incident.reported_at,
        )
        ledger = ledger.append(investigation_request)
        try:
            diagnostic = self._diagnostic.handle(
                investigation_request,
                incident=incident,
                known_asset_ids=known_asset_ids,
            )
        except Exception as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=investigation_request,
                stage=CollaborationStage.DIAGNOSTIC,
                role=AgentRole.DIAGNOSTIC,
                kind=CollaborationFailureKind.SPECIALIST_ERROR,
                detail=self._error_detail(error),
            )
        if not isinstance(diagnostic, DiagnosticWorkProduct):
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=investigation_request,
                stage=CollaborationStage.DIAGNOSTIC,
                role=AgentRole.DIAGNOSTIC,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail="DiagnosticAgent returned an invalid work product.",
            )
        try:
            ledger = ledger.append(diagnostic.handoff)
        except (AttributeError, TypeError, ValueError) as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=investigation_request,
                stage=CollaborationStage.DIAGNOSTIC,
                role=AgentRole.DIAGNOSTIC,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail=self._error_detail(error),
            )

        safety_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-SAFETY-REVIEW",
            incident_id=incident.incident_id,
            kind=HandoffKind.SAFETY_REVIEW_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.SAFETY_REVIEWER,
            purpose="Review all diagnostic actions, approvals, and evidence.",
            created_at=diagnostic.handoff.created_at + timedelta(seconds=1),
            observation_ids=diagnostic.handoff.observation_ids,
            action_ids=diagnostic.handoff.action_ids,
        )
        ledger = ledger.append(safety_request)
        try:
            safety_review = self._safety_reviewer.handle(
                safety_request,
                diagnostic=diagnostic,
            )
        except Exception as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=safety_request,
                stage=CollaborationStage.SAFETY_REVIEW,
                role=AgentRole.SAFETY_REVIEWER,
                kind=CollaborationFailureKind.SPECIALIST_ERROR,
                detail=self._error_detail(error),
                diagnostic=diagnostic,
            )
        if not isinstance(safety_review, SafetyReviewProduct):
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=safety_request,
                stage=CollaborationStage.SAFETY_REVIEW,
                role=AgentRole.SAFETY_REVIEWER,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail="SafetyReviewerAgent returned an invalid work product.",
                diagnostic=diagnostic,
            )
        try:
            ledger = ledger.append(safety_review.handoff)
        except (AttributeError, TypeError, ValueError) as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=safety_request,
                stage=CollaborationStage.SAFETY_REVIEW,
                role=AgentRole.SAFETY_REVIEWER,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail=self._error_detail(error),
                diagnostic=diagnostic,
            )

        if (
            safety_review.outcome is SafetyReviewOutcome.APPROVED
            and (
                diagnostic.run.final_state.status is not TaskStatus.COMPLETED
                or not diagnostic.run.evidence
            )
        ):
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=safety_request,
                stage=CollaborationStage.SAFETY_REVIEW,
                role=AgentRole.SAFETY_REVIEWER,
                kind=CollaborationFailureKind.CONFLICTING_RESULT,
                detail=(
                    "Safety review approved a diagnostic run without "
                    "evidence-backed completion."
                ),
                diagnostic=diagnostic,
                safety_review=safety_review,
            )
        if safety_review.outcome is not SafetyReviewOutcome.APPROVED:
            return MultiAgentRun(
                status=MultiAgentStatus.SAFE_STOPPED,
                ledger=ledger,
                diagnostic=diagnostic,
                safety_review=safety_review,
            )

        report_request = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-REPORT",
            incident_id=incident.incident_id,
            kind=HandoffKind.REPORT_REQUEST,
            sender=AgentRole.COORDINATOR,
            recipient=AgentRole.REPORTER,
            purpose="Produce an evidence-bound report from the approved record.",
            created_at=safety_review.handoff.created_at + timedelta(seconds=1),
            observation_ids=diagnostic.handoff.observation_ids,
            action_ids=diagnostic.handoff.action_ids,
        )
        ledger = ledger.append(report_request)
        try:
            report = self._reporter.handle(
                report_request,
                diagnostic=diagnostic,
                safety_review=safety_review,
            )
        except Exception as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=report_request,
                stage=CollaborationStage.REPORTING,
                role=AgentRole.REPORTER,
                kind=CollaborationFailureKind.SPECIALIST_ERROR,
                detail=self._error_detail(error),
                diagnostic=diagnostic,
                safety_review=safety_review,
            )
        if not isinstance(report, ReportWorkProduct):
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=report_request,
                stage=CollaborationStage.REPORTING,
                role=AgentRole.REPORTER,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail="ReporterAgent returned an invalid work product.",
                diagnostic=diagnostic,
                safety_review=safety_review,
            )
        try:
            ledger = ledger.append(report.handoff)
        except (AttributeError, TypeError, ValueError) as error:
            return self._failed_run(
                incident=incident,
                ledger=ledger,
                request=report_request,
                stage=CollaborationStage.REPORTING,
                role=AgentRole.REPORTER,
                kind=CollaborationFailureKind.INVALID_RESPONSE,
                detail=self._error_detail(error),
                diagnostic=diagnostic,
                safety_review=safety_review,
            )
        return MultiAgentRun(
            status=MultiAgentStatus.COMPLETED,
            ledger=ledger,
            diagnostic=diagnostic,
            safety_review=safety_review,
            report=report,
        )

    @staticmethod
    def _error_detail(error: Exception) -> str:
        detail = str(error).strip() or "no error detail"
        return f"{type(error).__name__}: {detail}"

    @staticmethod
    def _failed_run(
        *,
        incident: Incident,
        ledger: HandoffLedger,
        request: AgentHandoff,
        stage: CollaborationStage,
        role: AgentRole,
        kind: CollaborationFailureKind,
        detail: str,
        diagnostic: DiagnosticWorkProduct | None = None,
        safety_review: SafetyReviewProduct | None = None,
    ) -> MultiAgentRun:
        failure = CollaborationFailure(
            failure_id=f"FAIL-{incident.incident_id}-{stage.value.upper()}",
            incident_id=incident.incident_id,
            stage=stage,
            role=role,
            kind=kind,
            detail=detail,
            related_request_id=request.handoff_id,
            occurred_at=max(
                request.created_at,
                ledger.handoffs[-1].created_at,
            )
            + timedelta(seconds=1),
        )
        return MultiAgentRun(
            status=MultiAgentStatus.SAFE_STOPPED,
            ledger=ledger,
            diagnostic=diagnostic,
            safety_review=safety_review,
            failures=(failure,),
        )
