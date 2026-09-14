"""Manual structured fallback used before an Ollama adapter is enabled."""

from agentic_manufacturing_incident_lab.intake.contracts import (
    IncidentIntake,
    IntakeSource,
    SymptomType,
    intake_from_payload,
)


def build_manual_intake(
    *,
    raw_text: str,
    asset_id: str,
    symptom_type: SymptomType,
    known_asset_ids: tuple[str, ...],
) -> IncidentIntake:
    """Build the same contract from confirmed UI fields without NLP inference."""
    return intake_from_payload(
        raw_text,
        {
            "asset_id": asset_id,
            "symptom_type": symptom_type.value,
            "duration_minutes": None,
            "network_reachable": None,
            "telemetry_available": None,
            "peer_affected": None,
            "parse_confidence": 1.0,
        },
        parser_name="manual_structured_input_v1",
        source=IntakeSource.MANUAL,
        known_asset_ids=known_asset_ids,
    )
