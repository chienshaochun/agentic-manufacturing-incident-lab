"""Validated contracts between operator language and incident orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol, runtime_checkable

from agentic_manufacturing_incident_lab.domain._validation import require_text


class SymptomType(StrEnum):
    """Observable symptom categories; none of these is a root-cause label."""

    STATION_UNREACHABLE = "station_unreachable"
    MULTI_STATION_UNREACHABLE = "multi_station_unreachable"
    TELEMETRY_MISSING = "telemetry_missing"
    PROCESS_SIGNAL_FLATLINE = "process_signal_flatline"


class IntakeSource(StrEnum):
    """Origin of one structured intake interpretation."""

    MANUAL = "manual"
    OLLAMA = "ollama"


@dataclass(frozen=True, slots=True)
class IncidentIntake:
    """Strict structured interpretation awaiting operator confirmation."""

    raw_text: str
    asset_id: str
    symptom_type: SymptomType
    duration_minutes: int | None
    network_reachable: bool | None
    telemetry_available: bool | None
    peer_affected: bool | None
    parse_confidence: float
    parser_name: str
    source: IntakeSource

    def __post_init__(self) -> None:
        for field_name in ("raw_text", "asset_id", "parser_name"):
            require_text(getattr(self, field_name), field_name)
        if not isinstance(self.symptom_type, SymptomType):
            raise ValueError("symptom_type must be a SymptomType")
        if not isinstance(self.source, IntakeSource):
            raise ValueError("source must be an IntakeSource")
        if self.duration_minutes is not None and (
            isinstance(self.duration_minutes, bool)
            or not isinstance(self.duration_minutes, int)
            or self.duration_minutes < 0
        ):
            raise ValueError("duration_minutes must be a non-negative integer or None")
        for field_name in (
            "network_reachable",
            "telemetry_available",
            "peer_affected",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a boolean or None")
        if (
            isinstance(self.parse_confidence, bool)
            or not isinstance(self.parse_confidence, (int, float))
            or not 0.0 <= self.parse_confidence <= 1.0
        ):
            raise ValueError("parse_confidence must be between 0.0 and 1.0")


@runtime_checkable
class IncidentTextParser(Protocol):
    """Provider-neutral port that a future Ollama adapter must implement."""

    name: str

    def parse(
        self,
        raw_text: str,
        *,
        known_asset_ids: tuple[str, ...],
    ) -> IncidentIntake:
        """Return a validated structured interpretation without taking action."""


INTAKE_PAYLOAD_FIELDS = (
    "asset_id",
    "symptom_type",
    "duration_minutes",
    "network_reachable",
    "telemetry_available",
    "peer_affected",
    "parse_confidence",
)


def incident_intake_json_schema() -> dict[str, object]:
    """Return a fresh strict schema suitable for structured model output."""
    return {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "minLength": 1},
            "symptom_type": {
                "type": "string",
                "enum": [item.value for item in SymptomType],
            },
            "duration_minutes": {"type": ["integer", "null"], "minimum": 0},
            "network_reachable": {"type": ["boolean", "null"]},
            "telemetry_available": {"type": ["boolean", "null"]},
            "peer_affected": {"type": ["boolean", "null"]},
            "parse_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": list(INTAKE_PAYLOAD_FIELDS),
        "additionalProperties": False,
    }


def intake_from_payload(
    raw_text: str,
    payload: Mapping[str, object],
    *,
    parser_name: str,
    source: IntakeSource,
    known_asset_ids: tuple[str, ...],
) -> IncidentIntake:
    """Reject malformed or out-of-scope parser output before orchestration."""
    require_text(raw_text, "raw_text")
    require_text(parser_name, "parser_name")
    known_assets = tuple(known_asset_ids)
    if not known_assets:
        raise ValueError("known_asset_ids must not be empty")
    if len(set(known_assets)) != len(known_assets):
        raise ValueError("known_asset_ids must be unique")
    actual_fields = set(payload)
    expected_fields = set(INTAKE_PAYLOAD_FIELDS)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unknown = sorted(actual_fields - expected_fields)
        raise ValueError(
            f"intake payload fields mismatch; missing={missing}; unknown={unknown}"
        )
    asset_id = payload["asset_id"]
    if not isinstance(asset_id, str) or asset_id not in known_assets:
        raise ValueError("asset_id must reference a known asset")
    symptom_value = payload["symptom_type"]
    try:
        symptom_type = SymptomType(symptom_value)
    except (TypeError, ValueError) as error:
        raise ValueError("symptom_type is not allowlisted") from error
    return IncidentIntake(
        raw_text=raw_text,
        asset_id=asset_id,
        symptom_type=symptom_type,
        duration_minutes=payload["duration_minutes"],  # type: ignore[arg-type]
        network_reachable=payload["network_reachable"],  # type: ignore[arg-type]
        telemetry_available=payload["telemetry_available"],  # type: ignore[arg-type]
        peer_affected=payload["peer_affected"],  # type: ignore[arg-type]
        parse_confidence=payload["parse_confidence"],  # type: ignore[arg-type]
        parser_name=parser_name,
        source=source,
    )
