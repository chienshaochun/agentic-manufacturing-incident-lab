import hashlib
import json

import pytest

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.runtime import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    deserialize_checkpoint,
    load_checkpoint,
    save_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry
from agentic_manufacturing_incident_lab.workflows import (
    run_station_connectivity_baseline,
)


def run_agent():
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    return SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )


def rewrite_checksum(envelope: dict) -> str:
    canonical = json.dumps(
        envelope["run"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    envelope["payload_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return json.dumps(envelope)


def test_complete_agent_run_round_trips_exactly() -> None:
    original = run_agent()

    restored = deserialize_checkpoint(serialize_checkpoint(original))

    assert restored == original
    assert restored.final_memory == original.final_memory


def test_baseline_without_memory_round_trips_exactly() -> None:
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    original = run_station_connectivity_baseline(environment)

    restored = deserialize_checkpoint(serialize_checkpoint(original))

    assert restored == original
    assert restored.memory_states == ()


def test_serialization_is_deterministic_for_same_run() -> None:
    run = run_agent()

    assert serialize_checkpoint(run) == serialize_checkpoint(run)


def test_checkpoint_schema_tracks_attempt_history_format() -> None:
    envelope = json.loads(serialize_checkpoint(run_agent()))

    assert CHECKPOINT_SCHEMA_VERSION == 3
    assert envelope["schema_version"] == 3
    assert "attempts" in envelope["run"]["executions"][0]


def test_checkpoint_file_save_and_load_round_trip(tmp_path) -> None:
    original = run_agent()
    destination = tmp_path / "investigation.checkpoint.json"

    resolved = save_checkpoint(destination, original)
    restored = load_checkpoint(destination)

    assert resolved == destination.resolve()
    assert restored == original


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(CheckpointError, match="invalid checkpoint JSON"):
        deserialize_checkpoint("{not-json}")


def test_duplicate_json_key_is_rejected() -> None:
    with pytest.raises(CheckpointError, match="duplicate JSON key"):
        deserialize_checkpoint('{"kind": "one", "kind": "two"}')


def test_unsupported_schema_version_is_rejected() -> None:
    envelope = json.loads(serialize_checkpoint(run_agent()))
    envelope["schema_version"] = 99

    with pytest.raises(CheckpointError, match="unsupported checkpoint schema"):
        deserialize_checkpoint(json.dumps(envelope))


def test_tampered_payload_is_rejected_by_checksum() -> None:
    envelope = json.loads(serialize_checkpoint(run_agent()))
    envelope["run"]["incident"]["title"] = "Tampered title"

    with pytest.raises(CheckpointError, match="checksum mismatch"):
        deserialize_checkpoint(json.dumps(envelope))


def test_unknown_payload_field_is_rejected_after_valid_checksum() -> None:
    envelope = json.loads(serialize_checkpoint(run_agent()))
    envelope["run"]["unexpected"] = True

    with pytest.raises(CheckpointError, match="unknown fields"):
        deserialize_checkpoint(rewrite_checksum(envelope))


def test_invalid_enum_is_rejected_after_valid_checksum() -> None:
    envelope = json.loads(serialize_checkpoint(run_agent()))
    envelope["run"]["task_states"][0]["status"] = "invented_status"

    with pytest.raises(CheckpointError, match="invalid status"):
        deserialize_checkpoint(rewrite_checksum(envelope))


def test_restored_action_parameters_remain_immutable() -> None:
    restored = deserialize_checkpoint(serialize_checkpoint(run_agent()))

    with pytest.raises(TypeError):
        restored.executions[0].action.parameters["asset_id"] = "ST-99"  # type: ignore[index]


def test_missing_checkpoint_file_is_reported_as_checkpoint_error(tmp_path) -> None:
    with pytest.raises(CheckpointError, match="could not read checkpoint"):
        load_checkpoint(tmp_path / "missing.json")


def test_checkpoint_write_failure_is_reported_as_checkpoint_error(tmp_path) -> None:
    destination = tmp_path / "missing-directory" / "checkpoint.json"

    with pytest.raises(CheckpointError, match="could not write checkpoint"):
        save_checkpoint(destination, run_agent())
