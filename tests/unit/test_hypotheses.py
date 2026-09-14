from datetime import datetime, timezone

import pytest

from agentic_manufacturing_incident_lab.domain import (
    Hypothesis,
    HypothesisEffect,
    HypothesisSignal,
    HypothesisStatus,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_open_hypothesis_can_start_without_observations() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="HYP-001",
        incident_id="INC-001",
        statement="The station network interface is unavailable.",
        status=HypothesisStatus.OPEN,
        confidence=0.25,
        supporting_observation_ids=(),
        contradicting_observation_ids=(),
        rationale="Candidate explanation created from the incident scope.",
        updated_at=NOW,
    )

    assert hypothesis.status is HypothesisStatus.OPEN
    assert hypothesis.observation_ids == ()


def test_hypothesis_exposes_grounding_observations_in_stable_order() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="HYP-001",
        incident_id="INC-001",
        statement="The station network interface is unavailable.",
        status=HypothesisStatus.INCONCLUSIVE,
        confidence=0.50,
        supporting_observation_ids=("OBS-001", "OBS-002"),
        contradicting_observation_ids=("OBS-003",),
        rationale="The collected observations conflict.",
        updated_at=NOW,
    )

    assert hypothesis.observation_ids == ("OBS-001", "OBS-002", "OBS-003")


def test_conflicted_hypothesis_requires_both_signal_directions() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="HYP-CONFLICT",
        incident_id="INC-001",
        statement="The sensor stream is stale.",
        status=HypothesisStatus.CONFLICTED,
        confidence=0.50,
        supporting_observation_ids=("OBS-SUPPORT",),
        contradicting_observation_ids=("OBS-CONTRADICT",),
        rationale="Independent sources disagree.",
        updated_at=NOW,
    )

    assert hypothesis.status is HypothesisStatus.CONFLICTED

    with pytest.raises(ValueError, match="requires supporting and contradicting"):
        Hypothesis(
            hypothesis_id="HYP-CONFLICT",
            incident_id="INC-001",
            statement="The sensor stream is stale.",
            status=HypothesisStatus.CONFLICTED,
            confidence=0.50,
            supporting_observation_ids=("OBS-SUPPORT",),
            contradicting_observation_ids=(),
            rationale="Missing contradiction.",
            updated_at=NOW,
        )


def test_observation_cannot_both_support_and_contradict() -> None:
    with pytest.raises(ValueError, match="both support and contradict"):
        Hypothesis(
            hypothesis_id="HYP-001",
            incident_id="INC-001",
            statement="The station network interface is unavailable.",
            status=HypothesisStatus.INCONCLUSIVE,
            confidence=0.50,
            supporting_observation_ids=("OBS-001",),
            contradicting_observation_ids=("OBS-001",),
            rationale="Invalid overlap.",
            updated_at=NOW,
        )


@pytest.mark.parametrize(
    ("status", "supports", "contradicts", "message"),
    [
        (HypothesisStatus.SUPPORTED, (), (), "requires supporting"),
        (HypothesisStatus.REJECTED, (), (), "requires contradicting"),
    ],
)
def test_terminal_dispositions_require_grounding(
    status: HypothesisStatus,
    supports: tuple[str, ...],
    contradicts: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Hypothesis(
            hypothesis_id="HYP-001",
            incident_id="INC-001",
            statement="The station network interface is unavailable.",
            status=status,
            confidence=0.50,
            supporting_observation_ids=supports,
            contradicting_observation_ids=contradicts,
            rationale="Missing grounding.",
            updated_at=NOW,
        )


def test_signal_requires_bounded_nonzero_weight() -> None:
    signal = HypothesisSignal(
        hypothesis_id="HYP-001",
        observation_id="OBS-001",
        effect=HypothesisEffect.SUPPORTS,
        weight=0.75,
        rationale="The affected station is unreachable.",
    )

    assert signal.weight == 0.75

    with pytest.raises(ValueError, match="greater than 0.0"):
        HypothesisSignal(
            hypothesis_id="HYP-001",
            observation_id="OBS-001",
            effect=HypothesisEffect.SUPPORTS,
            weight=0.0,
            rationale="Invalid weight.",
        )
