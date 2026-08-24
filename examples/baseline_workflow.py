"""Run the fixed Phase 2 diagnostic SOP from incident to evidence."""

from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.workflows import (
    run_station_connectivity_baseline,
)


def main() -> None:
    """Print the complete deterministic baseline investigation trace."""
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    run = run_station_connectivity_baseline(environment)

    print("Fixed baseline workflow")
    print("Task states:")
    for state in run.task_states:
        print(f"- revision={state.revision} | status={state.status} | {state.reason}")
    print("Actions:")
    for record in run.executions:
        asset_id = record.action.parameters["asset_id"]
        print(
            f"- {record.action.tool_name}({asset_id}) "
            f"-> {record.result.status}"
        )
    print("Evidence:")
    for evidence in run.evidence:
        print(f"- {evidence.claim} | confidence={evidence.confidence:.2f}")


if __name__ == "__main__":
    main()
