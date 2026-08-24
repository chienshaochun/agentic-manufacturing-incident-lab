from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from agentic_manufacturing_incident_lab.agent import (
    MemoryFact,
    OpenQuestion,
    StepBudget,
    StepBudgetExceeded,
    WorkingMemory,
)

NOW = datetime(2026, 8, 24, 9, 5, tzinfo=UTC)


def make_fact(
    fact_id: str = "FACT-001",
    incident_id: str = "INC-001",
    observation_ids: tuple[str, ...] = ("OBS-001",),
) -> MemoryFact:
    return MemoryFact(
        fact_id=fact_id,
        incident_id=incident_id,
        statement="ST-02 is unreachable.",
        observation_ids=observation_ids,
        recorded_at=NOW,
    )


def make_question(
    question_id: str = "Q-001",
    incident_id: str = "INC-001",
) -> OpenQuestion:
    return OpenQuestion(
        question_id=question_id,
        incident_id=incident_id,
        prompt="Is another station reachable?",
        opened_at=NOW,
    )


def make_memory(
    *,
    facts: tuple[MemoryFact, ...] = (),
    open_questions: tuple[OpenQuestion, ...] = (),
    updated_at: datetime = NOW,
) -> WorkingMemory:
    return WorkingMemory(
        task_id="TASK-001",
        incident_id="INC-001",
        revision=0,
        facts=facts,
        open_questions=open_questions,
        step_budget=StepBudget(action_limit=4),
        updated_at=updated_at,
    )


def test_memory_fact_copies_observation_ids_to_immutable_tuple() -> None:
    observation_ids = ["OBS-001", "OBS-002"]

    fact = MemoryFact(
        fact_id="FACT-001",
        incident_id="INC-001",
        statement="The affected station has no telemetry.",
        observation_ids=observation_ids,  # type: ignore[arg-type]
        recorded_at=NOW,
    )
    observation_ids.append("OBS-003")

    assert fact.observation_ids == ("OBS-001", "OBS-002")


def test_memory_fact_requires_observation_reference() -> None:
    with pytest.raises(ValueError, match="at least one observation"):
        make_fact(observation_ids=())


def test_memory_fact_rejects_duplicate_observation_references() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        make_fact(observation_ids=("OBS-001", "OBS-001"))


@pytest.mark.parametrize(
    ("action_limit", "actions_used", "message"),
    [
        (0, 0, "positive integer"),
        (True, 0, "positive integer"),
        (3, -1, "non-negative integer"),
        (3, True, "non-negative integer"),
        (3, 4, "must not exceed"),
    ],
)
def test_step_budget_rejects_invalid_counts(
    action_limit: object,
    actions_used: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        StepBudget(
            action_limit=action_limit,  # type: ignore[arg-type]
            actions_used=actions_used,  # type: ignore[arg-type]
        )


def test_step_budget_consumption_returns_new_value() -> None:
    original = StepBudget(action_limit=3)

    consumed = original.consume()

    assert original.actions_used == 0
    assert consumed.actions_used == 1
    assert consumed.actions_remaining == 2
    assert not consumed.is_exhausted


def test_exhausted_step_budget_cannot_be_consumed() -> None:
    budget = StepBudget(action_limit=2, actions_used=2)

    assert budget.is_exhausted
    with pytest.raises(StepBudgetExceeded, match="exhausted"):
        budget.consume()


def test_working_memory_normalizes_collections_and_exposes_references() -> None:
    first = make_fact(observation_ids=("OBS-001", "OBS-002"))
    second = make_fact(
        fact_id="FACT-002",
        observation_ids=("OBS-002", "OBS-003"),
    )
    question = make_question()

    memory = WorkingMemory(
        task_id="TASK-001",
        incident_id="INC-001",
        revision=0,
        facts=[first, second],  # type: ignore[arg-type]
        open_questions=[question],  # type: ignore[arg-type]
        step_budget=StepBudget(action_limit=4),
        updated_at=NOW,
    )

    assert memory.facts == (first, second)
    assert memory.open_questions == (question,)
    assert memory.referenced_observation_ids == (
        "OBS-001",
        "OBS-002",
        "OBS-003",
    )


def test_working_memory_rejects_duplicate_fact_ids() -> None:
    fact = make_fact()

    with pytest.raises(ValueError, match="unique fact_id"):
        make_memory(facts=(fact, fact))


def test_working_memory_rejects_duplicate_question_ids() -> None:
    question = make_question()

    with pytest.raises(ValueError, match="unique question_id"):
        make_memory(open_questions=(question, question))


def test_working_memory_enforces_incident_scope() -> None:
    with pytest.raises(ValueError, match="facts must match"):
        make_memory(facts=(make_fact(incident_id="INC-OTHER"),))

    with pytest.raises(ValueError, match="questions must match"):
        make_memory(open_questions=(make_question(incident_id="INC-OTHER"),))


def test_working_memory_rejects_future_fact_or_question() -> None:
    future = NOW + timedelta(seconds=1)

    with pytest.raises(ValueError, match="facts must not be recorded after"):
        make_memory(facts=(replace(make_fact(), recorded_at=future),))

    with pytest.raises(ValueError, match="questions must not be opened after"):
        make_memory(
            open_questions=(replace(make_question(), opened_at=future),),
        )
