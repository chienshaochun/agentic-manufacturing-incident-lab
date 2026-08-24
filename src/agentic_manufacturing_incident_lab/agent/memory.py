"""Immutable working-memory records for resumable agent investigations."""

from dataclasses import dataclass, replace
from datetime import datetime

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


@dataclass(frozen=True, slots=True)
class MemoryFact:
    """One observation-backed fact retained in the agent's working memory."""

    fact_id: str
    incident_id: str
    statement: str
    observation_ids: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("fact_id", "incident_id", "statement"):
            require_text(getattr(self, field_name), field_name)
        observation_ids = tuple(self.observation_ids)
        if not observation_ids:
            raise ValueError("observation_ids must contain at least one observation")
        for observation_id in observation_ids:
            require_text(observation_id, "observation_id")
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation_ids must not contain duplicates")
        require_timezone(self.recorded_at, "recorded_at")
        object.__setattr__(self, "observation_ids", observation_ids)


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    """One unresolved question that can guide a later planning decision."""

    question_id: str
    incident_id: str
    prompt: str
    opened_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("question_id", "incident_id", "prompt"):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.opened_at, "opened_at")


class StepBudgetExceeded(RuntimeError):
    """Raised when an investigation attempts to consume an exhausted budget."""


@dataclass(frozen=True, slots=True)
class StepBudget:
    """Formal action allowance carried by working memory and checkpoints."""

    action_limit: int
    actions_used: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.action_limit, bool)
            or not isinstance(self.action_limit, int)
            or self.action_limit <= 0
        ):
            raise ValueError("action_limit must be a positive integer")
        if (
            isinstance(self.actions_used, bool)
            or not isinstance(self.actions_used, int)
            or self.actions_used < 0
        ):
            raise ValueError("actions_used must be a non-negative integer")
        if self.actions_used > self.action_limit:
            raise ValueError("actions_used must not exceed action_limit")

    @property
    def actions_remaining(self) -> int:
        """Return how many additional tool actions may be attempted."""
        return self.action_limit - self.actions_used

    @property
    def is_exhausted(self) -> bool:
        """Return whether no additional action may be attempted."""
        return self.actions_remaining == 0

    def consume(self) -> "StepBudget":
        """Return a new budget after one action, rejecting over-consumption."""
        if self.is_exhausted:
            raise StepBudgetExceeded("step budget is exhausted")
        return replace(self, actions_used=self.actions_used + 1)


@dataclass(frozen=True, slots=True)
class WorkingMemory:
    """One versioned snapshot of facts, questions, and remaining action budget."""

    task_id: str
    incident_id: str
    revision: int
    facts: tuple[MemoryFact, ...]
    open_questions: tuple[OpenQuestion, ...]
    step_budget: StepBudget
    updated_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("task_id", "incident_id"):
            require_text(getattr(self, field_name), field_name)
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("revision must be a non-negative integer")

        facts = tuple(self.facts)
        open_questions = tuple(self.open_questions)
        fact_ids = tuple(fact.fact_id for fact in facts)
        question_ids = tuple(question.question_id for question in open_questions)
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("facts must have unique fact_id values")
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("open questions must have unique question_id values")
        if any(fact.incident_id != self.incident_id for fact in facts):
            raise ValueError("all facts must match the memory incident")
        if any(
            question.incident_id != self.incident_id for question in open_questions
        ):
            raise ValueError("all open questions must match the memory incident")

        require_timezone(self.updated_at, "updated_at")
        if any(fact.recorded_at > self.updated_at for fact in facts):
            raise ValueError("facts must not be recorded after memory updated_at")
        if any(question.opened_at > self.updated_at for question in open_questions):
            raise ValueError("questions must not be opened after memory updated_at")

        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "open_questions", open_questions)

    @property
    def referenced_observation_ids(self) -> tuple[str, ...]:
        """Return unique observation references in first-seen fact order."""
        return tuple(
            dict.fromkeys(
                observation_id
                for fact in self.facts
                for observation_id in fact.observation_ids
            )
        )
