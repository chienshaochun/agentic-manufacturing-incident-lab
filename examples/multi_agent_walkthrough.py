"""Run and print the Phase 6 single-agent versus multi-agent comparison."""

import argparse

from agentic_manufacturing_incident_lab.runtime import InvestigationRun
from agentic_manufacturing_incident_lab.simulation import (
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.workflows import (
    AgentComparison,
    run_single_multi_comparison,
)


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _print_diagnostic(label: str, run: InvestigationRun) -> None:
    print(label)
    print(f"- final status: {run.final_state.status.value}")
    print(f"- reason: {run.final_state.reason}")
    print(f"- diagnostic actions: {len(run.executions)}")
    for index, record in enumerate(run.executions, start=1):
        action = record.action
        print(
            f"  {index}. {action.tool_name}({dict(action.parameters)}) "
            f"-> {record.result.status.value}"
        )
        for observation in record.observations:
            print(
                f"     observe: {observation.summary} "
                f"values={dict(observation.values)}"
            )
    print("- evidence:")
    if not run.evidence:
        print("  - none")
    for evidence in run.evidence:
        print(f"  - {evidence.claim} confidence={evidence.confidence:.2f}")
    print()


def _print_handoffs(comparison: AgentComparison) -> None:
    print("Coordinator handoff ledger")
    for index, handoff in enumerate(comparison.multi_run.ledger.handoffs, start=1):
        reply = f" reply_to={handoff.in_reply_to}" if handoff.in_reply_to else ""
        print(
            f"{index}. {handoff.sender.value} -> {handoff.recipient.value} "
            f"| {handoff.kind.value}{reply}"
        )
        print(f"   purpose: {handoff.purpose}")
    print()


def _print_governance(comparison: AgentComparison) -> None:
    print("Multi-agent governance")
    review = comparison.multi_run.safety_review
    if review is None:
        print("- safety review: unavailable")
    else:
        print(f"- safety review: {review.outcome.value}")
        print(f"- rationale: {review.rationale}")
        print("- findings:")
        for finding in review.findings:
            print(f"  - {finding}")

    report = comparison.multi_run.report
    if report is None:
        print("- report: not generated")
    else:
        print(f"- report: {report.report.report_id}")
        print(f"- summary: {report.report.executive_summary}")
        print(f"- conclusion: {report.report.conclusion}")

    print("- collaboration failures:")
    if not comparison.multi_run.failures:
        print("  - none")
    for failure in comparison.multi_run.failures:
        print(
            f"  - {failure.stage.value}/{failure.role.value}/"
            f"{failure.kind.value}: {failure.detail}"
        )
    print()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _print_comparison(comparison: AgentComparison) -> None:
    multi_diagnostic = comparison.multi_diagnostic_run
    multi_status = (
        multi_diagnostic.final_state.status.value
        if multi_diagnostic is not None
        else "unavailable"
    )
    review = comparison.safety_review_outcome

    print("Comparison summary")
    print(f"- single diagnostic status: {comparison.single_status.value}")
    print(f"- multi diagnostic status: {multi_status}")
    print(f"- multi workflow status: {comparison.multi_run.status.value}")
    print(f"- diagnostic status match: {_yes_no(comparison.diagnostic_status_match)}")
    print(f"- action plan match: {_yes_no(comparison.action_plan_match)}")
    print(f"- observation match: {_yes_no(comparison.observation_match)}")
    print(f"- evidence match: {_yes_no(comparison.evidence_match)}")
    print(f"- single diagnostic actions: {comparison.single_action_count}")
    print(
        "- multi diagnostic actions: "
        f"{comparison.multi_diagnostic_action_count}"
    )
    print(f"- diagnostic action delta: {comparison.diagnostic_action_delta:+d}")
    print(f"- coordination handoffs: {comparison.coordination_handoff_count}")
    print(f"- safety review: {review.value if review else 'unavailable'}")
    print(f"- report generated: {_yes_no(comparison.report_generated)}")
    print(
        "- collaboration failures: "
        f"{comparison.collaboration_failure_count}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one deterministic single-agent investigation with the "
            "coordinated Phase 6 multi-agent workflow."
        )
    )
    parser.add_argument(
        "--seed",
        type=_non_negative_int,
        default=43,
        help="deterministic scenario seed (default: 43)",
    )
    parser.add_argument(
        "--action-limit",
        type=_positive_int,
        default=32,
        help=(
            "maximum diagnostic actions per path; use 1 to demonstrate "
            "a reviewed safe stop (default: 32)"
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scenario = build_station_connectivity_scenario(seed=args.seed)
    comparison = run_single_multi_comparison(
        scenario,
        action_limit=args.action_limit,
    )
    incident = comparison.single_run.incident

    print("Phase 6 multi-agent collaboration walkthrough")
    print(f"Scenario: {comparison.scenario_id} | seed={comparison.seed}")
    print(f"Incident: {incident.incident_id} | asset={incident.asset_id}")
    print(f"Goal: {incident.goal}")
    print(f"Diagnostic action limit per path: {args.action_limit}")
    print()

    _print_diagnostic("Single-agent diagnostic path", comparison.single_run)
    if comparison.multi_diagnostic_run is None:
        print("Multi-agent diagnostic path")
        print("- DiagnosticAgent did not return a work product.")
        print()
    else:
        _print_diagnostic(
            "Multi-agent diagnostic path",
            comparison.multi_diagnostic_run,
        )
    _print_handoffs(comparison)
    _print_governance(comparison)
    _print_comparison(comparison)


if __name__ == "__main__":
    main()
