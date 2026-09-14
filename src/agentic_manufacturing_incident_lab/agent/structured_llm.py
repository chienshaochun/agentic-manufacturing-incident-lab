"""Provider-neutral structured LLM adapter with deterministic fallback."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, TypeAlias

from agentic_manufacturing_incident_lab.agent.contracts import (
    ActionDecision,
    AgentContext,
    CompleteDecision,
    PlanningDecision,
    PlanningPolicy,
    StopDecision,
    StopReason,
)
from agentic_manufacturing_incident_lab.domain import HypothesisStatus


StructuredResponse: TypeAlias = Mapping[str, Any]
StructuredPlannerInvoker: TypeAlias = Callable[[Mapping[str, Any]], StructuredResponse]


class StructuredPlannerResponseError(ValueError):
    """Raised internally when a provider response violates the planner contract."""


class StructuredLLMPlanner:
    """Convert a provider response into a safe decision or use a fallback policy."""

    __slots__ = ("_fallback", "_invoker", "_provider_name", "name")

    def __init__(
        self,
        *,
        invoker: StructuredPlannerInvoker,
        fallback: PlanningPolicy,
        provider_name: str = "provider-neutral",
    ) -> None:
        if not callable(invoker):
            raise TypeError("invoker must be callable")
        if not provider_name.strip():
            raise ValueError("provider_name must not be blank")
        self._invoker = invoker
        self._fallback = fallback
        self._provider_name = provider_name
        self.name = f"structured_llm_{provider_name}_with_{fallback.name}_fallback"

    def decide(self, context: AgentContext) -> PlanningDecision:
        """Request one structured proposal and fail closed to deterministic logic."""
        try:
            response = self._invoker(self.build_payload(context))
            return self._parse_response(response, context)
        except Exception as error:  # provider and validation failures share one safe path
            fallback = self._fallback.decide(context)
            prefix = f"Structured LLM fallback ({type(error).__name__}): "
            return replace(fallback, rationale=prefix + fallback.rationale)

    @staticmethod
    def build_payload(context: AgentContext) -> Mapping[str, Any]:
        """Expose only runtime-visible state; simulator truth is never serialized."""
        return {
            "contract_version": "structured_planner_v1",
            "allowed_decisions": ("action", "complete", "stop"),
            "incident": {
                "incident_id": context.incident.incident_id,
                "title": context.incident.title,
                "description": context.incident.description,
                "asset_id": context.incident.asset_id,
                "severity": context.incident.severity.value,
                "goal": context.incident.goal,
            },
            "known_asset_ids": context.known_asset_ids,
            "budget": {
                "actions_used": context.working_memory.step_budget.actions_used,
                "action_limit": context.working_memory.step_budget.action_limit,
                "actions_remaining": context.working_memory.step_budget.actions_remaining,
            },
            "tools": tuple(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "risk": spec.risk.value,
                    "parameters": tuple(
                        {
                            "name": parameter.name,
                            "type": parameter.value_type.value,
                            "required": parameter.required,
                            "description": parameter.description,
                        }
                        for parameter in spec.parameters
                    ),
                }
                for spec in context.available_tools
            ),
            "observations": tuple(
                {
                    "observation_id": item.observation_id,
                    "source": item.source,
                    "kind": item.kind.value,
                    "summary": item.summary,
                    "values": dict(item.values),
                    "source_reliability": item.source_reliability,
                    "measurement_quality": item.measurement_quality,
                    "freshness": item.freshness,
                    "quality_factor": item.quality_factor,
                }
                for item in context.observations
            ),
            "hypotheses": tuple(
                {
                    "hypothesis_id": item.hypothesis_id,
                    "statement": item.statement,
                    "status": item.status.value,
                    "confidence": item.confidence,
                    "supporting_observation_ids": item.supporting_observation_ids,
                    "contradicting_observation_ids": item.contradicting_observation_ids,
                }
                for item in context.hypotheses
            ),
            "response_schema": {
                "action": {
                    "decision": "action",
                    "tool_name": "allowlisted tool name",
                    "parameters": "object matching the tool schema",
                    "rationale": "non-empty string",
                },
                "complete": {
                    "decision": "complete",
                    "hypothesis_id": "one supported hypothesis ID",
                    "rationale": "non-empty string",
                },
                "stop": {
                    "decision": "stop",
                    "reason": tuple(item.value for item in StopReason),
                    "rationale": "non-empty string",
                },
            },
        }

    @classmethod
    def _parse_response(
        cls,
        response: StructuredResponse,
        context: AgentContext,
    ) -> PlanningDecision:
        if not isinstance(response, Mapping):
            raise StructuredPlannerResponseError("response must be an object")
        decision = response.get("decision")
        if decision == "action":
            return cls._parse_action(response, context)
        if decision == "complete":
            return cls._parse_complete(response, context)
        if decision == "stop":
            return cls._parse_stop(response)
        raise StructuredPlannerResponseError("decision must be action, complete, or stop")

    @staticmethod
    def _required_text(response: StructuredResponse, key: str) -> str:
        value = response.get(key)
        if not isinstance(value, str) or not value.strip():
            raise StructuredPlannerResponseError(f"{key} must be a non-empty string")
        return value

    @classmethod
    def _parse_action(
        cls,
        response: StructuredResponse,
        context: AgentContext,
    ) -> ActionDecision:
        tool_name = cls._required_text(response, "tool_name")
        rationale = cls._required_text(response, "rationale")
        parameters = response.get("parameters")
        if not isinstance(parameters, Mapping):
            raise StructuredPlannerResponseError("parameters must be an object")
        if not all(isinstance(key, str) for key in parameters):
            raise StructuredPlannerResponseError("parameter names must be strings")

        spec = next(
            (item for item in context.available_tools if item.name == tool_name),
            None,
        )
        if spec is None:
            raise StructuredPlannerResponseError("tool is outside the runtime allowlist")
        spec.validate_parameters(parameters)

        proposed = (tool_name, dict(parameters))
        if any(
            (record.action.tool_name, dict(record.action.parameters)) == proposed
            for record in context.executions
        ):
            raise StructuredPlannerResponseError("exact tool call was already executed")
        return ActionDecision(
            tool_name=tool_name,
            parameters=parameters,
            rationale=rationale,
        )

    @classmethod
    def _parse_complete(
        cls,
        response: StructuredResponse,
        context: AgentContext,
    ) -> CompleteDecision:
        hypothesis_id = cls._required_text(response, "hypothesis_id")
        rationale = cls._required_text(response, "rationale")
        hypothesis = next(
            (
                item
                for item in context.hypotheses
                if item.hypothesis_id == hypothesis_id
                and item.status is HypothesisStatus.SUPPORTED
            ),
            None,
        )
        if hypothesis is None:
            raise StructuredPlannerResponseError(
                "completion requires an existing supported hypothesis"
            )
        return CompleteDecision(
            rationale=rationale,
            claim=hypothesis.statement,
            observation_ids=hypothesis.supporting_observation_ids,
            confidence=hypothesis.confidence,
        )

    @classmethod
    def _parse_stop(cls, response: StructuredResponse) -> StopDecision:
        rationale = cls._required_text(response, "rationale")
        reason_text = cls._required_text(response, "reason")
        try:
            reason = StopReason(reason_text)
        except ValueError as error:
            raise StructuredPlannerResponseError("unknown stop reason") from error
        return StopDecision(reason=reason, rationale=rationale)

