"""Small, dependency-free Ollama client restricted to the local machine."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_MODEL = "qwen3.5:2b-q4_K_M"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_CONTEXT_LENGTH = 4096


class OllamaError(RuntimeError):
    """Base error raised by the optional local Ollama integration."""


class OllamaUnavailableError(OllamaError):
    """Raised when the local Ollama service cannot be reached."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns malformed or unsupported output."""


class OllamaClient:
    """Call Ollama through a loopback-only HTTP endpoint."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: float = 120.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama 僅允許使用本機 loopback HTTP 位址")
        if not model.strip():
            raise ValueError("model 不可為空白")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必須大於 0")
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    def healthcheck(self) -> str:
        """Return the local Ollama version when the service is healthy."""
        data = self._request("GET", "/api/version")
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            raise OllamaResponseError("Ollama 版本回應格式無效")
        return version.strip()

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Mapping[str, object],
    ) -> tuple[dict[str, object], str]:
        """Request one schema-constrained JSON object from the local model."""
        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("prompt 不可為空白")
        request_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": dict(schema),
            "options": {
                "temperature": 0,
                "num_ctx": DEFAULT_CONTEXT_LENGTH,
            },
        }
        response = self._request("POST", "/api/chat", request_payload)
        try:
            content = response["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise OllamaResponseError("Ollama 沒有回傳有效的結構化回答") from error
        if not isinstance(parsed, dict):
            raise OllamaResponseError("Ollama 的結構化回答必須是 JSON 物件")
        response_model = response.get("model", self.model)
        if not isinstance(response_model, str) or not response_model.strip():
            response_model = self.model
        return parsed, response_model

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, socket.timeout) as error:
            raise OllamaUnavailableError(
                "無法連線到本機 Ollama，請確認 Ollama 已啟動"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OllamaResponseError("Ollama 回傳了無效的 JSON") from error
        if not isinstance(result, dict):
            raise OllamaResponseError("Ollama API 回應必須是 JSON 物件")
        if isinstance(result.get("error"), str):
            raise OllamaResponseError(f"Ollama 錯誤：{result['error']}")
        return result
