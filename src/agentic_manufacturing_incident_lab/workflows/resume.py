"""Rebuild deterministic simulator state before resuming an agent checkpoint."""

from agentic_manufacturing_incident_lab.runtime.executor import ActionExecutor
from agentic_manufacturing_incident_lab.runtime.run import InvestigationRun
from agentic_manufacturing_incident_lab.simulation import (
    ScenarioDefinition,
    SimulatedEnvironment,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


class ResumeEnvironmentMismatch(ValueError):
    """Raised when a scenario cannot reproduce a checkpoint's prior executions."""


def replay_environment_to_run(
    scenario: ScenarioDefinition,
    run: InvestigationRun,
) -> SimulatedEnvironment:
    """Replay prior actions and return an environment ready for the next action."""
    if scenario.incident != run.incident:
        raise ResumeEnvironmentMismatch(
            "scenario incident does not match the checkpoint incident"
        )

    environment = SimulatedEnvironment(scenario)
    executor = ActionExecutor(build_diagnostic_registry(environment))
    for expected_record in run.executions:
        replayed_record = executor.execute(expected_record.action)
        if replayed_record != expected_record:
            raise ResumeEnvironmentMismatch(
                "scenario replay does not match the checkpoint execution history"
            )
    return environment
