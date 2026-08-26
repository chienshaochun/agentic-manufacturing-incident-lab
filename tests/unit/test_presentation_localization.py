from agentic_manufacturing_incident_lab.presentation.localization import (
    localize_benchmark_summary,
    localize_text,
    localize_trace,
)


def test_localize_text_translates_dynamic_station_sentences() -> None:
    assert localize_text(
        "The observed connectivity failure is isolated to ST-02."
    ) == "觀察到的連線故障目前隔離在 ST-02。"
    assert localize_text(
        "ST-03 is unreachable on the simulated network."
    ) == "ST-03 在模擬網路中無法連線。"
    assert localize_text(
        "Telemetry for ST-01 is available."
    ) == "ST-01 的 Telemetry 可用。"


def test_localize_trace_preserves_identifiers_and_status_values() -> None:
    trace = "\n".join(
        (
            "Benchmark trace: isolated-station-seed-43",
            "Incident: INC-CONNECTIVITY-0043",
            "Workflow status: completed",
            "  stage: reporting",
            "  detail: RuntimeError: injected reporter failure",
        )
    )

    localized = localize_trace(trace)

    assert "Benchmark 稽核軌跡： isolated-station-seed-43" in localized
    assert "事件： INC-CONNECTIVITY-0043" in localized
    assert "工作流狀態： completed" in localized
    assert "階段： reporting" in localized
    assert "RuntimeError：注入的 Reporter Agent 故障" in localized


def test_localize_benchmark_summary_translates_aggregate_labels() -> None:
    summary = "\n".join(
        (
            "Aggregate:",
            "- cases: 11",
            "- passed: 11",
            "- all passed: yes",
        )
    )

    localized = localize_benchmark_summary(summary)

    assert "彙總結果:" in localized
    assert "- 案例數： 11" in localized
    assert "- 通過案例： 11" in localized
    assert "- 是否全部通過： yes" in localized
