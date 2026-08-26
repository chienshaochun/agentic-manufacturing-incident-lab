"""Run the Phase 7 benchmark table or inspect one full audit trace."""

import argparse

from agentic_manufacturing_incident_lab.evaluation import (
    build_phase7_benchmark_catalog,
    render_benchmark_summary,
    render_benchmark_trace,
    run_controlled_benchmark,
)


def build_parser(case_ids: tuple[str, ...]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run all Phase 7 controlled cases or render one detailed "
            "multi-agent audit trace."
        )
    )
    parser.add_argument(
        "--case",
        choices=("all", *case_ids),
        default="all",
        help="benchmark case to trace (default: all summary)",
    )
    return parser


def main() -> None:
    catalog = build_phase7_benchmark_catalog()
    case_ids = tuple(case.case_id for case in catalog)
    args = build_parser(case_ids).parse_args()

    if args.case == "all":
        summary = run_controlled_benchmark(catalog)
        print("Phase 7 controlled benchmark")
        print(render_benchmark_summary(summary))
        return

    selected = next(case for case in catalog if case.case_id == args.case)
    summary = run_controlled_benchmark((selected,))
    print(render_benchmark_trace(summary.results[0]))


if __name__ == "__main__":
    main()
