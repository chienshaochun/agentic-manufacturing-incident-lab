import pytest

from agentic_manufacturing_incident_lab.evaluation import (
    build_phase7_benchmark_catalog,
    run_benchmark_case,
)
from agentic_manufacturing_incident_lab.local_llm import (
    OllamaInvestigationQA,
    OllamaResponseError,
    answer_from_payload,
    build_investigation_packet,
)


def completed_run():
    case = next(
        case
        for case in build_phase7_benchmark_catalog()
        if case.case_id == "isolated-station-seed-43"
    )
    return run_benchmark_case(case).run


def valid_answer(run) -> dict[str, object]:
    packet = build_investigation_packet(run)
    observation_ids = [item["id"] for item in packet["observations"]]
    evidence_ids = [item["id"] for item in packet["evidence"]]
    return {
        "answer": "ST-02 無法連線，但同區域的 ST-01 可以連線。",
        "observation_ids": observation_ids[:2],
        "evidence_ids": evidence_ids[:1],
        "next_checks": [
            {"action": "檢查 ST-02 網路介面", "reason": "故障目前限於單一設備"}
        ],
        "limitations": ["模擬資料不等同真實產線量測"],
    }


class FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.call: dict[str, object] = {}

    def chat_json(self, **kwargs):
        self.call = kwargs
        return self.payload, "qwen-test"


def test_packet_contains_only_traceable_investigation_records() -> None:
    packet = build_investigation_packet(completed_run())

    assert packet["incident"]["id"] == "INC-CONNECTIVITY-0043"
    assert len(packet["observations"]) == 3
    assert packet["evidence"]
    assert packet["safety_review"]["outcome"] == "approved"
    assert packet["approved_report"] is not None


def test_qa_returns_validated_cited_answer() -> None:
    run = completed_run()
    client = FakeClient(valid_answer(run))
    provider = OllamaInvestigationQA(client=client)  # type: ignore[arg-type]

    answer = provider.answer("為什麼判斷是單一設備問題？", run)

    assert answer.model == "qwen-test"
    assert answer.observation_ids
    assert answer.evidence_ids
    assert answer.next_checks[0].action == "檢查 ST-02 網路介面"
    assert client.call["schema"]["additionalProperties"] is False
    assert "Hypothesis 不是 Evidence" in client.call["system_prompt"]
    assert "不可無理由重複" in client.call["system_prompt"]
    assert "quality_factor 小於 0.8" in client.call["system_prompt"]
    assert "INC-CONNECTIVITY-0043" in client.call["user_prompt"]


def test_answer_rejects_unknown_observation_or_evidence_id() -> None:
    run = completed_run()
    packet = build_investigation_packet(run)
    unknown_observation = valid_answer(run) | {"observation_ids": ["OBS-FAKE"]}
    unknown_evidence = valid_answer(run) | {"evidence_ids": ["EVD-FAKE"]}

    with pytest.raises(OllamaResponseError, match="Observation ID"):
        answer_from_payload(unknown_observation, packet=packet, model="qwen")
    with pytest.raises(OllamaResponseError, match="Evidence ID"):
        answer_from_payload(unknown_evidence, packet=packet, model="qwen")


def test_answer_requires_observation_citation_when_run_has_observations() -> None:
    run = completed_run()
    packet = build_investigation_packet(run)
    payload = valid_answer(run) | {"observation_ids": []}

    with pytest.raises(OllamaResponseError, match="至少一個 Observation"):
        answer_from_payload(payload, packet=packet, model="qwen")


def test_qa_rejects_empty_or_oversized_question() -> None:
    run = completed_run()
    provider = OllamaInvestigationQA(client=FakeClient(valid_answer(run)))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="空白"):
        provider.answer("  ", run)
    with pytest.raises(ValueError, match="1000"):
        provider.answer("x" * 1001, run)
