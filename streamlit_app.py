"""Interactive Streamlit workbench for the controlled incident lab."""

from dataclasses import asdict
import json

import streamlit as st

from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkCaseResult,
    build_phase7_benchmark_catalog,
    run_benchmark_case,
    run_phase7_benchmark,
)
from agentic_manufacturing_incident_lab.presentation import (
    BenchmarkPresentation,
    CasePresentation,
    build_benchmark_presentation,
    build_case_presentation,
)


CASE_LABELS = {
    "isolated-station-seed-42": "Isolated station fault — ST-01",
    "isolated-station-seed-43": "Isolated station fault — ST-02",
    "isolated-station-seed-44": "Isolated station fault — ST-03",
    "shared-infrastructure-seed-73": "Shared infrastructure ambiguity",
    "telemetry-path-seed-91": "Telemetry-path ambiguity",
    "action-budget-safe-stop-seed-43": "Action budget safe stop",
    "diagnostic-exception-seed-43": "Diagnostic Agent exception",
    "diagnostic-invalid-response-seed-43": "Diagnostic invalid response",
    "safety-reviewer-exception-seed-43": "Safety Reviewer exception",
    "reporter-exception-seed-43": "Reporter Agent exception",
    "contradictory-approval-seed-43": "Contradictory safety approval",
}


def _metric_grid(metrics) -> None:
    columns = st.columns(4)
    for index, metric in enumerate(metrics):
        columns[index % len(columns)].metric(
            metric.label,
            metric.value,
            help=metric.help_text,
            border=True,
        )


def _case_lookup():
    return {case.case_id: case for case in build_phase7_benchmark_catalog()}


def _run_selected_case(case_id: str) -> None:
    case = _case_lookup()[case_id]
    with st.spinner("Running deterministic multi-agent investigation..."):
        result = run_benchmark_case(case)
    st.session_state["case_result"] = result


def _current_case_result(case_id: str) -> BenchmarkCaseResult | None:
    result = st.session_state.get("case_result")
    if isinstance(result, BenchmarkCaseResult) and result.case_id == case_id:
        return result
    return None


def _run_full_benchmark() -> None:
    with st.spinner("Running all controlled benchmark cases..."):
        summary = run_phase7_benchmark()
    st.session_state["benchmark_view"] = build_benchmark_presentation(summary)


def _current_benchmark_view() -> BenchmarkPresentation | None:
    view = st.session_state.get("benchmark_view")
    return view if isinstance(view, BenchmarkPresentation) else None


def _render_case_status(view: CasePresentation) -> None:
    if view.passed and view.workflow_status == "completed":
        st.success("Investigation completed with approved, evidence-bound output.")
    elif view.passed and view.failures:
        st.warning(
            "The workflow safely contained the injected collaboration failure."
        )
    elif view.passed:
        st.info(
            "The workflow safely stopped because the available evidence was "
            "insufficient for a report."
        )
    else:
        st.error("The run did not satisfy the controlled benchmark expectation.")


