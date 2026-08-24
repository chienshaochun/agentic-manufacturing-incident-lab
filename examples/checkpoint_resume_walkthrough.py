"""Pause, save, reload, replay, and resume one deterministic investigation."""

from pathlib import Path
from tempfile import TemporaryDirectory

from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.runtime import load_checkpoint, save_checkpoint
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry
from agentic_manufacturing_incident_lab.workflows import replay_environment_to_run


def make_runner(environment: SimulatedEnvironment) -> SingleAgentRunner:
    return SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
    )


def main() -> None:
    """Demonstrate that a loaded checkpoint continues instead of restarting."""
    scenario = build_station_connectivity_scenario(seed=43)
    first_environment = SimulatedEnvironment(scenario)
    brief = first_environment.brief

    partial = make_runner(first_environment).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
        pause_after_actions=1,
    )
    print("Paused investigation")
    print(f"- status: {partial.final_state.status.value}")
    print(f"- completed actions: {len(partial.executions)}")
    print(f"- latest observation: {partial.observations[-1].summary}")

    with TemporaryDirectory(prefix="agentic-lab-") as temporary_directory:
        checkpoint_path = Path(temporary_directory) / "investigation.checkpoint.json"
        save_checkpoint(checkpoint_path, partial)
        restored = load_checkpoint(checkpoint_path)
        print("Checkpoint")
        print(f"- saved and validated: {checkpoint_path}")
        print(f"- restored memory revision: {restored.final_memory.revision}")

        resumed_environment = replay_environment_to_run(scenario, restored)
        resumed = make_runner(resumed_environment).resume(
            restored,
            known_asset_ids=resumed_environment.brief.known_asset_ids,
        )

    print("Resumed investigation")
    print(f"- status: {resumed.final_state.status.value}")
    print(f"- total actions: {len(resumed.executions)}")
    print(
        "- action IDs: "
        + ", ".join(record.action.action_id for record in resumed.executions)
    )
    print(f"- final memory revision: {resumed.final_memory.revision}")
    print(f"- evidence: {resumed.evidence[0].claim}")


if __name__ == "__main__":
    main()
