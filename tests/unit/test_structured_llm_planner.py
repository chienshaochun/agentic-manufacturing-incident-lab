import json

from agentic_manufacturing_incident_lab.agent import (
    ManufacturingSignalPlanner,
    SingleAgentRunner,
    StructuredLLMPlanner,
)
from agentic_manufacturing_incident_lab.domain import TaskStatus
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


def run_with(invoker):
    scenario = build_sensor_staleness_scenario()
    environment = SimulatedEnvironment(scenario)
    fallback = ManufacturingSignalPlanner()
    planner = StructuredLLMPlanner(
        invoker=invoker,
        fallback=fallback,
        provider_name="test-provider",
    )
    return SingleAgentRunner(
        policy=planner,
        registry=build_manufacturing_diagnostic_registry(environment),
        hypothesis_policy=ManufacturingSignalHypothesisPolicy(),
    ).run(
        incident=environment.brief.incident,
        known_asset_ids=environment.brief.known_asset_ids,
    )


def replay_invoker(payload):
    step = len(payload["observations"])
    if step < len(TOOL_ORDER):
        return {
            "decision": "action",
            "tool_name": TOOL_ORDER[step],
            "parameters": {"asset_id": payload["incident"]["asset_id"]},
            "rationale": "Select the next independent diagnostic source.",
        }
    supported = next(
        item for item in payload["hypotheses"] if item["status"] == "supported"
    )
    return {
        "decision": "complete",
        "hypothesis_id": supported["hypothesis_id"],
        "rationale": "Use only the supported hypothesis and its observations.",
    }


def test_structured_replay_completes_without_a_live_llm() -> None:
    run = run_with(replay_invoker)

    assert run.final_state.status is TaskStatus.COMPLETED
    assert tuple(item.action.tool_name for item in run.executions) == TOOL_ORDER
    assert run.evidence[0].claim == "Sensor data on ST-01 is stale."
    assert run.evidence[0].observation_ids[-1].endswith("OBS-006")


def test_unknown_tool_response_falls_back_to_deterministic_planner() -> None:
    def invalid_invoker(_payload):
        return {
            "decision": "action",
            "tool_name": "shutdown_factory",
            "parameters": {},
            "rationale": "Attempt an unavailable operation.",
        }

    run = run_with(invalid_invoker)

    assert run.final_state.status is TaskStatus.COMPLETED
    assert tuple(item.action.tool_name for item in run.executions) == TOOL_ORDER
    assert all(
        item.action.rationale.startswith("Structured LLM fallback")
        for item in run.executions
    )


def test_provider_exception_falls_back_without_exposing_the_error() -> None:
    def raising_invoker(_payload):
        raise TimeoutError("provider unavailable")

    run = run_with(raising_invoker)

    assert run.final_state.status is TaskStatus.COMPLETED
    assert run.executions[0].action.tool_name == "read_alarm_history"
    assert "TimeoutError" in run.executions[0].action.rationale
    assert "provider unavailable" not in run.executions[0].action.rationale


def test_payload_contains_public_contract_but_not_simulator_truth() -> None:
    captured = {}

    def capture_and_stop(payload):
        captured.update(payload)
        return {
            "decision": "stop",
            "reason": "insufficient_evidence",
            "rationale": "No observations have been collected yet.",
        }

    run = run_with(capture_and_stop)
    serialized = json.dumps(captured)

    assert run.final_state.status is TaskStatus.SAFE_STOPPED
    assert captured["contract_version"] == "structured_planner_v1"
    assert len(captured["tools"]) == 6
    assert captured["observations"] == ()
    assert "root_cause" not in serialized
    assert "simulated_sensor_data_staleness" not in serialized


def test_fake_completion_without_supported_hypothesis_uses_fallback() -> None:
    calls = 0

    def premature_complete(_payload):
        nonlocal calls
        calls += 1
        return {
            "decision": "complete",
            "hypothesis_id": "HYP-NOT-OBSERVED",
            "rationale": "Invent a conclusion before collecting evidence.",
        }

    run = run_with(premature_complete)

    assert calls == 7
    assert run.final_state.status is TaskStatus.COMPLETED
    assert run.evidence[0].claim.endswith("stale sensor data on ST-01.")

