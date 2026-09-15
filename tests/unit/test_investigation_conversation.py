import pytest

from agentic_manufacturing_incident_lab.evaluation import (
    build_benchmark_catalog,
    run_benchmark_case,
)
from agentic_manufacturing_incident_lab.local_llm import (
    ConversationTurn,
    QuestionIntent,
    build_investigation_packet,
    classify_question,
    select_grounded_context,
)


def configuration_packet() -> dict[str, object]:
    case = next(
        case
        for case in build_benchmark_catalog()
        if case.case_id == "configuration-drift-seed-118"
    )
    return build_investigation_packet(run_benchmark_case(case).run)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("這次發生什麼事？", QuestionIntent.SUMMARY),
        ("為什麼支持設定漂移？", QuestionIntent.SUPPORT),
        ("為什麼不是感測器過期？", QuestionIntent.REJECTION),
        ("正式證據有哪些？", QuestionIntent.EVIDENCE),
        ("Safety Reviewer 為什麼核准？", QuestionIntent.SAFETY),
        ("下一步應該檢查什麼？", QuestionIntent.NEXT_CHECK),
        ("請解釋這份紀錄", QuestionIntent.GENERAL),
    ],
)
def test_question_intent_is_deterministic(
    question: str,
    expected: QuestionIntent,
) -> None:
    assert classify_question(question) is expected


def test_support_question_selects_exact_supporting_observations() -> None:
    context = select_grounded_context(
        configuration_packet(),
        question="為什麼支持設定版本漂移？",
        intent=QuestionIntent.SUPPORT,
    )

    hypothesis = context["hypothesis_observation_map"][0]
    assert hypothesis["status"] == "supported"
    assert [item["id"] for item in hypothesis["supporting_observations"]] == [
        "INC-SIGNAL-0118-OBS-001",
        "INC-SIGNAL-0118-OBS-004",
    ]
    assert hypothesis["contradicting_observations"] == []


def test_rejection_question_selects_sensor_contradiction_only() -> None:
    context = select_grounded_context(
        configuration_packet(),
        question="那為什麼不是感測器資料過期？",
        intent=QuestionIntent.REJECTION,
    )

    hypotheses = context["hypothesis_observation_map"]
    assert len(hypotheses) == 1
    assert hypotheses[0]["status"] == "rejected"
    assert "感測器資料已過期" in hypotheses[0]["statement"]
    assert [item["id"] for item in hypotheses[0]["contradicting_observations"]] == [
        "INC-SIGNAL-0118-OBS-006"
    ]


def test_follow_up_uses_recent_user_turn_to_retain_entity_focus() -> None:
    context = select_grounded_context(
        configuration_packet(),
        question="那它是被什麼資料排除的？",
        intent=QuestionIntent.REJECTION,
        history=(ConversationTurn("user", "我們先看感測器資料過期。"),),
    )

    hypotheses = context["hypothesis_observation_map"]
    assert len(hypotheses) == 1
    assert "感測器資料已過期" in hypotheses[0]["statement"]


def test_conversation_turn_rejects_invalid_role_or_blank_content() -> None:
    with pytest.raises(ValueError, match="role"):
        ConversationTurn("system", "hello")
    with pytest.raises(ValueError, match="blank"):
        ConversationTurn("user", "  ")
