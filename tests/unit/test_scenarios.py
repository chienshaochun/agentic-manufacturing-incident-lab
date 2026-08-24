from dataclasses import asdict, replace

import pytest

from agentic_manufacturing_incident_lab.simulation import (
    AssetRole,
    ScenarioDefinition,
    build_station_connectivity_scenario,
)


def test_same_seed_builds_identical_scenario() -> None:
    first = build_station_connectivity_scenario(seed=43)
    second = build_station_connectivity_scenario(seed=43)

    assert first == second


def test_seed_selects_reproducible_affected_station() -> None:
    first = build_station_connectivity_scenario(seed=42)
    second = build_station_connectivity_scenario(seed=43)

    assert first.faulted_asset_id == "ST-01"
    assert second.faulted_asset_id == "ST-02"


def test_scenario_contains_one_failed_station_and_healthy_gateway() -> None:
    scenario = build_station_connectivity_scenario(seed=43)

    failed_stations = [
        asset
        for asset in scenario.assets
        if asset.role is AssetRole.STATION and not asset.network_reachable
    ]
    gateway = scenario.asset_truth("GW-01")

    assert [asset.asset_id for asset in failed_stations] == [scenario.faulted_asset_id]
    assert gateway.role is AssetRole.TELEMETRY_GATEWAY
    assert gateway.network_reachable is True
    assert gateway.telemetry_available is True


def test_agent_brief_excludes_answer_key_and_asset_truth() -> None:
    scenario = build_station_connectivity_scenario(seed=43)
    brief = scenario.to_brief()
    serialized_brief = asdict(brief)

    assert brief.incident.asset_id == "ST-02"
    assert brief.known_asset_ids == ("ST-01", "ST-02", "ST-03", "GW-01")
    assert "faulted_asset_id" not in serialized_brief
    assert "root_cause_code" not in serialized_brief
    assert "assets" not in serialized_brief
    assert "seed" not in serialized_brief


@pytest.mark.parametrize("seed", [-1, True, 1.5])
def test_scenario_builder_rejects_invalid_seed(seed: object) -> None:
    with pytest.raises(ValueError, match="seed must be a non-negative integer"):
        build_station_connectivity_scenario(seed=seed)  # type: ignore[arg-type]


def test_scenario_rejects_duplicate_asset_ids() -> None:
    scenario = build_station_connectivity_scenario(seed=43)

    with pytest.raises(ValueError, match="unique asset_id"):
        replace(scenario, assets=(scenario.assets[0], scenario.assets[0]))


def test_scenario_rejects_unknown_faulted_asset() -> None:
    scenario = build_station_connectivity_scenario(seed=43)

    with pytest.raises(ValueError, match="faulted_asset_id must exist"):
        replace(scenario, faulted_asset_id="ST-99")


def test_unknown_asset_truth_lookup_fails_explicitly() -> None:
    scenario: ScenarioDefinition = build_station_connectivity_scenario(seed=43)

    with pytest.raises(KeyError, match="unknown asset_id: ST-99"):
        scenario.asset_truth("ST-99")
