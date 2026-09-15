import io
import json
from urllib.error import URLError

import pytest

from agentic_manufacturing_incident_lab.local_llm import (
    OllamaClient,
    OllamaResponseError,
    OllamaUnavailableError,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body.read()


def test_client_rejects_non_loopback_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaClient(base_url="https://models.example.com")


def test_healthcheck_returns_version() -> None:
    client = OllamaClient(opener=lambda *_args, **_kwargs: FakeResponse({"version": "0.12.0"}))

    assert client.healthcheck() == "0.12.0"


def test_chat_json_sends_schema_constrained_request() -> None:
    captured: dict[str, object] = {}

    def opener(request, **_kwargs):
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse(
            {
                "model": "qwen-test",
                "message": {"content": '{"answer":"ok"}'},
            }
        )

    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    result, model = OllamaClient(opener=opener).chat_json(
        system_prompt="system",
        user_prompt="question",
        schema=schema,
    )

    assert result == {"answer": "ok"}
    assert model == "qwen-test"
    assert captured["format"] == schema
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["options"] == {"temperature": 0, "num_ctx": 4096}


def test_client_distinguishes_unavailable_service() -> None:
    def unavailable(*_args, **_kwargs):
        raise URLError("offline")

    with pytest.raises(OllamaUnavailableError, match="無法連線"):
        OllamaClient(opener=unavailable).healthcheck()


def test_client_rejects_invalid_structured_content() -> None:
    client = OllamaClient(
        opener=lambda *_args, **_kwargs: FakeResponse(
            {"message": {"content": "not-json"}}
        )
    )

    with pytest.raises(OllamaResponseError, match="結構化回答"):
        client.chat_json(
            system_prompt="system",
            user_prompt="question",
            schema={"type": "object"},
        )
