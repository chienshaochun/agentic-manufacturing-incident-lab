"""Deterministic recovery policy for the diagnostic tool catalog."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from agentic_manufacturing_incident_lab.domain.execution import ActionResultStatus
from agentic_manufacturing_incident_lab.recovery.contracts import (
    RecoveryAssessment,
    RecoveryDisposition,
)
from agentic_manufacturing_incident_lab.tools import ToolSpec

if TYPE_CHECKING:
    from agentic_manufacturing_incident_lab.runtime.executor import (
        ActionExecutionRecord,
    )


class RuleBasedRecoveryPolicy:
    """Use one untried read path after retryable failure, otherwise stop safely."""

    name = "diagnostic_recovery_rule_based_v1"

    _ALTERNATIVES = {
        "check_connectivity": "read_telemetry",
        "read_telemetry": "check_connectivity",
    }
    _RECOVERABLE_ERRORS = frozenset({"tool_timeout", "transient_tool_error"})

    def assess(
        self,
        failed_execution: ActionExecutionRecord,
        *,
        available_tools: tuple[ToolSpec, ...],
        prior_executions: tuple[ActionExecutionRecord, ...],
        assessed_at: datetime,
    ) -> RecoveryAssessment:
        """Select a different, untried diagnostic channel when one is safe."""
        result = failed_execution.result
        if result.status is ActionResultStatus.SUCCEEDED:
            raise ValueError("recovery policy requires an unsuccessful execution")

        alternative = self._ALTERNATIVES.get(failed_execution.action.tool_name)
        available_names = {tool.name for tool in available_tools}
        parameters = failed_execution.action.parameters
        was_attempted = any(
            record.action.tool_name == alternative
            and record.action.parameters == parameters
            for record in prior_executions
        )
        can_try_alternative = (
            result.error_code in self._RECOVERABLE_ERRORS
            and alternative in available_names
            and not was_attempted
        )
        sequence = len(prior_executions)
        if can_try_alternative:
            return RecoveryAssessment(
                recovery_id=f"RCV-{failed_execution.action.action_id}-{sequence:03d}",
                action_id=failed_execution.action.action_id,
                incident_id=failed_execution.action.incident_id,
                policy_name=self.name,
                disposition=RecoveryDisposition.TRY_ALTERNATIVE,
                rationale=(
                    f"{failed_execution.action.tool_name} ended with "
                    f"{result.error_code}; try independent diagnostic channel "
                    f"{alternative} once."
                ),
                assessed_at=assessed_at,
                alternative_tool_name=alternative,
                alternative_parameters=parameters,
            )

        return RecoveryAssessment(
            recovery_id=f"RCV-{failed_execution.action.action_id}-{sequence:03d}",
            action_id=failed_execution.action.action_id,
            incident_id=failed_execution.action.incident_id,
            policy_name=self.name,
            disposition=RecoveryDisposition.SAFE_STOP,
            rationale=(
                f"No untried allowlisted alternative remains after "
                f"{failed_execution.action.tool_name} ended with {result.error_code}."
            ),
            assessed_at=assessed_at,
        )
