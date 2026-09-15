"""Optional local-language-model adapters for the incident lab."""

from agentic_manufacturing_incident_lab.local_llm.ollama import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    OllamaClient,
    OllamaError,
    OllamaResponseError,
    OllamaUnavailableError,
)

__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_URL",
    "OllamaClient",
    "OllamaError",
    "OllamaResponseError",
    "OllamaUnavailableError",
]
