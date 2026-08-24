"""Allowlisted registry that validates an Action before invoking a tool."""

from collections.abc import Iterable

from agentic_manufacturing_incident_lab.domain.models import Action
from agentic_manufacturing_incident_lab.tools.contracts import Tool, ToolResponse, ToolSpec


class DuplicateToolError(ValueError):
    """Raised when two tools attempt to use the same public name."""


class UnknownToolError(KeyError):
    """Raised when an action requests a tool outside the allowlist."""


class ToolRiskMismatchError(ValueError):
    """Raised when an action understates or changes a registered tool's risk."""


class ToolRegistry:
    """Own the callable tool allowlist and enforce each declared contract."""

    __slots__ = ("_tools",)

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    @property
    def specs(self) -> tuple[ToolSpec, ...]:
        """Return stable public metadata without exposing tool handlers."""
        return tuple(self._tools[name].spec for name in sorted(self._tools))

    def register(self, tool: Tool) -> None:
        """Add one tool to the allowlist, rejecting duplicate names."""
        name = tool.spec.name
        if name in self._tools:
            raise DuplicateToolError(f"tool already registered: {name}")
        self._tools[name] = tool

    def spec_for(self, name: str) -> ToolSpec:
        """Return public metadata for one registered tool."""
        return self._resolve(name).spec

    def execute(self, action: Action) -> ToolResponse:
        """Validate an action against its tool contract, then invoke the handler."""
        tool = self._resolve(action.tool_name)
        if action.risk is not tool.spec.risk:
            raise ToolRiskMismatchError(
                f"action risk {action.risk} does not match registered risk {tool.spec.risk}"
            )
        tool.spec.validate_parameters(action.parameters)
        return tool.invoke(action.parameters)

    def _resolve(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise UnknownToolError(f"tool is not registered: {name}") from error
