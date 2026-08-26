"""Factory functions for reproducible synthetic incident scenarios."""

from datetime import UTC, datetime

from agentic_manufacturing_incident_lab.domain.models import Incident, IncidentSeverity
from agentic_manufacturing_incident_lab.simulation.scenario import (
    AssetRole,
    AssetTruth,
    ScenarioDefinition,
)


def build_station_connectivity_scenario(seed: int = 43) -> ScenarioDefinition:
    """Build a reproducible case with one isolated station connectivity failure."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    station_ids = ("ST-01", "ST-02", "ST-03")
    affected_station = station_ids[seed % len(station_ids)]
    assets = tuple(
        AssetTruth(
            asset_id=station_id,
            role=AssetRole.STATION,
            network_reachable=station_id != affected_station,
            telemetry_available=station_id != affected_station,
            configuration_version="recipe-2026.08",
            alarm_codes=("NETWORK_LINK_DOWN",) if station_id == affected_station else (),
        )
        for station_id in station_ids
    ) + (
        AssetTruth(
            asset_id="GW-01",
            role=AssetRole.TELEMETRY_GATEWAY,
            network_reachable=True,
            telemetry_available=True,
            configuration_version="gateway-2026.08",
        ),
    )

    incident = Incident(
        incident_id=f"INC-CONNECTIVITY-{seed:04d}",
        title="Station telemetry connectivity failure",
        description=f"{affected_station} stopped reporting telemetry to GW-01.",
        asset_id=affected_station,
        severity=IncidentSeverity.WARNING,
        reported_at=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        goal="Determine whether the fault is isolated to a station or shared infrastructure.",
    )

    return ScenarioDefinition(
        scenario_id="station-connectivity-isolation",
        seed=seed,
        title="Isolated station connectivity failure",
        incident=incident,
        assets=assets,
        faulted_asset_id=affected_station,
        root_cause_code="simulated_station_network_interface_down",
    )


def build_shared_connectivity_scenario(seed: int = 73) -> ScenarioDefinition:
    """Build a case where all stations lose shared network infrastructure."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    station_ids = ("ST-01", "ST-02", "ST-03")
    affected_station = station_ids[seed % len(station_ids)]
    assets = tuple(
        AssetTruth(
            asset_id=station_id,
            role=AssetRole.STATION,
            network_reachable=False,
            telemetry_available=False,
            configuration_version="recipe-2026.08",
            alarm_codes=("NETWORK_UPLINK_DOWN",),
        )
        for station_id in station_ids
    ) + (
        AssetTruth(
            asset_id="GW-01",
            role=AssetRole.TELEMETRY_GATEWAY,
            network_reachable=False,
            telemetry_available=False,
            configuration_version="gateway-2026.08",
            alarm_codes=("SHARED_NETWORK_DOWN",),
        ),
    )
    incident = Incident(
        incident_id=f"INC-SHARED-CONNECTIVITY-{seed:04d}",
        title="Multiple stations lost connectivity",
        description=(
            f"{affected_station} and peer stations stopped reporting to GW-01."
        ),
        asset_id=affected_station,
        severity=IncidentSeverity.CRITICAL,
        reported_at=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
        goal=(
            "Determine whether the reported station fault is isolated or shared "
            "infrastructure is affected."
        ),
    )
    return ScenarioDefinition(
        scenario_id="station-connectivity-shared-infrastructure",
        seed=seed,
        title="Shared station connectivity failure",
        incident=incident,
        assets=assets,
        faulted_asset_id="GW-01",
        root_cause_code="simulated_shared_network_gateway_down",
    )


def build_telemetry_path_scenario(seed: int = 91) -> ScenarioDefinition:
    """Build an ambiguous case with healthy connectivity but missing telemetry."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    station_ids = ("ST-01", "ST-02", "ST-03")
    affected_station = station_ids[seed % len(station_ids)]
    assets = tuple(
        AssetTruth(
            asset_id=station_id,
            role=AssetRole.STATION,
            network_reachable=True,
            telemetry_available=station_id != affected_station,
            configuration_version="recipe-2026.08",
            alarm_codes=("TELEMETRY_MISSING",)
            if station_id == affected_station
            else (),
        )
        for station_id in station_ids
    ) + (
        AssetTruth(
            asset_id="GW-01",
            role=AssetRole.TELEMETRY_GATEWAY,
            network_reachable=True,
            telemetry_available=True,
            configuration_version="gateway-2026.08",
        ),
    )
    incident = Incident(
        incident_id=f"INC-TELEMETRY-PATH-{seed:04d}",
        title="Station telemetry path failure",
        description=(
            f"{affected_station} remains reachable but stopped sending telemetry."
        ),
        asset_id=affected_station,
        severity=IncidentSeverity.WARNING,
        reported_at=datetime(2026, 8, 24, 11, 0, tzinfo=UTC),
        goal="Determine whether read-only evidence can localize the telemetry failure.",
    )
    return ScenarioDefinition(
        scenario_id="station-telemetry-path-ambiguous",
        seed=seed,
        title="Ambiguous station telemetry-path failure",
        incident=incident,
        assets=assets,
        faulted_asset_id=affected_station,
        root_cause_code="simulated_station_telemetry_path_failure",
    )
