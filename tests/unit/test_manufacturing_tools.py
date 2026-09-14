from agentic_manufacturing_incident_lab.domain import Action, ActionRisk
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_sensor_staleness_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    build_manufacturing_diagnostic_registry,
)


def test_multi_source_tools_return_typed_observations() -> None:
    environment = SimulatedEnvironment(build_sensor_staleness_scenario())
    incident = environment.brief.incident
    registry = build_manufacturing_diagnostic_registry(environment)

    expected_tools = {
        "read_alarm_history",
        "check_connectivity",
        "read_telemetry",
        "inspect_configuration",
        "read_maintenance_record",
        "check_sensor_freshness",
    }
    assert {spec.name for spec in registry.specs} == expected_tools

    values_by_tool = {}
    for sequence, tool_name in enumerate(sorted(expected_tools), start=1):
        response = registry.execute(
            Action(
                action_id=f"ACT-{sequence}",
                incident_id=incident.incident_id,
                tool_name=tool_name,
                rationale="Test one read-only source.",
                risk=ActionRisk.READ_ONLY,
                requested_at=incident.reported_at,
                parameters={"asset_id": incident.asset_id},
            )
        )
        values_by_tool[tool_name] = dict(response.observations[0].values)

    assert values_by_tool["check_connectivity"]["network_reachable"] is True
    assert values_by_tool["read_telemetry"]["telemetry_available"] is True
    assert values_by_tool["inspect_configuration"]["configuration_matches"] is True
    assert values_by_tool["read_maintenance_record"]["maintenance_active"] is False
    assert values_by_tool["check_sensor_freshness"]["sensor_fresh"] is False
    assert "SENSOR_STALE" in values_by_tool["read_alarm_history"]["alarm_codes_csv"]
