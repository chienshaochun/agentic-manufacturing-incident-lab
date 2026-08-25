"""Deterministic fault injection for exercising tool recovery behavior."""

from enum import StrEnum

from agentic_manufacturing_incident_lab.domain.models import Action
from agentic_manufacturing_incident_lab.tools.contracts import (
    PermanentToolError,
    Tool,
    ToolResponse,
    ToolSpec,
    ToolTimeoutError,
    TransientToolError,
)


class InjectedFault(StrEnum):
    """One expected failure that can be scripted before a tool succeeds."""

    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


class FaultInjectingTool:
    """Wrap a tool and replay a fixed failure script before delegating to it."""

    __slots__ = ("_attempt_count", "_fault_script", "_tool")

    def __init__(
        self,
        tool: Tool,
        fault_script: tuple[InjectedFault, ...],
    ) -> None:
        self._tool = tool
        self._fault_script = tuple(fault_script)
        if not all(isinstance(fault, InjectedFault) for fault in self._fault_script):
            raise TypeError("fault_script must contain InjectedFault values")
        self._attempt_count = 0

    @property
    def spec(self) -> ToolSpec:
        """Expose the wrapped tool contract without changing its allowlist entry."""
        return self._tool.spec

    @property
    def attempt_count(self) -> int:
        """Return how many times the wrapper has been invoked."""
        return self._attempt_count

    def invoke(self, action: Action) -> ToolResponse:
        """Raise the next scripted failure or invoke the wrapped tool."""
        script_index = self._attempt_count
        self._attempt_count += 1
        if script_index >= len(self._fault_script):
            return self._tool.invoke(action)

        fault = self._fault_script[script_index]
        detail = f"Injected {fault.value} failure on attempt {self._attempt_count}."
        if fault is InjectedFault.TIMEOUT:
            raise ToolTimeoutError(detail)
        if fault is InjectedFault.TRANSIENT:
            raise TransientToolError(detail)
        raise PermanentToolError(detail)
