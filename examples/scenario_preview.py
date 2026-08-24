"""Compare the agent-visible scenario brief with the evaluator answer key."""

from agentic_manufacturing_incident_lab.simulation import (
    build_station_connectivity_scenario,
)


def main() -> None:
    """Print both views to demonstrate the intended information boundary."""
    scenario = build_station_connectivity_scenario(seed=43)
    brief = scenario.to_brief()
    faulted_asset = scenario.asset_truth(scenario.faulted_asset_id)

    print("Agent-visible brief")
    print(f"Scenario: {brief.scenario_id}")
    print(f"Incident: {brief.incident.description}")
    print(f"Known assets: {', '.join(brief.known_asset_ids)}")
    print()
    print("Evaluator-only answer key")
    print(f"Faulted asset: {scenario.faulted_asset_id}")
    print(f"Root cause: {scenario.root_cause_code}")
    print(f"Network reachable: {faulted_asset.network_reachable}")


if __name__ == "__main__":
    main()
