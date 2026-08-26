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

    assert app.title[0].value == "Manufacturing Incident Workbench"
    assert app.selectbox[0].value == "isolated-station-seed-43"
    assert app.button[0].label == "Run investigation"
    assert any("Select a case" in info.value for info in app.info)


def test_run_button_executes_default_case_and_displays_metrics() -> None:
    app = load_app()

    app.button[0].click().run()

    assert not app.exception
    assert any(metric.label == "Workflow" for metric in app.metric)
    assert any(metric.value == "completed" for metric in app.metric)
    assert any(metric.label == "Benchmark" for metric in app.metric)
    assert any(metric.value == "PASS" for metric in app.metric)
    assert any("Investigation completed" in success.value for success in app.success)
    assert len(app.get("tab")) == 5
    assert len(app.dataframe) == 3
    assert any(
        "Benchmark trace: isolated-station-seed-43" in code.value
        for code in app.code
    )


def test_reporter_failure_shows_preserved_review_and_failure_panel() -> None:
    app = load_app()

    app.selectbox[0].set_value("reporter-exception-seed-43").run()
    app.button[0].click().run()

    assert not app.exception
    assert any("contained" in warning.value for warning in app.warning)
    assert any("Safety outcome: approved" in success.value for success in app.success)
    assert any("No formal report" in info.value for info in app.info)
    assert any("stage: reporting" in code.value for code in app.code)


def test_about_page_explains_deterministic_no_llm_boundary() -> None:
    app = load_app()

    app.radio[0].set_value("About").run()

    assert not app.exception
    assert app.title[0].value == "About this lab"
    assert "No LLM" in app.markdown[0].value
