"""Immutable aggregate for one investigation's states, executions, and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agentic_manufacturing_incident_lab.domain.models import Evidence, Incident, Observation
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.runtime.executor import ActionExecutionRecord

if TYPE_CHECKING:
    from agentic_manufacturing_incident_lab.agent.memory import WorkingMemory
    from agentic_manufacturing_incident_lab.safety import (
        ApprovalDecision,
        ApprovalRequest,
        SafetyAssessment,
    )


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    """A replayable snapshot of all records produced by one investigation."""

    incident: Incident
    task_states: tuple[TaskState, ...]
    executions: tuple[ActionExecutionRecord, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    memory_states: tuple[WorkingMemory, ...] = ()
    safety_assessments: tuple[SafetyAssessment, ...] = ()
    approval_requests: tuple[ApprovalRequest, ...] = ()
    approval_decisions: tuple[ApprovalDecision, ...] = ()

    def __post_init__(self) -> None:
        task_states = tuple(self.task_states)
        executions = tuple(self.executions)
        evidence = tuple(self.evidence)
        memory_states = tuple(self.memory_states)
        safety_assessments = tuple(self.safety_assessments)
        approval_requests = tuple(self.approval_requests)
        approval_decisions = tuple(self.approval_decisions)
        if not task_states:
            raise ValueError("task_states must contain at least one state")
        if task_states[0].status is not TaskStatus.CREATED:
            raise ValueError("the first task state must be created")

        task_ids = {state.task_id for state in task_states}
        if len(task_ids) != 1:
            raise ValueError("all task states must have the same task_id")
        if any(state.incident_id != self.incident.incident_id for state in task_states):
            raise ValueError("all task states must match the run incident")
        if tuple(state.revision for state in task_states) != tuple(range(len(task_states))):
            raise ValueError("task state revisions must be contiguous and start at zero")
        if any(
            later.updated_at <= earlier.updated_at
            for earlier, later in zip(task_states, task_states[1:])
        ):
            raise ValueError("task state timestamps must move forward")

        action_ids = tuple(record.action.action_id for record in executions)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("execution actions must have unique action_id values")
        if any(
            record.action.incident_id != self.incident.incident_id for record in executions
        ):
            raise ValueError("all executions must match the run incident")

        observations = tuple(
            observation for record in executions for observation in record.observations
        )
        observation_ids = tuple(
            observation.observation_id for observation in observations
        )
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("run observations must have unique observation_id values")

        evidence_ids = tuple(item.evidence_id for item in evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("run evidence must have unique evidence_id values")
        if any(item.incident_id != self.incident.incident_id for item in evidence):
            raise ValueError("all evidence must match the run incident")
        known_observation_ids = set(observation_ids)
        if any(
            not set(item.observation_ids).issubset(known_observation_ids)
            for item in evidence
        ):
            raise ValueError("evidence may only reference observations in the run")

        if memory_states:
            task_id = task_states[0].task_id
            if any(memory.task_id != task_id for memory in memory_states):
                raise ValueError("all memory states must match the run task")
            if any(
                memory.incident_id != self.incident.incident_id
                for memory in memory_states
            ):
                raise ValueError("all memory states must match the run incident")
            if tuple(memory.revision for memory in memory_states) != tuple(
                range(len(memory_states))
            ):
                raise ValueError(
                    "memory revisions must be contiguous and start at zero"
                )
            if any(
                later.updated_at <= earlier.updated_at
                for earlier, later in zip(memory_states, memory_states[1:])
            ):
                raise ValueError("memory state timestamps must move forward")
            action_limits = {memory.step_budget.action_limit for memory in memory_states}
            if len(action_limits) != 1:
                raise ValueError("memory states must preserve one action_limit")
            if memory_states[-1].step_budget.actions_used != len(executions):
                raise ValueError("final memory actions_used must match run executions")
            if any(
                not set(memory.referenced_observation_ids).issubset(
                    known_observation_ids
                )
                for memory in memory_states
            ):
                raise ValueError(
                    "memory facts may only reference observations in the run"
                )

        assessment_ids = tuple(
            assessment.assessment_id for assessment in safety_assessments
        )
        assessed_action_ids = tuple(
            assessment.action_id for assessment in safety_assessments
        )
        if len(set(assessment_ids)) != len(assessment_ids):
            raise ValueError("safety assessments must have unique assessment_id values")
        if len(set(assessed_action_ids)) != len(assessed_action_ids):
            raise ValueError("each action may only have one safety assessment")
        if any(
            assessment.incident_id != self.incident.incident_id
            for assessment in safety_assessments
        ):
            raise ValueError("all safety assessments must match the run incident")
        if safety_assessments and not set(action_ids).issubset(assessed_action_ids):
            raise ValueError("every executed action must have a safety assessment")

        assessments_by_id = {
            assessment.assessment_id: assessment for assessment in safety_assessments
        }
        request_ids = tuple(request.request_id for request in approval_requests)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("approval requests must have unique request_id values")
        if any(
            request.action.incident_id != self.incident.incident_id
            for request in approval_requests
        ):
            raise ValueError("all approval requests must match the run incident")
        if any(
            assessments_by_id.get(request.assessment.assessment_id)
            != request.assessment
            for request in approval_requests
        ):
            raise ValueError("approval requests must reference run safety assessments")

        decisions_by_request_id: dict[str, ApprovalDecision] = {}
        decision_ids: set[str] = set()
        requests_by_id = {request.request_id: request for request in approval_requests}
        for decision in approval_decisions:
            if decision.decision_id in decision_ids:
                raise ValueError(
                    "approval decisions must have unique decision_id values"
                )
            decision_ids.add(decision.decision_id)
            request_id = decision.request.request_id
            if request_id in decisions_by_request_id:
                raise ValueError("an approval request may only have one decision")
            if requests_by_id.get(request_id) != decision.request:
                raise ValueError("approval decisions must reference run approval requests")
            decisions_by_request_id[request_id] = decision

        pending_requests = tuple(
            request
            for request in approval_requests
            if request.request_id not in decisions_by_request_id
        )
        if len(pending_requests) > 1:
            raise ValueError("a run may have at most one pending approval request")
        if self.final_state.status is TaskStatus.WAITING_APPROVAL:
            if len(pending_requests) != 1:
                raise ValueError("waiting task requires one pending approval request")
        elif pending_requests:
            raise ValueError("pending approval requires a waiting task")

        executed_action_ids = set(action_ids)
        for decision in approval_decisions:
            action_id = decision.request.action.action_id
            if (
                decision.outcome.value == "approved"
                and action_id not in executed_action_ids
            ):
                raise ValueError("approved action must exist in run executions")
            if decision.outcome.value == "rejected" and action_id in executed_action_ids:
                raise ValueError("rejected action must not be executed")

        object.__setattr__(self, "task_states", task_states)
        object.__setattr__(self, "executions", executions)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "memory_states", memory_states)
        object.__setattr__(self, "safety_assessments", safety_assessments)
        object.__setattr__(self, "approval_requests", approval_requests)
        object.__setattr__(self, "approval_decisions", approval_decisions)

    @property
    def final_state(self) -> TaskState:
        """Return the latest task state in the run."""
        return self.task_states[-1]

    @property
    def observations(self) -> tuple[Observation, ...]:
        """Return every observation in execution order."""
        return tuple(
            observation for record in self.executions for observation in record.observations
        )

    @property
    def final_memory(self) -> WorkingMemory | None:
        """Return the latest working-memory snapshot when the run uses memory."""
        return self.memory_states[-1] if self.memory_states else None

    @property
    def pending_approval(self) -> ApprovalRequest | None:
        """Return the one unresolved approval request, if present."""
        decided_request_ids = {
            decision.request.request_id for decision in self.approval_decisions
        }
        for request in self.approval_requests:
            if request.request_id not in decided_request_ids:
                return request
        return None
