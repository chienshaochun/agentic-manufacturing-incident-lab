from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.intake import (
    IncidentTextParser,
    IntakeSource,
    SymptomType,
    build_manual_intake,
    incident_intake_json_schema,
    intake_from_payload,
)


KNOWN_ASSETS = ("ST-01", "ST-02", "ST-03", "GW-01")


def valid_payload() -> dict[str, object]:
    return {
        "asset_id": "ST-02",
        "symptom_type": "telemetry_missing",
        "duration_minutes": 30,
        "network_reachable": True,
        "telemetry_available": False,
        "peer_affected": False,
        "parse_confidence": 0.91,
    }


def test_strict_payload_builds_validated_intake() -> None:
    intake = intake_from_payload(
        "ST-02 ping 得到，但三十分鐘沒有數值。",
        valid_payload(),
        parser_name="future_ollama_parser",
        source=IntakeSource.OLLAMA,
        known_asset_ids=KNOWN_ASSETS,
    )

    assert intake.asset_id == "ST-02"
    assert intake.symptom_type is SymptomType.TELEMETRY_MISSING
    assert intake.duration_minutes == 30
    assert intake.network_reachable is True
    assert intake.telemetry_available is False
    assert intake.parse_confidence == 0.91


def test_schema_is_strict_and_lists_only_observable_symptoms() -> None:
    schema = incident_intake_json_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    symptom_schema = schema["properties"]["symptom_type"]
    assert symptom_schema["enum"] == [item.value for item in SymptomType]
    assert "sensor_staleness" not in symptom_schema["enum"]
    assert "configuration_drift" not in symptom_schema["enum"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"asset_id": "ST-99"}, "known asset"),
        ({"symptom_type": "configuration_drift"}, "not allowlisted"),
        ({"duration_minutes": -1}, "non-negative integer"),
        ({"network_reachable": "yes"}, "boolean or None"),
        ({"parse_confidence": 1.1}, "between 0.0 and 1.0"),
    ],
)
def test_payload_rejects_invalid_or_root_cause_values(
    change: dict[str, object],
    message: str,
) -> None:
    payload = valid_payload() | change

    with pytest.raises(ValueError, match=message):
        intake_from_payload(
            "設備異常",
            payload,
            parser_name="parser",
            source=IntakeSource.OLLAMA,
            known_asset_ids=KNOWN_ASSETS,
        )


def test_payload_rejects_missing_and_unknown_fields() -> None:
    missing = valid_payload()
    missing.pop("peer_affected")
    unknown = valid_payload() | {"root_cause": "sensor"}

    with pytest.raises(ValueError, match="fields mismatch"):
        intake_from_payload(
            "設備異常",
            missing,
            parser_name="parser",
            source=IntakeSource.OLLAMA,
            known_asset_ids=KNOWN_ASSETS,
        )
    with pytest.raises(ValueError, match="fields mismatch"):
        intake_from_payload(
            "設備異常",
            unknown,
            parser_name="parser",
            source=IntakeSource.OLLAMA,
            known_asset_ids=KNOWN_ASSETS,
        )


def test_manual_fallback_uses_same_contract_without_claiming_nlp() -> None:
    intake = build_manual_intake(
        raw_text="設備在線，但製程值沒有變化。",
        asset_id="ST-01",
        symptom_type=SymptomType.PROCESS_SIGNAL_FLATLINE,
        known_asset_ids=KNOWN_ASSETS,
    )

    assert intake.source is IntakeSource.MANUAL
    assert intake.parser_name == "manual_structured_input_v1"
    assert intake.parse_confidence == 1.0
    assert intake.network_reachable is None


def test_protocol_accepts_future_parser_shape() -> None:
    class Parser:
        name = "test_parser"

        def parse(self, raw_text: str, *, known_asset_ids: tuple[str, ...]):
            return build_manual_intake(
                raw_text=raw_text,
                asset_id=known_asset_ids[0],
                symptom_type=SymptomType.STATION_UNREACHABLE,
                known_asset_ids=known_asset_ids,
            )

    assert isinstance(Parser(), IncidentTextParser)


@pytest.mark.parametrize("value", [-0.1, 1.1, True])
def test_intake_rejects_invalid_confidence(value: object) -> None:
    intake = build_manual_intake(
        raw_text="設備異常",
        asset_id="ST-01",
        symptom_type=SymptomType.STATION_UNREACHABLE,
        known_asset_ids=KNOWN_ASSETS,
    )

    with pytest.raises(ValueError, match="parse_confidence"):
        replace(intake, parse_confidence=value)  # type: ignore[arg-type]
