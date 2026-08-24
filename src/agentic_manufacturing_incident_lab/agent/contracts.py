"""Immutable context and decision contracts shared by all planning policies."""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol, TypeAlias, runtime_checkable

from agentic_manufacturing_incident_lab.domain._validation import require_text
from agentic_manufacturing_incident_lab.domain.models import (
    Incident,
    Observation,
    ScalarValue,
)
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.agent.memory import WorkingMemory
from agentic_manufacturing_incident_lab.runtime import ActionExecutionRecord
from agentic_manufacturing_incident_lab.tools import ToolSpec


@dataclass(frozen=True, slots=True)
class AgentContext:
    """The complete, limited information available for one planning decision."""

    incident: Incident
    known_asset_ids: tuple[str, ...]
    task_state: TaskState
    available_tools: tuple[ToolSpec, ...]
    working_memory: WorkingMemory
    executions: tuple[ActionExecutionRecord, ...] = ()

    def __post_init__(self) -> None:
        known_asset_ids = tuple(self.known_asset_ids)
        available_tools = tuple(self.available_tools)
        executions = tuple(self.executions)
        if not known_asset_ids:
            raise ValueError("known_asset_ids must contain at least one asset")
        for asset_id in known_asset_ids:
            require_text(asset_id, "asset_id")
        if len(set(known_asset_ids)) != len(known_asset_ids):
            raise ValueError("known_asset_ids must not contain duplicates")
        if self.incident.asset_id not in known_asset_ids:
            raise ValueError("incident asset_id must exist in known_asset_ids")
        if self.task_state.incident_id != self.incident.incident_id:
            raise ValueError("task state must match the context incident")
        if self.task_state.status is not TaskStatus.INVESTIGATING:
            raise ValueError("planner context requires an investigating task")
        if self.working_memory.task_id != self.task_state.task_id:
            raise ValueError("working memory must match the context task")
        if self.working_memory.incident_id != self.incident.incident_id:
            raise ValueError("working memory must match the context incident")

        tool_names = tuple(spec.name for spec in available_tools)
        if len(set(tool_names)) != len(tool_names):
            raise ValueError("available tools must have unique names")
        action_ids = tuple(record.action.action_id for record in executions)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("context executions must have unique action_id values")
        if any(
            record.action.incident_id != self.incident.incident_id for record in executions
        ):
            raise ValueError("all executions must match the context incident")
        if self.working_memory.step_budget.actions_used != len(executions):
            raise ValueError("working memory actions_used must match context executions")
        known_observation_ids = {
            observation.observation_id
            for record in executions
            for observation in record.observations
        }
        if not set(self.working_memory.referenced_observation_ids).issubset(
            known_observation_ids
        ):
            raise ValueError("working memory may only reference context observations")

        object.__setattr__(self, "known_asset_ids", known_asset_ids)
        object.__setattr__(self, "available_tools", available_tools)
        object.__setattr__(self, "executions", executions)

    @property
    def observations(self) -> tuple[Observation, ...]:
        """Return every observation in action execution order."""
        return tuple(
            observation for record in self.executions for observation in record.observations
        )

    @property
    def step_number(self) -> int:
        """Return the number of actions already attempted."""
        return len(self.executions)


@dataclass(frozen=True, slots=True)
class ActionDecision:
    """A planner proposal to invoke one named tool with specific parameters."""

    tool_name: str
    rationale: str
    parameters: Mapping[str, ScalarValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.tool_name, "tool_name")
        require_text(self.rationale, "rationale")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class CompleteDecision:
    """A planner decision that the investigation goal is supported by evidence."""

    rationale: str
    claim: str
    observation_ids: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        require_text(self.rationale, "rationale")
        require_text(self.claim, "claim")
        observation_ids = tuple(self.observation_ids)
        if not observation_ids:
            raise ValueError("observation_ids must contain at least one observation")
        for observation_id in observation_ids:
            require_text(observation_id, "observation_id")
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation_ids must not contain duplicates")
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "observation_ids", observation_ids)


class StopReason(StrEnum):
    """Controlled reason for stopping without claiming task completion."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SAFE_ACTION = "no_safe_action"
    POLICY_STOP = "policy_stop"


@dataclass(frozen=True, slots=True)
class StopDecision:
    """A planner decision to stop without manufacturing an unsupported claim."""

    reason: StopReason
    rationale: str

    def __post_init__(self) -> None:
        require_text(self.rationale, "rationale")


PlanningDecision: TypeAlias = ActionDecision | CompleteDecision | StopDecision


@runtime_checkable
class PlanningPolicy(Protocol):
    """Interchangeable decision policy used by the single-agent runtime."""

    name: str

    def decide(self, context: AgentContext) -> PlanningDecision:
        """Choose one tool proposal, task completion, or controlled stop."""
        ...
