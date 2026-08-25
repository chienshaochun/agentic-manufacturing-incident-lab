"""Immutable role and handoff contracts for multi-agent collaboration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


class AgentRole(StrEnum):
    """One bounded responsibility in the incident investigation team."""

    COORDINATOR = "coordinator"
    DIAGNOSTIC = "diagnostic"
    SAFETY_REVIEWER = "safety_reviewer"
    REPORTER = "reporter"


class HandoffKind(StrEnum):
    """Purpose and expected route of one structured handoff."""

    INVESTIGATION_REQUEST = "investigation_request"
    DIAGNOSTIC_RESULT = "diagnostic_result"
    SAFETY_REVIEW_REQUEST = "safety_review_request"
    SAFETY_REVIEW_RESULT = "safety_review_result"
    REPORT_REQUEST = "report_request"
    REPORT_RESULT = "report_result"


_ROUTES: dict[HandoffKind, tuple[AgentRole, AgentRole]] = {
    HandoffKind.INVESTIGATION_REQUEST: (
        AgentRole.COORDINATOR,
        AgentRole.DIAGNOSTIC,
    ),
    HandoffKind.DIAGNOSTIC_RESULT: (
        AgentRole.DIAGNOSTIC,
        AgentRole.COORDINATOR,
    ),
    HandoffKind.SAFETY_REVIEW_REQUEST: (
        AgentRole.COORDINATOR,
        AgentRole.SAFETY_REVIEWER,
    ),
    HandoffKind.SAFETY_REVIEW_RESULT: (
        AgentRole.SAFETY_REVIEWER,
        AgentRole.COORDINATOR,
    ),
    HandoffKind.REPORT_REQUEST: (
        AgentRole.COORDINATOR,
        AgentRole.REPORTER,
    ),
    HandoffKind.REPORT_RESULT: (
        AgentRole.REPORTER,
        AgentRole.COORDINATOR,
    ),
}

_RESPONSE_TO_REQUEST: dict[HandoffKind, HandoffKind] = {
    HandoffKind.DIAGNOSTIC_RESULT: HandoffKind.INVESTIGATION_REQUEST,
    HandoffKind.SAFETY_REVIEW_RESULT: HandoffKind.SAFETY_REVIEW_REQUEST,
    HandoffKind.REPORT_RESULT: HandoffKind.REPORT_REQUEST,
}


@dataclass(frozen=True, slots=True)
class AgentHandoff:
    """One traceable message crossing an agent responsibility boundary."""

    handoff_id: str
    incident_id: str
    kind: HandoffKind
    sender: AgentRole
    recipient: AgentRole
    purpose: str
    created_at: datetime
    observation_ids: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    in_reply_to: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("handoff_id", "incident_id", "purpose"):
            require_text(getattr(self, field_name), field_name)
        require_timezone(self.created_at, "created_at")
        if self.sender is self.recipient:
            raise ValueError("handoff sender and recipient must be different roles")
        expected_route = _ROUTES.get(self.kind)
        if expected_route != (self.sender, self.recipient):
            raise ValueError(
                f"{self.kind.value} must route from "
                f"{expected_route[0].value} to {expected_route[1].value}"
            )

        observation_ids = self._validated_ids(
            self.observation_ids,
            "observation_ids",
        )
        action_ids = self._validated_ids(self.action_ids, "action_ids")
        is_response = self.kind in _RESPONSE_TO_REQUEST
        if is_response:
            require_text(self.in_reply_to, "in_reply_to")
        elif self.in_reply_to is not None:
            raise ValueError("request handoff must not contain in_reply_to")

        object.__setattr__(self, "observation_ids", observation_ids)
        object.__setattr__(self, "action_ids", action_ids)

    @staticmethod
    def _validated_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
        normalized = tuple(values)
        for value in normalized:
            require_text(value, field_name)
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{field_name} must not contain duplicates")
        return normalized


@dataclass(frozen=True, slots=True)
class HandoffLedger:
    """Ordered, immutable communication history for one incident."""

    incident_id: str
    handoffs: tuple[AgentHandoff, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.incident_id, "incident_id")
        handoffs = tuple(self.handoffs)
        handoffs_by_id: dict[str, AgentHandoff] = {}
        replied_request_ids: set[str] = set()
        previous_time: datetime | None = None

        for handoff in handoffs:
            if handoff.incident_id != self.incident_id:
                raise ValueError("all handoffs must match the ledger incident")
            if handoff.handoff_id in handoffs_by_id:
                raise ValueError("handoffs must have unique handoff_id values")
            if previous_time is not None and handoff.created_at <= previous_time:
                raise ValueError("handoff timestamps must move forward")

            if handoff.in_reply_to is not None:
                request = handoffs_by_id.get(handoff.in_reply_to)
                if request is None:
                    raise ValueError("response must reference an earlier request")
                expected_request_kind = _RESPONSE_TO_REQUEST[handoff.kind]
                if request.kind is not expected_request_kind:
                    raise ValueError("response kind does not match referenced request")
                if (
                    request.sender is not handoff.recipient
                    or request.recipient is not handoff.sender
                ):
                    raise ValueError("response route must reverse the request route")
                if request.handoff_id in replied_request_ids:
                    raise ValueError("a request may only receive one response")
                replied_request_ids.add(request.handoff_id)

            handoffs_by_id[handoff.handoff_id] = handoff
            previous_time = handoff.created_at

        object.__setattr__(self, "handoffs", handoffs)

    def append(self, handoff: AgentHandoff) -> HandoffLedger:
        """Return a new ledger containing one additional validated handoff."""
        return HandoffLedger(
            incident_id=self.incident_id,
            handoffs=(*self.handoffs, handoff),
        )

    @property
    def pending_requests(self) -> tuple[AgentHandoff, ...]:
        """Return requests that do not yet have a matching response."""
        replied_request_ids = {
            handoff.in_reply_to
            for handoff in self.handoffs
            if handoff.in_reply_to is not None
        }
        return tuple(
            handoff
            for handoff in self.handoffs
            if handoff.kind not in _RESPONSE_TO_REQUEST
            and handoff.handoff_id not in replied_request_ids
        )
