"""Structured incident-intake contracts and adapters."""

from agentic_manufacturing_incident_lab.intake.contracts import (
    INTAKE_PAYLOAD_FIELDS,
    ConfirmedIncidentIntake,
    IncidentIntake,
    IncidentTextParser,
    IntakeSource,
    SymptomType,
    confirm_intake,
    incident_intake_json_schema,
    intake_from_payload,
)
from agentic_manufacturing_incident_lab.intake.manual import build_manual_intake
from agentic_manufacturing_incident_lab.intake.ollama import (
    MAX_INTAKE_TEXT_LENGTH,
    OllamaIncidentTextParser,
)

__all__ = [
    "INTAKE_PAYLOAD_FIELDS",
    "ConfirmedIncidentIntake",
    "IncidentIntake",
    "IncidentTextParser",
    "IntakeSource",
    "MAX_INTAKE_TEXT_LENGTH",
    "OllamaIncidentTextParser",
    "SymptomType",
    "build_manual_intake",
    "confirm_intake",
    "incident_intake_json_schema",
    "intake_from_payload",
]
