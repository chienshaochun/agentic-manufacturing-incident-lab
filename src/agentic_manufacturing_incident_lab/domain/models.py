"""Immutable records used to describe incidents and observations."""

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
