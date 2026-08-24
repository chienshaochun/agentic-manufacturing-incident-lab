"""Execute registered diagnostic tools against the simulated environment."""

from datetime import timedelta

from agentic_manufacturing_incident_lab import Action, ActionRisk
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


def main() -> None:
    """Run two allowlisted Actions and print their returned observations."""
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    registry = build_diagnostic_registry(environment)
    incident = environment.brief.incident

    actions = (
        Action(
            action_id="ACT-001",
            incident_id=incident.incident_id,
            tool_name="check_connectivity",
            rationale="Check whether the affected station is reachable.",
            risk=ActionRisk.READ_ONLY,
            requested_at=incident.reported_at + timedelta(seconds=10),
            parameters={"asset_id": "ST-02"},
        ),
        Action(
            action_id="ACT-002",
            incident_id=incident.incident_id,
            tool_name="read_telemetry",
            rationale="Check whether the affected station is reporting telemetry.",
            risk=ActionRisk.READ_ONLY,
            requested_at=incident.reported_at + timedelta(seconds=20),
            parameters={"asset_id": "ST-02"},
        ),
    )

    print("Registered tools")
    for spec in registry.specs:
        print(f"- {spec.name} | risk={spec.risk}")
    print()
    print("Executed actions")
    for action in actions:
        response = registry.execute(action)
        observation = response.observations[0]
        print(f"- {action.action_id} -> {observation.summary}")


if __name__ == "__main__":
    main()
