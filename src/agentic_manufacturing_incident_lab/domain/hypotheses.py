"""Immutable records for observation-backed diagnostic hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


class HypothesisStatus(StrEnum):
    """Current disposition of one candidate explanation."""

    OPEN = "open"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    CONFLICTED = "conflicted"


class HypothesisEffect(StrEnum):
    """How one observation changes a candidate explanation."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True, slots=True)
class HypothesisSignal:
    """Auditable link between one observation and one hypothesis."""

    hypothesis_id: str
    observation_id: str
    effect: HypothesisEffect
    weight: float
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("hypothesis_id", "observation_id", "rationale"):
            require_text(getattr(self, field_name), field_name)
        if isinstance(self.weight, bool) or not 0.0 < self.weight <= 1.0:
            raise ValueError("weight must be greater than 0.0 and at most 1.0")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A versioned candidate explanation grounded in observation references."""

    hypothesis_id: str
    incident_id: str
    statement: str
    status: HypothesisStatus
    confidence: float
    supporting_observation_ids: tuple[str, ...]
    contradicting_observation_ids: tuple[str, ...]
    rationale: str
    updated_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "hypothesis_id",
            "incident_id",
            "statement",
            "rationale",
        ):
            require_text(getattr(self, field_name), field_name)
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        supporting_ids = tuple(self.supporting_observation_ids)
        contradicting_ids = tuple(self.contradicting_observation_ids)
        for observation_id in (*supporting_ids, *contradicting_ids):
            require_text(observation_id, "observation_id")
        if len(set(supporting_ids)) != len(supporting_ids):
            raise ValueError("supporting observations must not contain duplicates")
        if len(set(contradicting_ids)) != len(contradicting_ids):
            raise ValueError("contradicting observations must not contain duplicates")
        if set(supporting_ids).intersection(contradicting_ids):
            raise ValueError("an observation cannot both support and contradict")
        if self.status is HypothesisStatus.SUPPORTED and not supporting_ids:
            raise ValueError("a supported hypothesis requires supporting observations")
        if self.status is HypothesisStatus.REJECTED and not contradicting_ids:
            raise ValueError("a rejected hypothesis requires contradicting observations")
        if self.status is HypothesisStatus.CONFLICTED and (
            not supporting_ids or not contradicting_ids
        ):
            raise ValueError(
                "a conflicted hypothesis requires supporting and contradicting observations"
            )
        require_timezone(self.updated_at, "updated_at")
        object.__setattr__(self, "supporting_observation_ids", supporting_ids)
        object.__setattr__(self, "contradicting_observation_ids", contradicting_ids)

    @property
    def observation_ids(self) -> tuple[str, ...]:
        """Return every referenced observation in stable first-seen order."""
        return tuple(
            dict.fromkeys(
                (*self.supporting_observation_ids, *self.contradicting_observation_ids)
            )
        )
