from dataclasses import replace

import pytest

from agentic_manufacturing_incident_lab.collaboration import (
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.simulation import (
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.workflows import (
    run_single_multi_comparison,
)


def run_comparison(*, seed=43, action_limit=32):
    return run_single_multi_comparison(
        build_station_connectivity_scenario(seed=seed),
        action_limit=action_limit,
    )


def test_comparison_runs_matching_diagnostics_in_isolated_environments() -> None:
    comparison = run_comparison()

    assert comparison.single_status is TaskStatus.COMPLETED
    assert comparison.multi_run.status is MultiAgentStatus.COMPLETED
    assert comparison.diagnostic_status_match is True
    assert comparison.action_plan_match is True
    assert comparison.observation_match is True
    assert comparison.evidence_match is True


def test_comparison_exposes_diagnostic_cost_and_governance_overhead() -> None:
    comparison = run_comparison()

    assert comparison.single_action_count == 3
    assert comparison.multi_diagnostic_action_count == 3
    assert comparison.diagnostic_action_delta == 0
    assert comparison.coordination_handoff_count == 6
    assert comparison.safety_review_outcome is SafetyReviewOutcome.APPROVED
    assert comparison.report_generated is True
    assert comparison.collaboration_failure_count == 0


def test_isolated_twins_generate_equivalent_observation_sequences() -> None:
    comparison = run_comparison()
    assert comparison.multi_diagnostic_run is not None

    single_ids = tuple(
        observation.observation_id
        for observation in comparison.single_run.observations
    )
    multi_ids = tuple(
        observation.observation_id
        for observation in comparison.multi_diagnostic_run.observations
    )

    assert single_ids == multi_ids
    assert single_ids[0].endswith("OBS-001")


def test_limited_budget_compares_matching_safe_stops() -> None:
    comparison = run_comparison(action_limit=1)

    assert comparison.single_status is TaskStatus.SAFE_STOPPED
    assert comparison.multi_run.status is MultiAgentStatus.SAFE_STOPPED
    assert comparison.diagnostic_status_match is True
    assert comparison.action_plan_match is True
    assert comparison.observation_match is True
    assert comparison.evidence_match is True
    assert comparison.single_action_count == 1
    assert comparison.multi_diagnostic_action_count == 1
    assert comparison.coordination_handoff_count == 4
    assert (
        comparison.safety_review_outcome
        is SafetyReviewOutcome.REQUIRES_ATTENTION
    )
    assert comparison.report_generated is False
    assert comparison.collaboration_failure_count == 0


def test_comparison_replay_is_deterministic() -> None:
    assert run_comparison() == run_comparison()


def test_comparison_rejects_different_incidents() -> None:
    first = run_comparison(seed=43)
    second = run_comparison(seed=44)

    with pytest.raises(ValueError, match="must describe the same incident"):
        replace(first, multi_run=second.multi_run)


@pytest.mark.parametrize("action_limit", [0, -1, True])
def test_comparison_rejects_invalid_action_limit(action_limit) -> None:
    with pytest.raises(ValueError, match="action_limit must be a positive integer"):
        run_comparison(action_limit=action_limit)
