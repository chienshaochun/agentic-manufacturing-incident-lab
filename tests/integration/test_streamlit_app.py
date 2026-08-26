from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).parents[2] / "streamlit_app.py"


def load_app() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=15)
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
    assert len(app.success) == 1


def test_about_page_explains_deterministic_no_llm_boundary() -> None:
    app = load_app()

    app.radio[0].set_value("About").run()

    assert not app.exception
    assert app.title[0].value == "About this lab"
    assert "No LLM" in app.markdown[0].value
