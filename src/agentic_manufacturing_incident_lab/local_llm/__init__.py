"""Optional local-language-model adapters for the incident lab."""

from agentic_manufacturing_incident_lab.local_llm.investigation_qa import (
    ANSWER_SCHEMA,
    InvestigationAnswer,
    NextCheck,
    OllamaInvestigationQA,
    answer_from_payload,
    build_investigation_packet,
)
from agentic_manufacturing_incident_lab.local_llm.ollama import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    OllamaClient,
    OllamaError,
    OllamaResponseError,
    OllamaUnavailableError,
)

__all__ = [
    "ANSWER_SCHEMA",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_URL",
    "InvestigationAnswer",
    "NextCheck",
    "OllamaClient",
    "OllamaError",
    "OllamaInvestigationQA",
    "OllamaResponseError",
    "OllamaUnavailableError",
    "answer_from_payload",
    "build_investigation_packet",
]