def _render_case_details(view: CasePresentation) -> None:
    st.subheader("Investigation overview")
    _metric_grid(view.metrics)
    _render_case_status(view)
    handoff_tab, action_tab, evidence_tab, outcome_tab, trace_tab = st.tabs(
        (
            "Handoffs",
            "Actions & attempts",
            "Evidence & safety",
            "Report & failures",
            "Raw trace",
        )
    )

    with handoff_tab:
        st.markdown("#### Coordinator handoff ledger")
        st.caption(
            "Every request and response crossing an Agent responsibility boundary."
        )
        st.dataframe(
            [asdict(handoff) for handoff in view.handoffs],
            hide_index=True,
            width="stretch",
        )

    with action_tab:
        st.markdown("#### Diagnostic actions and physical attempts")
        st.caption(
            "One logical Action may contain multiple physical attempts when retrying."
        )
        if view.action_attempts:
            st.dataframe(
                [asdict(attempt) for attempt in view.action_attempts],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("DiagnosticAgent returned no executable work product.")

    with evidence_tab:
        st.markdown("#### Evidence")
        if view.evidence:
            st.dataframe(
                [asdict(evidence) for evidence in view.evidence],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No evidence claim was created for this case.")

        st.markdown("#### Independent safety review")
        if view.safety is None:
            st.warning("Safety Reviewer did not return a work product.")
        else:
            if view.safety.outcome == "approved":
                st.success(f"Safety outcome: {view.safety.outcome}")
            else:
                st.warning(f"Safety outcome: {view.safety.outcome}")
            st.write(view.safety.rationale)
            for finding in view.safety.findings:
                st.markdown(f"- {finding}")

    with outcome_tab:
        st.markdown("#### Evidence-bound report")
        if view.report is None:
            st.info("No formal report was generated for this run.")
        else:
            st.markdown(f"**{view.report.title}**")
            st.write(view.report.executive_summary)
            st.markdown(f"**Conclusion:** {view.report.conclusion}")
            st.caption(f"Evidence records: {view.report.evidence_ids}")

        st.markdown("#### Collaboration failures")
        if view.failures:
            st.dataframe(
                [asdict(failure) for failure in view.failures],
                hide_index=True,
                width="stretch",
            )
        else:
            st.success("No collaboration failure was recorded.")

    with trace_tab:
        st.markdown("#### Complete deterministic audit trace")
        st.code(view.trace_text, language="text", line_numbers=True)


def _incident_workbench() -> None:
    st.title("Manufacturing Incident Workbench")
    st.caption(
        "Run one controlled incident through Coordinator, Diagnostic, "
        "Safety Reviewer, and Reporter roles."
    )
    cases = _case_lookup()
    case_ids = tuple(cases)
    default_index = case_ids.index("isolated-station-seed-43")
    selected_id = st.selectbox(
        "Benchmark case",
        options=case_ids,
        index=default_index,
        format_func=lambda case_id: CASE_LABELS[case_id],
        help="Each case binds a deterministic scenario to an expected safe outcome.",
    )
    selected = cases[selected_id]
    incident = selected.scenario.incident
    st.markdown(f"**Incident:** `{incident.incident_id}` — {incident.title}")
    st.markdown(
        f"**Asset:** `{incident.asset_id}` · **Severity:** `{incident.severity.value}`"
    )
    st.markdown(f"**Goal:** {incident.goal}")
    st.caption(
        f"Scenario: {selected.scenario.scenario_id} · seed={selected.scenario.seed} "
        f"· action limit={selected.action_limit} · fault profile="
        f"{selected.specialist_fault.value}"
    )

    if st.button(
        "Run investigation",
        type="primary",
        width="stretch",
        icon=":material/play_arrow:",
    ):
        _run_selected_case(selected_id)

    result = _current_case_result(selected_id)
    if result is None:
        st.info("Select a case and run the investigation to view its results.")
        return
    _render_case_details(build_case_presentation(result))


def _benchmark_dashboard() -> None:
    st.title("Benchmark Dashboard")
    st.caption(
        "Evaluate normal, ambiguous, resource-limited, and injected-failure "
        "paths against the same deterministic acceptance gates."
    )
    if st.button(
        "Run full benchmark",
        type="primary",
        width="stretch",
        icon=":material/speed:",
    ):
        _run_full_benchmark()

    view = _current_benchmark_view()
    if view is None:
        st.info("Run the benchmark to compare all 11 controlled cases.")
        return

    _metric_grid(view.metrics)
    if all(row.passed for row in view.rows):
        st.success("All controlled correctness, safety, and resource gates passed.")
    else:
        failed_count = sum(not row.passed for row in view.rows)
        st.error(f"{failed_count} benchmark case(s) did not pass every gate.")

    st.subheader("Case comparison")
    st.dataframe(
        [asdict(row) for row in view.rows],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Aggregate text summary"):
        st.code(view.summary_text, language="text")


def _about() -> None:
    st.title("About this lab")
    st.markdown(
        """
This is a deterministic learning lab for safe Agentic AI in manufacturing
incident response. It uses synthetic scenarios, bounded tools, structured
handoffs, independent safety review, evidence-bound reports, and controlled
benchmarks.

The current planner is rule-based. No LLM, external API, production equipment,
or confidential factory data is used.
"""
    )


def main() -> None:
    st.set_page_config(
        page_title="Agentic Incident Lab",
        page_icon=":material/precision_manufacturing:",
        layout="wide",
    )
    st.sidebar.title("Agentic Incident Lab")
    page = st.sidebar.radio(
        "Workspace",
        ("Incident Workbench", "Benchmark Dashboard", "About"),
    )
    st.sidebar.caption(
        "Deterministic · synthetic data · read-only diagnostics · no LLM"
    )

    if page == "Incident Workbench":
        _incident_workbench()
    elif page == "Benchmark Dashboard":
        _benchmark_dashboard()
    else:
        _about()


if __name__ == "__main__":
    main()
