from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.collaboration import (
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkCase,
    build_controlled_benchmark_catalog,
)
from agentic_manufacturing_incident_lab.simulation import (
    build_shared_connectivity_scenario,
    build_station_connectivity_scenario,
    build_telemetry_path_scenario,
)


def catalog():
    return build_controlled_benchmark_catalog()


def case_by_id(case_id: str) -> BenchmarkCase:
    return next(case for case in catalog() if case.case_id == case_id)


def test_catalog_has_unique_six_controlled_cases() -> None:
    cases = catalog()

    assert isinstance(cases, tuple)
    assert len(cases) == 6
    assert len({case.case_id for case in cases}) == 6


def test_isolated_cases_rotate_fault_across_all_stations() -> None:
    cases = catalog()[:3]

    assert tuple(case.scenario.incident.asset_id for case in cases) == (
        "ST-01",
        "ST-02",
        "ST-03",
    )
    for case in cases:
        affected = case.scenario.incident.asset_id
        assert case.expectation.expected_multi_status is MultiAgentStatus.COMPLETED
        assert case.expectation.expected_diagnostic_status is TaskStatus.COMPLETED
        assert case.expectation.expected_safety_outcome is SafetyReviewOutcome.APPROVED
        assert case.expectation.expect_report is True
        assert case.expectation.expected_evidence_claims == (
            f"The observed connectivity failure is isolated to {affected}.",
        )


def test_shared_infrastructure_case_requires_safe_stop_without_claim() -> None:
    case = case_by_id("shared-infrastructure-seed-73")

    assert case.scenario.faulted_asset_id == "GW-01"
    assert case.expectation.expected_tool_sequence == (
        "check_connectivity",
        "check_connectivity",
    )
    assert case.expectation.expected_evidence_claims == ()
    assert case.expectation.expected_multi_status is MultiAgentStatus.SAFE_STOPPED
    assert (
        case.expectation.expected_safety_outcome
        is SafetyReviewOutcome.REQUIRES_ATTENTION
    )
    assert case.expectation.expect_report is False


def test_telemetry_path_case_requires_safe_stop_without_overclaim() -> None:
    case = case_by_id("telemetry-path-seed-91")
    affected = case.scenario.asset_truth(case.scenario.incident.asset_id)

    assert affected.network_reachable is True
    assert affected.telemetry_available is False
    assert case.expectation.expected_tool_sequence == (
        "check_connectivity",
        "read_telemetry",
    )
    assert case.expectation.expected_evidence_claims == ()
    assert case.expectation.expected_multi_status is MultiAgentStatus.SAFE_STOPPED
    assert case.expectation.expect_report is False


def test_budget_case_binds_one_action_limit_to_one_expected_call() -> None:
    case = case_by_id("action-budget-safe-stop-seed-43")

    assert case.action_limit == 1
    assert case.expectation.max_tool_calls == 1
    assert case.expectation.expected_tool_sequence == ("check_connectivity",)
    assert case.expectation.expected_multi_status is MultiAgentStatus.SAFE_STOPPED
    assert case.expectation.max_handoffs == 4


def test_catalog_replay_is_deterministic() -> None:
    assert catalog() == catalog()


@pytest.mark.parametrize(
    "builder",
    [
        build_station_connectivity_scenario,
        build_shared_connectivity_scenario,
        build_telemetry_path_scenario,
    ],
)
@pytest.mark.parametrize("seed", [-1, True, 1.5])
def test_scenario_builders_reject_invalid_seed(builder, seed) -> None:
    with pytest.raises(ValueError, match="seed must be a non-negative integer"):
        builder(seed=seed)


def test_benchmark_case_rejects_invalid_action_limit() -> None:
    case = catalog()[0]

    with pytest.raises(ValueError, match="action_limit must be a positive integer"):
        replace(case, action_limit=0)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("scenario_id", "other", "scenario_id"),
        ("seed", 999, "seed"),
        ("incident_id", "INC-OTHER", "incident_id"),
    ],
)
def test_benchmark_case_rejects_mismatched_expectation(
    field_name,
    value,
    message,
) -> None:
    case = catalog()[0]
    expectation = replace(case.expectation, **{field_name: value})

    with pytest.raises(ValueError, match=message):
        replace(case, expectation=expectation)


def test_benchmark_case_rejects_tool_budget_above_action_limit() -> None:
    case = case_by_id("shared-infrastructure-seed-73")

    with pytest.raises(ValueError, match="must not exceed case action_limit"):
        BenchmarkCase(
            scenario=case.scenario,
            action_limit=1,
            expectation=case.expectation,
        )
