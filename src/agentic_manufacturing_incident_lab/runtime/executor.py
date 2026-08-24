"""Execute one Action through the registry and produce an auditable record."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.models import Action, Observation
from agentic_manufacturing_incident_lab.tools import (
    IncidentScopeError,
    ToolParameterError,
    ToolRegistry,
    ToolRiskMismatchError,
    UnknownToolError,
)


@dataclass(frozen=True, slots=True)
class ActionExecutionRecord:
    """One Action, its terminal result, and every observation it produced."""

    action: Action
    result: ActionResult
    observations: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        observations = tuple(self.observations)
        if self.result.action_id != self.action.action_id:
            raise ValueError("result action_id must match action")
        if self.result.incident_id != self.action.incident_id:
            raise ValueError("result incident_id must match action")
        observation_ids = tuple(observation.observation_id for observation in observations)
        if self.result.observation_ids != observation_ids:
            raise ValueError("result observation_ids must match record observations")
        object.__setattr__(self, "observations", observations)


class ActionExecutor:
    """Convert registry responses and expected tool errors into ActionResults."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, action: Action) -> ActionExecutionRecord:
        """Execute one action and always record known validation or lookup failures."""
        try:
            response = self._registry.execute(action)
        except UnknownToolError as error:
            return self._error_record(
                action,
                status=ActionResultStatus.DENIED,
                error_code="tool_not_allowed",
                detail=str(error),
            )
        except ToolParameterError as error:
            return self._error_record(
                action,
                status=ActionResultStatus.DENIED,
                error_code="invalid_parameters",
                detail=str(error),
            )
        except ToolRiskMismatchError as error:
            return self._error_record(
                action,
                status=ActionResultStatus.DENIED,
                error_code="risk_mismatch",
                detail=str(error),
            )
        except IncidentScopeError as error:
            return self._error_record(
                action,
                status=ActionResultStatus.DENIED,
                error_code="incident_scope_mismatch",
                detail=str(error),
            )
        except KeyError as error:
            detail = str(error.args[0]) if error.args else "unknown lookup failure"
            return self._error_record(
                action,
                status=ActionResultStatus.FAILED,
                error_code="unknown_asset",
                detail=detail,
            )

        observations = tuple(response.observations)
        completed_at = self._completion_time(action, observations)
        result = ActionResult(
            result_id=f"RES-{action.action_id}",
            action_id=action.action_id,
            incident_id=action.incident_id,
            status=ActionResultStatus.SUCCEEDED,
            summary=response.summary,
            completed_at=completed_at,
            observation_ids=tuple(
                observation.observation_id for observation in observations
            ),
        )
        return ActionExecutionRecord(
            action=action,
            result=result,
            observations=observations,
        )

    @staticmethod
    def _completion_time(
        action: Action,
        observations: tuple[Observation, ...],
    ) -> datetime:
        earliest_completion = action.requested_at + timedelta(seconds=1)
        if not observations:
            return earliest_completion
        return max(
            earliest_completion,
            max(observation.observed_at for observation in observations),
        )

    @staticmethod
    def _error_record(
        action: Action,
        *,
        status: ActionResultStatus,
        error_code: str,
        detail: str,
    ) -> ActionExecutionRecord:
        result = ActionResult(
            result_id=f"RES-{action.action_id}",
            action_id=action.action_id,
            incident_id=action.incident_id,
            status=status,
            summary=f"Action was not executed successfully: {detail}",
            completed_at=action.requested_at + timedelta(seconds=1),
            error_code=error_code,
        )
        return ActionExecutionRecord(action=action, result=result)
