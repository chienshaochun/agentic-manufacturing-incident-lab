import pytest

from agentic_manufacturing_incident_lab.evaluation import (
    run_planner_comparison,
)


def test_planner_comparison_uses_five_matching_connectivity_cases() -> None:
    rows = run_planner_comparison()

    assert len(rows) == 5
    assert all(row.rule_status == row.hypothesis_status for row in rows)
    assert all(row.action_delta == 0 for row in rows)
    assert all(row.same_tool_sequence for row in rows)
    assert all(row.same_evidence for row in rows)
    assert tuple(row.hypothesis_resolution for row in rows) == pytest.approx(
        (2 / 3, 2 / 3, 2 / 3, 2 / 3, 1.0)
    )


def test_planner_comparison_replays_deterministically() -> None:
    assert run_planner_comparison() == run_planner_comparison()


def test_planner_comparison_rejects_empty_selection() -> None:
    with pytest.raises(ValueError, match="at least one case"):
        run_planner_comparison(())

