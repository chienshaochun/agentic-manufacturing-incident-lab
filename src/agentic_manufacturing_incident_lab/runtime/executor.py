"""Execute one Action through the registry and produce an auditable record."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)
from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.models import Action, Observation
from agentic_manufacturing_incident_lab.tools import (
    IncidentScopeError,
    PermanentToolError,
    ToolParameterError,
    ToolRegistry,
    ToolRiskMismatchError,
    ToolTimeoutError,
    TransientToolError,
    UnknownToolError,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bound the number of attempts made for retryable tool failures."""

    max_attempts: int = 3

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts <= 0
        ):
            raise ValueError("max_attempts must be a positive integer")


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    """Auditable outcome of one physical invocation of a logical action."""

    attempt_number: int
    status: ActionResultStatus
    summary: str
    completed_at: datetime
    error_code: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.attempt_number, bool)
            or not isinstance(self.attempt_number, int)
            or self.attempt_number <= 0
        ):
            raise ValueError("attempt_number must be a positive integer")
        require_text(self.summary, "summary")
        require_timezone(self.completed_at, "completed_at")
        if self.status is ActionResultStatus.SUCCEEDED:
            if self.error_code is not None:
                raise ValueError("a successful attempt must not have an error_code")
        else:
            require_text(self.error_code, "error_code")


@dataclass(frozen=True, slots=True)
class ActionExecutionRecord:
    """One Action, its terminal result, and every observation it produced."""

    action: Action
    result: ActionResult
    observations: tuple[Observation, ...] = ()
    attempts: tuple[ExecutionAttempt, ...] = ()

    def __post_init__(self) -> None:
        observations = tuple(self.observations)
        attempts = tuple(self.attempts)
        if self.result.action_id != self.action.action_id:
            raise ValueError("result action_id must match action")
        if self.result.incident_id != self.action.incident_id:
            raise ValueError("result incident_id must match action")
        observation_ids = tuple(observation.observation_id for observation in observations)
        if self.result.observation_ids != observation_ids:
            raise ValueError("result observation_ids must match record observations")
        if attempts:
            if tuple(attempt.attempt_number for attempt in attempts) != tuple(
                range(1, len(attempts) + 1)
            ):
                raise ValueError("execution attempts must be consecutively numbered")
            if any(
                later.completed_at <= earlier.completed_at
                for earlier, later in zip(attempts, attempts[1:])
            ):
                raise ValueError("execution attempts must have increasing timestamps")
            terminal_attempt = attempts[-1]
            if terminal_attempt.status is not self.result.status:
                raise ValueError("final attempt status must match action result")
            if terminal_attempt.completed_at != self.result.completed_at:
                raise ValueError("final attempt time must match action result")
            if terminal_attempt.error_code != self.result.error_code:
                raise ValueError("final attempt error_code must match action result")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "attempts", attempts)


class ActionExecutor:
    """Convert registry responses and expected tool errors into ActionResults."""

    __slots__ = ("_registry", "_retry_policy")

    def __init__(
        self,
        registry: ToolRegistry,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._retry_policy = retry_policy or RetryPolicy()

    def execute(self, action: Action) -> ActionExecutionRecord:
        """Execute one action and always record known validation or lookup failures."""
        attempts: list[ExecutionAttempt] = []
        for attempt_number in range(1, self._retry_policy.max_attempts + 1):
            try:
                response = self._registry.execute(action)
            except UnknownToolError as error:
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.DENIED,
                    error_code="tool_not_allowed",
                    detail=str(error),
                )
            except ToolParameterError as error:
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.DENIED,
                    error_code="invalid_parameters",
                    detail=str(error),
                )
            except ToolRiskMismatchError as error:
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.DENIED,
                    error_code="risk_mismatch",
                    detail=str(error),
                )
            except IncidentScopeError as error:
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.DENIED,
                    error_code="incident_scope_mismatch",
                    detail=str(error),
                )
            except KeyError as error:
                detail = str(error.args[0]) if error.args else "unknown lookup failure"
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.FAILED,
                    error_code="unknown_asset",
                    detail=detail,
                )
            except PermanentToolError as error:
                return self._error_record(
                    action,
                    attempts,
                    attempt_number=attempt_number,
                    status=ActionResultStatus.FAILED,
                    error_code="permanent_tool_error",
                    detail=str(error),
                )
            except ToolTimeoutError as error:
                attempts.append(
                    self._failure_attempt(
                        action,
                        attempt_number=attempt_number,
                        status=ActionResultStatus.TIMED_OUT,
                        error_code="tool_timeout",
                        detail=str(error),
                    )
                )
                if attempt_number == self._retry_policy.max_attempts:
                    return self._terminal_error_record(action, attempts)
                continue
            except TransientToolError as error:
                attempts.append(
                    self._failure_attempt(
                        action,
                        attempt_number=attempt_number,
                        status=ActionResultStatus.FAILED,
                        error_code="transient_tool_error",
                        detail=str(error),
                    )
                )
                if attempt_number == self._retry_policy.max_attempts:
                    return self._terminal_error_record(action, attempts)
                continue

            observations = tuple(response.observations)
            completed_at = self._completion_time(
                action,
                observations,
                attempt_number=attempt_number,
            )
            attempts.append(
                ExecutionAttempt(
                    attempt_number=attempt_number,
                    status=ActionResultStatus.SUCCEEDED,
                    summary=response.summary,
                    completed_at=completed_at,
                )
            )
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
                attempts=tuple(attempts),
            )

        raise AssertionError("positive max_attempts must produce a terminal result")

    @staticmethod
    def _completion_time(
        action: Action,
        observations: tuple[Observation, ...],
        *,
        attempt_number: int,
    ) -> datetime:
        earliest_completion = action.requested_at + timedelta(seconds=attempt_number)
        if not observations:
            return earliest_completion
        return max(
            earliest_completion,
            max(observation.observed_at for observation in observations),
        )

    @classmethod
    def _error_record(
        cls,
        action: Action,
        previous_attempts: list[ExecutionAttempt],
        *,
        attempt_number: int,
        status: ActionResultStatus,
        error_code: str,
        detail: str,
    ) -> ActionExecutionRecord:
        attempts = [
            *previous_attempts,
            cls._failure_attempt(
                action,
                attempt_number=attempt_number,
                status=status,
                error_code=error_code,
                detail=detail,
            ),
        ]
        return cls._terminal_error_record(action, attempts)

    @staticmethod
    def _failure_attempt(
        action: Action,
        *,
        attempt_number: int,
        status: ActionResultStatus,
        error_code: str,
        detail: str,
    ) -> ExecutionAttempt:
        return ExecutionAttempt(
            attempt_number=attempt_number,
            status=status,
            summary=f"Tool attempt failed: {detail}",
            completed_at=action.requested_at + timedelta(seconds=attempt_number),
            error_code=error_code,
        )

    @staticmethod
    def _terminal_error_record(
        action: Action,
        attempts: list[ExecutionAttempt],
    ) -> ActionExecutionRecord:
        terminal_attempt = attempts[-1]
        result = ActionResult(
            result_id=f"RES-{action.action_id}",
            action_id=action.action_id,
            incident_id=action.incident_id,
            status=terminal_attempt.status,
            summary=terminal_attempt.summary,
            completed_at=terminal_attempt.completed_at,
            error_code=terminal_attempt.error_code,
        )
        return ActionExecutionRecord(
            action=action,
            result=result,
            attempts=tuple(attempts),
        )
