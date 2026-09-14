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
    assert app.selectbox[0].value == "設備無法連線或遙測中斷"
    assert app.selectbox[1].value == "isolated-station-seed-43"
    assert app.selectbox[1].label == "選擇可重播模擬批次 Simulation batch"
    assert app.button[0].label == "執行調查 Run investigation"
    assert any("請選擇症狀與模擬批次" in info.value for info in app.info)
    assert any("answer key 在調查期間對 Agent 隱藏" in caption.value for caption in app.caption)
    assert any("介面版本：Investigation Reasoning UX v1" in caption.value for caption in app.caption)


def test_run_button_executes_default_case_and_displays_metrics() -> None:
    app = load_app()

    app.button[0].click().run()

    assert not app.exception
    assert any(metric.label == "工作流 Workflow" for metric in app.metric)
    assert any(metric.value == "completed" for metric in app.metric)
    assert any(metric.label == "基準結果 Benchmark" for metric in app.metric)
    assert any(metric.value == "PASS" for metric in app.metric)
    assert any("調查完成" in success.value for success in app.success)
    assert len(app.get("tab")) == 6
    assert len(app.dataframe) == 7
    assert any("每取得一筆新 Observation" in caption.value for caption in app.caption)
    assert len(app.dataframe[1].value) == 4
    assert any("Utility = Information" in caption.value for caption in app.caption)
    assert any("Planner 候選決策" in code.value for code in app.code)
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
    view = _default_case_view()
    report = case_report_markdown(view)

    assert "# 事件調查報告" in report
    assert "觀察到的連線故障目前隔離在 ST-02" in report
    assert "Benchmark 稽核軌跡" in view.trace_text
    assert "ST-02 在模擬網路中無法連線" in view.trace_text

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
        view.trace_text,
        "text/plain",
        "isolated-station-seed-43-trace.txt",
    )


def test_uncertain_symptom_batch_safe_stops_without_report() -> None:
    app = load_app()

    app.selectbox[0].set_value("製程數值持續平線").run()
    app.selectbox[1].set_value("low-quality-configuration-evidence-seed-120").run()
    app.button[0].click().run()

    assert not app.exception
    assert any("安全停止" in info.value for info in app.info)
    assert any("Safety outcome：requires_attention" in warning.value for warning in app.warning)
    assert any("沒有產生正式報告" in info.value for info in app.info)
    assert any("設定資料品質不足" not in caption.value for caption in app.caption)


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
