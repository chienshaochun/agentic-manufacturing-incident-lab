"""Immutable contracts shared by tool implementations and the registry."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol

from agentic_manufacturing_incident_lab.domain._validation import require_text
from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Observation,
    ScalarValue,
)

_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ToolParameterError(ValueError):
    """Raised when tool parameters do not satisfy a declared contract."""


class ToolParameterType(StrEnum):
    """Serializable scalar types accepted by tool parameters."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"

    def accepts(self, value: ScalarValue) -> bool:
        """Return whether a scalar value matches this parameter type exactly."""
        if self is ToolParameterType.STRING:
            return isinstance(value, str)
        if self is ToolParameterType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if self is ToolParameterType.NUMBER:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class ToolParameter:
    """One named input accepted by a tool."""

    name: str
    description: str
    value_type: ToolParameterType
    required: bool = True

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        require_text(self.description, "description")
        if _TOOL_NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("parameter name must use lower_snake_case")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Public metadata and parameter schema for one allowlisted tool."""

    name: str
    description: str
    risk: ActionRisk
    parameters: tuple[ToolParameter, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        require_text(self.description, "description")
        if _TOOL_NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("tool name must use lower_snake_case")
        parameters = tuple(self.parameters)
        parameter_names = tuple(parameter.name for parameter in parameters)
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("tool parameters must have unique names")
        object.__setattr__(self, "parameters", parameters)

    def validate_parameters(self, values: Mapping[str, ScalarValue]) -> None:
        """Validate required, unknown, and incorrectly typed parameters."""
        parameters_by_name = {parameter.name: parameter for parameter in self.parameters}
        missing = sorted(
            parameter.name
            for parameter in self.parameters
            if parameter.required and parameter.name not in values
        )
        if missing:
            raise ToolParameterError(f"missing required parameters: {', '.join(missing)}")

        unknown = sorted(set(values) - set(parameters_by_name))
        if unknown:
            raise ToolParameterError(f"unknown parameters: {', '.join(unknown)}")

        for name, value in values.items():
            parameter = parameters_by_name[name]
            if not parameter.value_type.accepts(value):
                raise ToolParameterError(
                    f"parameter {name} must be {parameter.value_type.value}"
                )


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """Raw output returned by a tool before an ActionResult is recorded."""

    summary: str
    observations: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.summary, "summary")
        observations = tuple(self.observations)
        observation_ids = tuple(observation.observation_id for observation in observations)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("tool response observations must have unique IDs")
        object.__setattr__(self, "observations", observations)


class Tool(Protocol):
    """Interface implemented by every callable tool."""

    spec: ToolSpec

    def invoke(self, action: Action) -> ToolResponse:
        """Execute one complete action after registry validation."""
        ...
