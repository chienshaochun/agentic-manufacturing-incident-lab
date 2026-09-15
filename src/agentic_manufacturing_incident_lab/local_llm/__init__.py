"""Optional local-language-model adapters for the incident lab."""

from agentic_manufacturing_incident_lab.local_llm.conversation import (
    ConversationTurn,
    QuestionIntent,
    classify_question,
    select_grounded_context,
)
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
    "ConversationTurn",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_URL",
    "InvestigationAnswer",
    "NextCheck",
    "OllamaClient",
    "OllamaError",
    "OllamaInvestigationQA",
    "OllamaResponseError",
    "OllamaUnavailableError",
    "QuestionIntent",
    "answer_from_payload",
    "build_investigation_packet",
    "classify_question",
    "select_grounded_context",
]
