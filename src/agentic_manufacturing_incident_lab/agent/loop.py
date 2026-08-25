"""Single-agent loop with memory, safety assessment, approval, and resume."""

from dataclasses import replace
from datetime import datetime, timedelta

from agentic_manufacturing_incident_lab.agent.contracts import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningPolicy,
    StopDecision,
)
from agentic_manufacturing_incident_lab.agent.memory import (
    WorkingMemory,
    complete_working_memory,
    initialize_working_memory,
    prepare_action_memory,
    record_action_memory,
)
from agentic_manufacturing_incident_lab.domain.models import Action, Evidence, Incident
from agentic_manufacturing_incident_lab.domain.task import (
    TaskState,
    TaskStatus,
    transition_task,
)
from agentic_manufacturing_incident_lab.runtime import (
    ActionExecutionRecord,
    ActionExecutor,
    InvestigationRun,
    RetryPolicy,
)
from agentic_manufacturing_incident_lab.safety import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    RiskBasedSafetyPolicy,
    SafetyAssessment,
    SafetyDisposition,
    SafetyPolicy,
    create_approval_request,
    record_approval_decision,
)
from agentic_manufacturing_incident_lab.tools import ToolRegistry


class SingleAgentRunner:
    """Run one planning policy through controlled actions and terminal decisions."""

    __slots__ = (
        "_action_limit",
        "_executor",
        "_policy",
        "_registry",
        "_safety_policy",
    )

    def __init__(
        self,
        *,
        policy: PlanningPolicy,
        registry: ToolRegistry,
        action_limit: int = 32,
        safety_policy: SafetyPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if (
            isinstance(action_limit, bool)
            or not isinstance(action_limit, int)
            or action_limit <= 0
        ):
            raise ValueError("action_limit must be a positive integer")
        self._policy = policy
        self._registry = registry
        self._executor = ActionExecutor(registry, retry_policy=retry_policy)
        self._action_limit = action_limit
        self._safety_policy = safety_policy or RiskBasedSafetyPolicy()

    def run(
        self,
        *,
        incident: Incident,
        known_asset_ids: tuple[str, ...],
        pause_after_actions: int | None = None,
    ) -> InvestigationRun:
        """Start an investigation and optionally pause after a total action count."""
        self._validate_pause_after_actions(pause_after_actions)
        created = TaskState(
            task_id=f"TASK-{incident.incident_id}",
            incident_id=incident.incident_id,
            status=TaskStatus.CREATED,
            revision=0,
            updated_at=incident.reported_at,
            reason="Single-agent investigation task created.",
        )
        investigating = transition_task(
            created,
            TaskStatus.INVESTIGATING,
            reason=f"Planning policy {self._policy.name} started.",
            updated_at=incident.reported_at + timedelta(seconds=1),
        )
        task_states = [created, investigating]
        memory_states = [
            initialize_working_memory(
                task_id=created.task_id,
                incident=incident,
                action_limit=self._action_limit,
                updated_at=investigating.updated_at,
            )
        ]
        return self._continue_run(
            incident=incident,
            known_asset_ids=known_asset_ids,
            task_states=task_states,
            executions=[],
            memory_states=memory_states,
            safety_assessments=[],
            approval_requests=[],
            approval_decisions=[],
            pause_after_actions=pause_after_actions,
        )

    def resume(
        self,
        partial_run: InvestigationRun,
        *,
        known_asset_ids: tuple[str, ...],
        pause_after_actions: int | None = None,
    ) -> InvestigationRun:
        """Continue one investigating run using the configured runtime."""
        self._validate_pause_after_actions(pause_after_actions)
        if partial_run.final_state.status is not TaskStatus.INVESTIGATING:
            raise ValueError("only an investigating run can be resumed")
        if partial_run.evidence:
            raise ValueError("an investigating run cannot already contain evidence")
        self._validate_resume_configuration(partial_run)
        return self._continue_run(
            incident=partial_run.incident,
            known_asset_ids=known_asset_ids,
            task_states=list(partial_run.task_states),
            executions=list(partial_run.executions),
            memory_states=list(partial_run.memory_states),
            safety_assessments=list(partial_run.safety_assessments),
            approval_requests=list(partial_run.approval_requests),
            approval_decisions=list(partial_run.approval_decisions),
            pause_after_actions=pause_after_actions,
        )

    def resolve_approval(
        self,
        waiting_run: InvestigationRun,
        *,
        outcome: ApprovalOutcome,
        decided_by: str,
        rationale: str,
        known_asset_ids: tuple[str, ...],
        decided_at: datetime | None = None,
        pause_after_actions: int | None = None,
    ) -> InvestigationRun:
        """Record a human decision, then execute an approved pending action."""
        self._validate_pause_after_actions(pause_after_actions)
        if waiting_run.final_state.status is not TaskStatus.WAITING_APPROVAL:
            raise ValueError("only a waiting-approval run can receive a decision")
        self._validate_resume_configuration(waiting_run)
        request = waiting_run.pending_approval
        if request is None:
            raise ValueError("waiting run has no pending approval request")
        if request.assessment.policy_name != self._safety_policy.name:
            raise ValueError("runner safety policy must match approval request")

        task_states = list(waiting_run.task_states)
        executions = list(waiting_run.executions)
        memory_states = list(waiting_run.memory_states)
        safety_assessments = list(waiting_run.safety_assessments)
        approval_requests = list(waiting_run.approval_requests)
        approval_decisions = list(waiting_run.approval_decisions)
        decision_time = decided_at or (
            self._latest_time(
                task_states,
                executions,
                memory_states,
                safety_assessments,
                approval_requests,
                approval_decisions,
            )
            + timedelta(seconds=1)
        )
        approval = record_approval_decision(
            request,
            outcome=outcome,
            decided_by=decided_by,
            rationale=rationale,
            decided_at=decision_time,
        )
        approval_decisions.append(approval)

        if outcome is ApprovalOutcome.REJECTED:
            stopped = transition_task(
                task_states[-1],
                TaskStatus.SAFE_STOPPED,
                reason=f"Human operator rejected action: {rationale}",
                updated_at=decision_time + timedelta(seconds=1),
            )
            task_states.append(stopped)
            return self._snapshot_run(
                incident=waiting_run.incident,
                task_states=task_states,
                executions=executions,
                memory_states=memory_states,
                safety_assessments=safety_assessments,
                approval_requests=approval_requests,
                approval_decisions=approval_decisions,
            )

        investigating = transition_task(
            task_states[-1],
            TaskStatus.INVESTIGATING,
            reason=f"Human operator {decided_by} approved the pending action.",
            updated_at=decision_time + timedelta(seconds=1),
        )
        task_states.append(investigating)
        approved_action = replace(
            request.action,
            requested_at=decision_time + timedelta(seconds=2),
        )
        self._execute_action(approved_action, executions, memory_states)
        return self._continue_run(
            incident=waiting_run.incident,
            known_asset_ids=known_asset_ids,
            task_states=task_states,
            executions=executions,
            memory_states=memory_states,
            safety_assessments=safety_assessments,
            approval_requests=approval_requests,
            approval_decisions=approval_decisions,
            pause_after_actions=pause_after_actions,
        )

    def _continue_run(
        self,
        *,
        incident: Incident,
        known_asset_ids: tuple[str, ...],
        task_states: list[TaskState],
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
        safety_assessments: list[SafetyAssessment],
        approval_requests: list[ApprovalRequest],
        approval_decisions: list[ApprovalDecision],
        pause_after_actions: int | None,
    ) -> InvestigationRun:
        while True:
            context = AgentContext(
                incident=incident,
                known_asset_ids=known_asset_ids,
                task_state=task_states[-1],
                available_tools=self._registry.specs,
                working_memory=memory_states[-1],
                executions=tuple(executions),
            )
            if pause_after_actions is not None and len(executions) >= pause_after_actions:
                return self._snapshot_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                )

            decision = self._policy.decide(context)
            if isinstance(decision, CompleteDecision):
                return self._complete_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    decision=decision,
                )
            if isinstance(decision, StopDecision):
                return self._stop_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    reason=(
                        f"Planner stopped ({decision.reason.value}): "
                        f"{decision.rationale}"
                    ),
                )
            if not isinstance(decision, ActionDecision):
                return self._stop_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    reason="Planner returned an unsupported decision type.",
                )
            if memory_states[-1].step_budget.is_exhausted:
                return self._stop_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    reason=(
                        "Step budget exhausted before the planner produced a terminal "
                        "decision."
                    ),
                )

            specs_by_name = {spec.name: spec for spec in self._registry.specs}
            spec = specs_by_name.get(decision.tool_name)
            if spec is None:
                return self._stop_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    reason=(
                        "Planner proposed a tool outside the runtime allowlist: "
                        f"{decision.tool_name}."
                    ),
                )

            sequence = len(safety_assessments) + 1
            action = Action(
                action_id=f"{incident.incident_id}-ACT-{sequence:03d}",
                incident_id=incident.incident_id,
                tool_name=decision.tool_name,
                rationale=decision.rationale,
                risk=spec.risk,
                requested_at=self._latest_time(
                    task_states,
                    executions,
                    memory_states,
                    safety_assessments,
                    approval_requests,
                    approval_decisions,
                )
                + timedelta(seconds=1),
                parameters=decision.parameters,
            )
            assessment = self._safety_policy.assess(
                action,
                assessed_at=action.requested_at + timedelta(seconds=1),
            )
            safety_assessments.append(assessment)

            if assessment.disposition is SafetyDisposition.DENY:
                return self._stop_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                    reason=f"Safety policy denied action: {assessment.rationale}",
                )
            if assessment.disposition is SafetyDisposition.REQUIRE_APPROVAL:
                request = create_approval_request(
                    action,
                    assessment,
                    requested_at=assessment.assessed_at + timedelta(seconds=1),
                )
                approval_requests.append(request)
                waiting = transition_task(
                    task_states[-1],
                    TaskStatus.WAITING_APPROVAL,
                    reason=f"Waiting for approval of {action.action_id}.",
                    updated_at=request.requested_at + timedelta(seconds=1),
                )
                task_states.append(waiting)
                return self._snapshot_run(
                    incident=incident,
                    task_states=task_states,
                    executions=executions,
                    memory_states=memory_states,
                    safety_assessments=safety_assessments,
                    approval_requests=approval_requests,
                    approval_decisions=approval_decisions,
                )

            self._execute_action(action, executions, memory_states)

    def _execute_action(
        self,
        action: Action,
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
    ) -> None:
        memory_states.append(prepare_action_memory(memory_states[-1], action))
        record = self._executor.execute(action)
        executions.append(record)
        memory_states.append(record_action_memory(memory_states[-1], record))

    def _validate_resume_configuration(self, run: InvestigationRun) -> None:
        if run.final_memory is None:
            raise ValueError("a resumable run must contain working memory")
        if run.final_memory.step_budget.action_limit != self._action_limit:
            raise ValueError("runner action_limit must match checkpoint memory")
        expected_policy_reason = f"Planning policy {self._policy.name} started."
        if len(run.task_states) < 2 or run.task_states[1].reason != expected_policy_reason:
            raise ValueError("runner planning policy must match checkpoint policy")
        if any(
            assessment.policy_name != self._safety_policy.name
            for assessment in run.safety_assessments
        ):
            raise ValueError("runner safety policy must match checkpoint policy")

    @staticmethod
    def _snapshot_run(
        *,
        incident: Incident,
        task_states: list[TaskState],
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
        safety_assessments: list[SafetyAssessment],
        approval_requests: list[ApprovalRequest],
        approval_decisions: list[ApprovalDecision],
    ) -> InvestigationRun:
        return InvestigationRun(
            incident=incident,
            task_states=tuple(task_states),
            executions=tuple(executions),
            memory_states=tuple(memory_states),
            safety_assessments=tuple(safety_assessments),
            approval_requests=tuple(approval_requests),
            approval_decisions=tuple(approval_decisions),
        )

    @staticmethod
    def _validate_pause_after_actions(value: int | None) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("pause_after_actions must be a non-negative integer")

    @classmethod
    def _complete_run(
        cls,
        *,
        incident: Incident,
        task_states: list[TaskState],
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
        safety_assessments: list[SafetyAssessment],
        approval_requests: list[ApprovalRequest],
        approval_decisions: list[ApprovalDecision],
        decision: CompleteDecision,
    ) -> InvestigationRun:
        known_observation_ids = {
            observation.observation_id
            for record in executions
            for observation in record.observations
        }
        if not set(decision.observation_ids).issubset(known_observation_ids):
            return cls._stop_run(
                incident=incident,
                task_states=task_states,
                executions=executions,
                memory_states=memory_states,
                safety_assessments=safety_assessments,
                approval_requests=approval_requests,
                approval_decisions=approval_decisions,
                reason=(
                    "Planner completion referenced observations that were not collected "
                    "during this investigation."
                ),
            )

        latest_time = cls._latest_time(
            task_states,
            executions,
            memory_states,
            safety_assessments,
            approval_requests,
            approval_decisions,
        )
        memory_states.append(
            complete_working_memory(
                memory_states[-1],
                updated_at=latest_time + timedelta(seconds=1),
            )
        )
        evidence = Evidence(
            evidence_id=f"EVD-{incident.incident_id}-001",
            incident_id=incident.incident_id,
            claim=decision.claim,
            observation_ids=decision.observation_ids,
            confidence=decision.confidence,
            created_at=latest_time + timedelta(seconds=2),
        )
        completed = transition_task(
            task_states[-1],
            TaskStatus.COMPLETED,
            reason=decision.rationale,
            updated_at=latest_time + timedelta(seconds=3),
        )
        return InvestigationRun(
            incident=incident,
            task_states=(*task_states, completed),
            executions=tuple(executions),
            evidence=(evidence,),
            memory_states=tuple(memory_states),
            safety_assessments=tuple(safety_assessments),
            approval_requests=tuple(approval_requests),
            approval_decisions=tuple(approval_decisions),
        )

    @classmethod
    def _stop_run(
        cls,
        *,
        incident: Incident,
        task_states: list[TaskState],
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
        safety_assessments: list[SafetyAssessment],
        approval_requests: list[ApprovalRequest],
        approval_decisions: list[ApprovalDecision],
        reason: str,
    ) -> InvestigationRun:
        stopped = transition_task(
            task_states[-1],
            TaskStatus.SAFE_STOPPED,
            reason=reason,
            updated_at=cls._latest_time(
                task_states,
                executions,
                memory_states,
                safety_assessments,
                approval_requests,
                approval_decisions,
            )
            + timedelta(seconds=1),
        )
        return InvestigationRun(
            incident=incident,
            task_states=(*task_states, stopped),
            executions=tuple(executions),
            memory_states=tuple(memory_states),
            safety_assessments=tuple(safety_assessments),
            approval_requests=tuple(approval_requests),
            approval_decisions=tuple(approval_decisions),
        )

    @staticmethod
    def _latest_time(
        task_states: list[TaskState],
        executions: list[ActionExecutionRecord],
        memory_states: list[WorkingMemory],
        safety_assessments: list[SafetyAssessment],
        approval_requests: list[ApprovalRequest],
        approval_decisions: list[ApprovalDecision],
    ) -> datetime:
        timestamps = [task_states[-1].updated_at]
        timestamps.extend(record.result.completed_at for record in executions)
        timestamps.extend(memory.updated_at for memory in memory_states)
        timestamps.extend(item.assessed_at for item in safety_assessments)
        timestamps.extend(item.requested_at for item in approval_requests)
        timestamps.extend(item.decided_at for item in approval_decisions)
        return max(timestamps)
