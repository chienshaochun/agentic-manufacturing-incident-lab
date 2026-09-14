import pytest

from agentic_manufacturing_incident_lab.domain import HypothesisStatus, TaskStatus
from agentic_manufacturing_incident_lab.evaluation import (
    build_benchmark_catalog,
    run_benchmark_case,
)


def result(case_id: str):
    case = next(item for item in build_benchmark_catalog() if item.case_id == case_id)
    return run_benchmark_case(case)


@pytest.mark.parametrize(
    "case_id",
    [
        "conflicting-sensor-evidence-seed-119",
        "low-quality-configuration-evidence-seed-120",
        "multiple-supported-causes-seed-121",
    ],
)
def test_uncertain_cases_stop_without_manufacturing_evidence(case_id: str) -> None:
    benchmark = result(case_id)
    diagnostic = benchmark.run.diagnostic.run

    assert benchmark.passed is True
    assert diagnostic.final_state.status is TaskStatus.SAFE_STOPPED
    assert len(diagnostic.executions) == 6
    assert diagnostic.evidence == ()
    assert benchmark.run.report is None


def test_conflicting_alarm_and_direct_sensor_measurement_reject_alarm_clue() -> None:
    diagnostic = result(
        "conflicting-sensor-evidence-seed-119"
    ).run.diagnostic.run
    sensor = next(
        item for item in diagnostic.hypotheses
        if item.hypothesis_id.endswith("-SENSOR")
    )

    assert sensor.status is HypothesisStatus.REJECTED
    assert "support_score=0.30" in sensor.rationale
    assert "contradiction_score=1.00" in sensor.rationale


def test_stale_configuration_source_remains_inconclusive() -> None:
    diagnostic = result(
        "low-quality-configuration-evidence-seed-120"
    ).run.diagnostic.run
    configuration = next(
        item for item in diagnostic.hypotheses
        if item.hypothesis_id.endswith("-CONFIG")
    )
    observation = diagnostic.executions[3].observations[0]

    assert observation.freshness == 0.40
    assert configuration.status is HypothesisStatus.INCONCLUSIVE
    assert "support_score=0.58" in configuration.rationale


def test_multiple_supported_causes_are_not_collapsed_into_one_claim() -> None:
    diagnostic = result(
        "multiple-supported-causes-seed-121"
    ).run.diagnostic.run
    supported = {
        item.hypothesis_id.rsplit("-", 1)[-1]
        for item in diagnostic.hypotheses
        if item.status is HypothesisStatus.SUPPORTED
    }

    assert supported == {"CONFIG", "SENSOR"}
    assert diagnostic.evidence == ()
