from pathlib import Path

from streamlit.runtime.memory_media_file_storage import _calculate_file_id
from streamlit.testing.v1 import AppTest

from agentic_manufacturing_incident_lab.evaluation import (
    build_phase7_benchmark_catalog,
    run_benchmark_case,
)
from agentic_manufacturing_incident_lab.presentation import (
    build_case_presentation,
    case_report_markdown,
)


APP_PATH = Path(__file__).parents[2] / "streamlit_app.py"


def load_app() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.run()
    assert not app.exception
    return app


def _expected_download_url(data: str, mimetype: str, filename: str) -> str:
    file_id = _calculate_file_id(data.encode(), mimetype, filename)
    extension = Path(filename).suffix
    return f"/mock/media/{file_id}{extension}"


def _default_case_view():
    case = next(
        case
        for case in build_phase7_benchmark_catalog()
        if case.case_id == "isolated-station-seed-43"
    )
    return build_case_presentation(run_benchmark_case(case))


def test_app_loads_incident_workbench_without_running_case() -> None:
    app = load_app()

    assert app.title[0].value == "製造事件調查台"
    assert app.selectbox[0].value == "單一設備無法連線"
    assert len(app.selectbox[0].options) == 4
    assert app.selectbox[1].value == "isolated-station-seed-43"
    assert app.selectbox[1].label == "選擇可重播模擬批次 Simulation batch"
    assert app.button[0].label == "確認並執行調查 Confirm & run"
    assert app.button[0].disabled is False
    assert len(app.checkbox) == 0
    assert len(app.number_input) == 1
    assert len(app.selectbox) == 5
    assert app.text_area[0].value == "單一設備無法連線"
    assert len(app.json) == 1
    assert any("工程師可直接修改" in caption.value for caption in app.caption)
    assert any(expander.label == "技術與稽核資料（JSON）" for expander in app.expander)
    assert any("請選擇症狀與模擬批次" in info.value for info in app.info)
    assert any("answer key 在調查期間對 Agent 隱藏" in caption.value for caption in app.caption)
    assert any("介面版本：Editable Incident Intake v1" in caption.value for caption in app.caption)


def test_run_button_executes_default_case_and_displays_metrics() -> None:
    app = load_app()

    app.button[0].click().run()

    assert not app.exception
    assert any(metric.label == "工作流" for metric in app.metric)
    assert any(metric.value == "completed" for metric in app.metric)
    assert any(metric.label == "安全審查" and metric.value == "approved" for metric in app.metric)
    assert any("調查完成" in success.value for success in app.success)
    assert len(app.get("tab")) == 0
    assert app.toggle[0].value is False
    assert any("目前為精簡展示" in caption.value for caption in app.caption)
    assert any(markdown.value == "#### 關鍵檢查" for markdown in app.markdown)
    assert any(markdown.value == "#### 最終候選原因" for markdown in app.markdown)


def test_operator_can_edit_intake_before_confirming_and_running() -> None:
    app = load_app()
    note = "ST-02 可以 ping，但數值已經三十分鐘沒有更新。"

    app.text_area[0].input(note).run()
    app.number_input[0].set_value(30).run()
    app.selectbox[2].set_value("可以連線").run()
    app.selectbox[3].set_value("沒有更新").run()
    app.selectbox[4].set_value("其他設備正常").run()
    app.button[0].click().run()
    app.toggle[0].set_value(True).run()

    trace = next(code.value for code in app.code if "Benchmark 稽核軌跡" in code.value)
    assert note in trace
    assert "duration_minutes=30" in trace
    assert "network_reachable=True" in trace
    assert "telemetry_available=False" in trace
    assert "peer_affected=False" in trace
    assert any(
        "Hypothesis 不是正式 Evidence" in caption.value
        for caption in app.caption
    )
    assert any("記錄Utility" in caption.value for caption in app.caption)
    assert any(
        "Benchmark 稽核軌跡： isolated-station-seed-43" in code.value
        for code in app.code
    )


def test_case_download_buttons_serve_chinese_markdown_and_trace() -> None:
    app = load_app()
    app.button[0].click().run()
    app.toggle[0].set_value(True).run()
    view = _default_case_view()
    report = case_report_markdown(view)
    displayed_trace = next(
        code.value
        for code in app.code
        if "Benchmark 稽核軌跡" in code.value
    )

    assert "# 事件調查報告" in report
    assert "觀察到的連線故障目前隔離在 ST-02" in report
    assert "Benchmark 稽核軌跡" in view.trace_text
    assert "ST-02 在模擬網路中無法連線" in view.trace_text
    assert "操作員確認的事件內容" in displayed_trace
    assert "Operator-confirmed report" in displayed_trace

    downloads = app.get("download_button")
    report_button = next(
        button for button in downloads if button.label == "下載工程報告 (.md)"
    )
    trace_button = next(
        button for button in downloads if button.label == "下載稽核軌跡 (.txt)"
    )

    assert report_button.proto.url == _expected_download_url(
        report,
        "text/markdown",
        "isolated-station-seed-43-report.md",
    )
    assert trace_button.proto.url == _expected_download_url(
        displayed_trace,
        "text/plain",
        "isolated-station-seed-43-trace.txt",
    )


def test_uncertain_symptom_batch_safe_stops_without_report() -> None:
    app = load_app()

    app.selectbox[0].set_value("設備在線，但製程數值持續平線").run()
    app.selectbox[1].set_value("low-quality-configuration-evidence-seed-120").run()
    app.button[0].click().run()

    assert not app.exception
    assert any("安全停止" in info.value for info in app.info)
    assert any(
        metric.label == "安全審查" and metric.value == "requires_attention"
        for metric in app.metric
    )
    assert any("未產生正式結論" in warning.value for warning in app.warning)
    assert any("目前沒有足以成立的 Evidence" in info.value for info in app.info)


def test_benchmark_dashboard_runs_all_controlled_cases() -> None:
    app = load_app()

    app.radio[0].set_value("基準測試 Benchmark Dashboard").run()
    assert app.title[0].value == "基準測試儀表板"
    assert app.button[0].label == "執行完整 Benchmark"

    app.button[0].click().run(timeout=60)

    assert not app.exception
    assert any(metric.label == "案例數 Cases" and metric.value == "16" for metric in app.metric)
    assert any(metric.label == "通過 Passed" and metric.value == "16" for metric in app.metric)
    assert len(app.dataframe) == 2
    assert len(app.dataframe[0].value) == 16
    assert len(app.dataframe[1].value) == 5
    assert any("所有案例" in success.value for success in app.success)
    assert any("- 案例數： 16" in code.value for code in app.code)


def test_about_page_explains_guarded_optional_llm_boundary() -> None:
    app = load_app()

    app.radio[0].set_value("關於專案 About").run()

    assert not app.exception
    assert app.title[0].value == "關於本實驗室"
    assert "沒有呼叫 LLM 或外部 API" in app.markdown[0].value
    assert "Structured LLM Planner adapter" in app.markdown[0].value
    assert "hypothesis-driven utility policy" in app.markdown[0].value
