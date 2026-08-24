"""Immutable aggregate for one investigation's states, executions, and evidence."""

from dataclasses import dataclass

from agentic_manufacturing_incident_lab.domain.models import Evidence, Incident, Observation
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.runtime.executor import ActionExecutionRecord


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    """A replayable snapshot of all records produced by one investigation."""

    incident: Incident
    task_states: tuple[TaskState, ...]
    executions: tuple[ActionExecutionRecord, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        task_states = tuple(self.task_states)
        executions = tuple(self.executions)
        evidence = tuple(self.evidence)
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

        object.__setattr__(self, "task_states", task_states)
        object.__setattr__(self, "executions", executions)
        object.__setattr__(self, "evidence", evidence)

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
