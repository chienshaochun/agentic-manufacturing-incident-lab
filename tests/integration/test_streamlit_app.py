from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).parents[2] / "streamlit_app.py"


def load_app() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.run()
    assert not app.exception
    return app


def test_app_loads_incident_workbench_without_running_case() -> None:
    app = load_app()

    assert app.title[0].value == "製造事件調查台"
    assert app.selectbox[0].value == "isolated-station-seed-43"
    assert app.button[0].label == "執行調查 Run investigation"
    assert any("請選擇案例" in info.value for info in app.info)


def test_run_button_executes_default_case_and_displays_metrics() -> None:
    app = load_app()

    app.button[0].click().run()

    assert not app.exception
    assert any(metric.label == "工作流 Workflow" for metric in app.metric)
    assert any(metric.value == "completed" for metric in app.metric)
    assert any(metric.label == "基準結果 Benchmark" for metric in app.metric)
    assert any(metric.value == "PASS" for metric in app.metric)
    assert any("調查完成" in success.value for success in app.success)
    assert len(app.get("tab")) == 5
    assert len(app.dataframe) == 3
    assert any(
        "Benchmark 稽核軌跡： isolated-station-seed-43" in code.value
        for code in app.code
    )


def test_reporter_failure_shows_preserved_review_and_failure_panel() -> None:
    app = load_app()

    app.selectbox[0].set_value("reporter-exception-seed-43").run()
    app.button[0].click().run()

    assert not app.exception
    assert any("安全收斂" in warning.value for warning in app.warning)
    assert any("Safety outcome：approved" in success.value for success in app.success)
    assert any("沒有產生正式報告" in info.value for info in app.info)
    assert any("階段： reporting" in code.value for code in app.code)


def test_benchmark_dashboard_runs_all_controlled_cases() -> None:
    app = load_app()

    app.radio[0].set_value("基準測試 Benchmark Dashboard").run()
    assert app.title[0].value == "基準測試儀表板"
    assert app.button[0].label == "執行完整 Benchmark"

    app.button[0].click().run(timeout=60)

    assert not app.exception
    assert any(metric.label == "案例數 Cases" and metric.value == "11" for metric in app.metric)
    assert any(metric.label == "通過 Passed" and metric.value == "11" for metric in app.metric)
    assert len(app.dataframe) == 1
    assert len(app.dataframe[0].value) == 11
    assert any("所有案例" in success.value for success in app.success)
    assert any("- 案例數： 11" in code.value for code in app.code)


def test_about_page_explains_deterministic_no_llm_boundary() -> None:
    app = load_app()

    app.radio[0].set_value("關於專案 About").run()

    assert not app.exception
    assert app.title[0].value == "關於本實驗室"
    assert "沒有使用 LLM" in app.markdown[0].value
