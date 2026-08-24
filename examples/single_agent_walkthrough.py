"""Run and print the Phase 3 single-agent investigation trace."""

from agentic_manufacturing_incident_lab.agent import (
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


def main() -> None:
    """Run one deterministic agent investigation and print its audit trail."""
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)
    registry = build_diagnostic_registry(environment)
    policy = RuleBasedPlanner()
    brief = environment.brief

    run = SingleAgentRunner(policy=policy, registry=registry).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    print("Single-agent investigation")
    print(f"Scenario: {brief.scenario_id} | seed={scenario.seed}")
    print(f"Incident: {brief.incident.incident_id} | asset={brief.incident.asset_id}")
    print(f"Goal: {brief.incident.goal}")
    print(f"Policy: {policy.name}")
    print()

    print("Agent actions and observations:")
    for step, record in enumerate(run.executions, start=1):
        action = record.action
        print(
            f"{step}. PLAN  {action.rationale}\n"
            f"   ACT   {action.tool_name}({dict(action.parameters)}) "
            f"risk={action.risk.value}\n"
            f"   RESULT {record.result.status.value}: {record.result.summary}"
        )
        for observation in record.observations:
            print(
                f"   OBSERVE {observation.observation_id}: {observation.summary} "
                f"values={dict(observation.values)}"
            )
        print()

    print("Task states:")
    for state in run.task_states:
        print(
            f"- revision={state.revision} | status={state.status.value} "
            f"| {state.reason}"
        )

    print("Evidence:")
    if not run.evidence:
        print("- none")
    for evidence in run.evidence:
        print(f"- claim: {evidence.claim}")
        print(f"  confidence: {evidence.confidence:.2f}")
        print(f"  observations: {', '.join(evidence.observation_ids)}")

    print("Working memory:")
    memory = run.final_memory
    if memory is None:
        print("- none")
        return
    print(f"- revision: {memory.revision}")
    print(
        f"- action budget: used={memory.step_budget.actions_used} "
        f"remaining={memory.step_budget.actions_remaining} "
        f"limit={memory.step_budget.action_limit}"
    )
    print("- facts:")
    for fact in memory.facts:
        print(f"  - {fact.statement} [{', '.join(fact.observation_ids)}]")
    print("- open questions:")
    if not memory.open_questions:
        print("  - none")
    for question in memory.open_questions:
        print(f"  - {question.prompt}")


if __name__ == "__main__":
    main()
