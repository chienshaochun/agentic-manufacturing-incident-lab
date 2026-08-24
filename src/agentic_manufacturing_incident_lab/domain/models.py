"""Immutable records used throughout an incident investigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, TypeAlias

ScalarValue: TypeAlias = str | int | float | bool | None


class IncidentSeverity(StrEnum):
    """Operational urgency assigned when an incident is reported."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ObservationKind(StrEnum):
    """Category of evidence returned by a diagnostic source."""

    ALARM = "alarm"
    METRIC = "metric"
    CONNECTIVITY = "connectivity"
    CONFIGURATION = "configuration"
    MAINTENANCE = "maintenance"


class ActionRisk(StrEnum):
    """Potential operational impact of a proposed action."""

    READ_ONLY = "read_only"
    CONTROLLED_WRITE = "controlled_write"
    HIGH_IMPACT = "high_impact"


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_timezone(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")


@dataclass(frozen=True, slots=True)
class Incident:
    """A reported problem and its investigation goal, not a proven cause."""

    incident_id: str
    title: str
    description: str
    asset_id: str
    severity: IncidentSeverity
    reported_at: datetime
    goal: str

    def __post_init__(self) -> None:
        for field_name in ("incident_id", "title", "description", "asset_id", "goal"):
            _require_text(getattr(self, field_name), field_name)
        _require_timezone(self.reported_at, "reported_at")


@dataclass(frozen=True, slots=True)
class Action:
    """An immutable request to invoke one registered tool for a stated reason."""

    action_id: str
    incident_id: str
    tool_name: str
    rationale: str
    risk: ActionRisk
    requested_at: datetime
    parameters: Mapping[str, ScalarValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("action_id", "incident_id", "tool_name", "rationale"):
            _require_text(getattr(self, field_name), field_name)
        _require_timezone(self.requested_at, "requested_at")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class Observation:
    """A timestamped piece of evidence collected during an investigation."""

    observation_id: str
    incident_id: str
    source: str
    kind: ObservationKind
    summary: str
    observed_at: datetime
    values: Mapping[str, ScalarValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("observation_id", "incident_id", "source", "summary"):
            _require_text(getattr(self, field_name), field_name)
        _require_timezone(self.observed_at, "observed_at")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class Evidence:
    """A claim explicitly supported by one or more observations."""

    evidence_id: str
    incident_id: str
    claim: str
    observation_ids: tuple[str, ...]
    confidence: float
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "incident_id", "claim"):
            _require_text(getattr(self, field_name), field_name)
        observation_ids = tuple(self.observation_ids)
        if not observation_ids:
            raise ValueError("observation_ids must contain at least one observation")
        for observation_id in observation_ids:
            _require_text(observation_id, "observation_id")
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation_ids must not contain duplicates")
        if isinstance(self.confidence, bool) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        _require_timezone(self.created_at, "created_at")
        object.__setattr__(self, "observation_ids", observation_ids)
