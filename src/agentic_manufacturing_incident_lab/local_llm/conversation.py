"""Deterministic intent routing and grounding for local investigation chat."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence


class QuestionIntent(StrEnum):
    SUMMARY = "summary"
    SUPPORT = "hypothesis_support"
    REJECTION = "hypothesis_rejection"
    EVIDENCE = "evidence"
    SAFETY = "safety"
    NEXT_CHECK = "next_check"
    GENERAL = "general"


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"user", "assistant"}:
            raise ValueError("conversation role must be user or assistant")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("conversation content must not be blank")


INTENT_KEYWORDS = (
    (
        QuestionIntent.NEXT_CHECK,
        ("下一步", "接下來", "還要檢查", "建議", "怎麼處理", "next", "check next"),
    ),
    (
        QuestionIntent.SAFETY,
        ("安全", "核准", "拒絕", "停止", "reviewer", "approved", "safe stop"),
    ),
    (
        QuestionIntent.REJECTION,
        ("排除", "反對", "不是", "rejected", "reject", "contradict"),
    ),
    (
        QuestionIntent.SUPPORT,
        ("支持", "為什麼判斷", "為何判斷", "根據什麼", "supported", "supporting"),
    ),
    (
        QuestionIntent.EVIDENCE,
        ("證據", "evidence", "observation", "依據", "引用"),
    ),
    (
        QuestionIntent.SUMMARY,
        ("摘要", "發生什麼", "調查結果", "結論", "summary", "what happened"),
    ),
)

ENTITY_GROUPS = (
    ("configuration", ("設定", "版本", "config", "configuration", "recipe")),
    ("sensor", ("感測器", "過期", "sensor", "stale", "freshness")),
    ("telemetry", ("telemetry", "遙測", "資料沒有更新")),
    ("network", ("網路", "連線", "network", "connectivity")),
    ("maintenance", ("維護", "maintenance")),
    ("shared", ("共用", "共享", "多台", "shared", "infrastructure")),
    ("station", ("單一", "隔離", "工作站", "station", "isolated")),
)


def classify_question(question: str) -> QuestionIntent:
    """Classify common investigation questions without spending an LLM call."""
    text = question.strip().lower()
    if not text:
        raise ValueError("question must not be blank")
    for intent, keywords in INTENT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent
    return QuestionIntent.GENERAL


def _question_entities(text: str) -> set[str]:
    lowered = text.lower()
    return {
        group
        for group, aliases in ENTITY_GROUPS
        if any(alias in lowered for alias in aliases)
    }


def _hypothesis_entities(hypothesis: Mapping[str, object]) -> set[str]:
    text = " ".join(
        str(hypothesis.get(field, ""))
        for field in ("id", "statement", "rationale")
    )
    return _question_entities(text)


def _records_by_id(records: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(records, list):
        return {}
    return {
        str(item["id"]): item
        for item in records
        if isinstance(item, dict) and item.get("id")
    }


def _expanded_hypothesis(
    hypothesis: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    supporting_ids = hypothesis.get("supporting_observation_ids", [])
    contradicting_ids = hypothesis.get("contradicting_observation_ids", [])
    return {
        "id": hypothesis.get("id"),
        "statement": hypothesis.get("statement"),
        "status": hypothesis.get("status"),
        "confidence": hypothesis.get("confidence"),
        "supporting_observations": [
            observations[item]
            for item in supporting_ids
            if isinstance(item, str) and item in observations
        ],
        "contradicting_observations": [
            observations[item]
            for item in contradicting_ids
            if isinstance(item, str) and item in observations
        ],
        "rationale": hypothesis.get("rationale"),
    }


def select_grounded_context(
    packet: Mapping[str, object],
    *,
    question: str,
    intent: QuestionIntent,
    history: Sequence[ConversationTurn] = (),
) -> dict[str, object]:
    """Select explicit hypothesis-to-observation mappings for a small model."""
    observations = _records_by_id(packet.get("observations"))
    hypotheses = packet.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        hypotheses = []
    evidence = packet.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    recent_user_context = " ".join(
        turn.content for turn in history[-4:] if turn.role == "user"
    )
    requested_entities = _question_entities(f"{recent_user_context} {question}")

    status_filter: set[str] | None = None
    if intent is QuestionIntent.SUPPORT:
        status_filter = {"supported"}
    elif intent is QuestionIntent.REJECTION:
        status_filter = {"rejected"}
    elif intent is QuestionIntent.NEXT_CHECK:
        status_filter = {"open", "inconclusive", "conflicted"}

    selected_hypotheses: list[Mapping[str, object]] = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        if status_filter is not None and hypothesis.get("status") not in status_filter:
            continue
        if requested_entities and not (
            requested_entities & _hypothesis_entities(hypothesis)
        ):
            continue
        selected_hypotheses.append(hypothesis)
    if not selected_hypotheses and status_filter is not None:
        selected_hypotheses = [
            hypothesis
            for hypothesis in hypotheses
            if isinstance(hypothesis, dict)
            and hypothesis.get("status") in status_filter
        ]
    if not selected_hypotheses and intent in {
        QuestionIntent.SUMMARY,
        QuestionIntent.EVIDENCE,
        QuestionIntent.SAFETY,
        QuestionIntent.GENERAL,
    }:
        selected_hypotheses = [
            hypothesis for hypothesis in hypotheses if isinstance(hypothesis, dict)
        ]

    selected_observation_ids = {
        item
        for hypothesis in selected_hypotheses
        for field in ("supporting_observation_ids", "contradicting_observation_ids")
        for item in hypothesis.get(field, [])
        if isinstance(item, str) and item in observations
    }
    selected_evidence = evidence
    if requested_entities:
        matching_evidence = [
            item
            for item in evidence
            if isinstance(item, dict)
            and requested_entities & _question_entities(str(item.get("claim", "")))
        ]
        if matching_evidence:
            selected_evidence = matching_evidence
    for item in selected_evidence:
        if not isinstance(item, dict):
            continue
        selected_observation_ids.update(
            observation_id
            for observation_id in item.get("observation_ids", [])
            if isinstance(observation_id, str) and observation_id in observations
        )

    if intent in {QuestionIntent.SUMMARY, QuestionIntent.SAFETY, QuestionIntent.GENERAL}:
        selected_observation_ids.update(observations)

    return {
        "question_intent": intent.value,
        "incident": packet.get("incident"),
        "workflow_status": packet.get("workflow_status"),
        "completed_actions": packet.get("actions", []),
        "hypothesis_observation_map": [
            _expanded_hypothesis(item, observations)
            for item in selected_hypotheses
        ],
        "selected_observations": [
            observations[item]
            for item in observations
            if item in selected_observation_ids
        ],
        "formal_evidence": selected_evidence,
        "safety_review": packet.get("safety_review"),
        "approved_report": packet.get("approved_report"),
    }
