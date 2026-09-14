"""Factory functions for reproducible synthetic incident scenarios."""

from dataclasses import replace
from datetime import UTC, datetime

from agentic_manufacturing_incident_lab.domain.models import Incident, IncidentSeverity
from agentic_manufacturing_incident_lab.simulation.scenario import (
    AssetRole,
    AssetTruth,
    ScenarioDefinition,
    SourceQualityProfile,
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


def _build_flatline_scenario(*, seed: int, configuration_drift: bool) -> ScenarioDefinition:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    station_ids = ("ST-01", "ST-02", "ST-03")
    affected_station = station_ids[seed % len(station_ids)]
    assets = tuple(
        AssetTruth(
            asset_id=station_id,
            role=AssetRole.STATION,
            network_reachable=True,
            telemetry_available=True,
            configuration_version=(
                "recipe-2026.07"
                if configuration_drift and station_id == affected_station
                else "recipe-2026.08"
            ),
            expected_configuration_version="recipe-2026.08",
            sensor_fresh=(
                configuration_drift or station_id != affected_station
            ),
            sensor_age_seconds=(
                0 if configuration_drift or station_id != affected_station else 1860
            ),
            maintenance_active=False,
            alarm_codes=(
                ("CONFIG_VERSION_MISMATCH", "PROCESS_SIGNAL_FLATLINE")
                if configuration_drift and station_id == affected_station
                else (
                    ("SENSOR_STALE", "PROCESS_SIGNAL_FLATLINE")
                    if station_id == affected_station
                    else ()
                )
            ),
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
    cause = "configuration-drift" if configuration_drift else "sensor-staleness"
    incident = Incident(
        incident_id=f"INC-SIGNAL-{seed:04d}",
        title="Process signal stopped changing",
        description=(
            f"{affected_station} remains online, but its process value has been "
            "flat for more than 30 minutes."
        ),
        asset_id=affected_station,
        severity=IncidentSeverity.WARNING,
        reported_at=datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
        goal=(
            "Distinguish sensor staleness, configuration drift, planned maintenance, "
            "and transport-path failures."
        ),
    )
    return ScenarioDefinition(
        scenario_id=f"manufacturing-signal-flatline-{cause}",
        seed=seed,
        title=f"Process signal flatline caused by {cause}",
        incident=incident,
        assets=assets,
        faulted_asset_id=affected_station,
        root_cause_code=(
            "simulated_configuration_drift"
            if configuration_drift
            else "simulated_sensor_data_staleness"
        ),
    )


def build_sensor_staleness_scenario(seed: int = 117) -> ScenarioDefinition:
    """Build a flatline case caused by a stale sensor stream."""
    return _build_flatline_scenario(seed=seed, configuration_drift=False)


def build_configuration_drift_scenario(seed: int = 118) -> ScenarioDefinition:
    """Build the same symptom with a mismatched recipe configuration."""
    return _build_flatline_scenario(seed=seed, configuration_drift=True)


def _replace_affected_asset(
    scenario: ScenarioDefinition,
    **changes,
) -> tuple[AssetTruth, ...]:
    return tuple(
        replace(asset, **changes)
        if asset.asset_id == scenario.incident.asset_id
        else asset
        for asset in scenario.assets
    )


def build_conflicting_sensor_signal_scenario(seed: int = 119) -> ScenarioDefinition:
    """Build a stale-sensor alarm contradicted by a fresh direct measurement."""
    base = build_sensor_staleness_scenario(seed=seed)
    return replace(
        base,
        scenario_id="manufacturing-signal-flatline-conflicting-sensor-data",
        title="Process signal flatline with conflicting sensor evidence",
        assets=_replace_affected_asset(
            base,
            sensor_fresh=True,
            sensor_age_seconds=0,
        ),
        root_cause_code="simulated_alarm_sensor_measurement_conflict",
    )


def build_low_quality_configuration_scenario(seed: int = 120) -> ScenarioDefinition:
    """Build configuration drift whose direct store observation is too stale."""
    base = build_configuration_drift_scenario(seed=seed)
    return replace(
        base,
        scenario_id="manufacturing-signal-flatline-low-quality-configuration",
        title="Process signal flatline with stale configuration evidence",
        source_quality_profiles=(
            SourceQualityProfile(
                source="simulated_configuration_store",
                freshness=0.40,
            ),
        ),
        root_cause_code="simulated_unconfirmed_configuration_drift",
    )


def build_multi_cause_flatline_scenario(seed: int = 121) -> ScenarioDefinition:
    """Build simultaneous sensor staleness and configuration drift evidence."""
    base = build_configuration_drift_scenario(seed=seed)
    return replace(
        base,
        scenario_id="manufacturing-signal-flatline-multiple-supported-causes",
        title="Process signal flatline with multiple supported causes",
        assets=_replace_affected_asset(
            base,
            sensor_fresh=False,
            sensor_age_seconds=1860,
            alarm_codes=(
                "CONFIG_VERSION_MISMATCH",
                "SENSOR_STALE",
                "PROCESS_SIGNAL_FLATLINE",
            ),
        ),
        root_cause_code="simulated_multiple_concurrent_causes",
    )
