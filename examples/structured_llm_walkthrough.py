"""Demonstrate structured planner responses without a live LLM provider."""

import argparse

from agentic_manufacturing_incident_lab.agent import (
    ManufacturingSignalPlanner,
    SingleAgentRunner,
    StructuredLLMPlanner,
)
from agentic_manufacturing_incident_lab.hypotheses import (
    ManufacturingSignalHypothesisPolicy,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_sensor_staleness_scenario,
)
from agentic_manufacturing_incident_lab.tools import (
    build_manufacturing_diagnostic_registry,
)


TOOL_ORDER = (
    "read_alarm_history",
    "check_connectivity",
    "read_telemetry",
    "inspect_configuration",
    "read_maintenance_record",
    "check_sensor_freshness",
)


def replay_response(payload):
    """Return recorded contract-valid responses as a no-network LLM stand-in."""
    step = len(payload["observations"])
    if step < len(TOOL_ORDER):
        return {
            "decision": "action",
            "tool_name": TOOL_ORDER[step],
            "parameters": {"asset_id": payload["incident"]["asset_id"]},
            "rationale": "Recorded structured proposal for the next data source.",
        }
    supported = next(
        item for item in payload["hypotheses"] if item["status"] == "supported"
    )
    return {
        "decision": "complete",
        "hypothesis_id": supported["hypothesis_id"],
        "rationale": "Recorded completion selects an existing supported hypothesis.",
    }


def invalid_response(_payload):
    """Simulate an unsafe provider proposal to exercise deterministic fallback."""
    return {
        "decision": "action",
        "tool_name": "shutdown_factory",
        "parameters": {},
        "rationale": "This tool is not allowlisted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "invalid"), default="replay")
    args = parser.parse_args()

    scenario = build_sensor_staleness_scenario()
    environment = SimulatedEnvironment(scenario)
    planner = StructuredLLMPlanner(
        invoker=replay_response if args.mode == "replay" else invalid_response,
        fallback=ManufacturingSignalPlanner(),
        provider_name=f"offline-{args.mode}",
    )
    run = SingleAgentRunner(
        policy=planner,
        registry=build_manufacturing_diagnostic_registry(environment),
        hypothesis_policy=ManufacturingSignalHypothesisPolicy(),
    ).run(
        incident=environment.brief.incident,
        known_asset_ids=environment.brief.known_asset_ids,
    )

    print(f"Mode: {args.mode}")
    print(f"Status: {run.final_state.status.value}")
    for sequence, record in enumerate(run.executions, start=1):
        print(f"{sequence}. {record.action.tool_name}: {record.action.rationale}")
    print(f"Evidence: {run.evidence[0].claim if run.evidence else 'none'}")


if __name__ == "__main__":
    main()

