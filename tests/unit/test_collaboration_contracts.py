from datetime import UTC, datetime, timedelta

import pytest

from agentic_manufacturing_incident_lab.collaboration import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
    HandoffLedger,
)

STARTED_AT = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)
INCIDENT_ID = "INC-COLLAB-001"


def make_handoff(
    kind: HandoffKind,
    *,
    handoff_id: str | None = None,
    created_offset: int = 1,
    in_reply_to: str | None = None,
    incident_id: str = INCIDENT_ID,
    observation_ids: tuple[str, ...] = (),
    action_ids: tuple[str, ...] = (),
) -> AgentHandoff:
    routes = {
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
    sender, recipient = routes[kind]
    return AgentHandoff(
        handoff_id=handoff_id or f"HND-{kind.value.upper()}",
        incident_id=incident_id,
        kind=kind,
        sender=sender,
        recipient=recipient,
        purpose=f"Handle {kind.value}.",
        created_at=STARTED_AT + timedelta(seconds=created_offset),
        observation_ids=observation_ids,
        action_ids=action_ids,
        in_reply_to=in_reply_to,
    )


def test_agent_roles_define_four_separate_responsibilities() -> None:
    assert tuple(role.value for role in AgentRole) == (
        "coordinator",
        "diagnostic",
        "safety_reviewer",
        "reporter",
    )


@pytest.mark.parametrize(
    "kind",
    [
        HandoffKind.INVESTIGATION_REQUEST,
        HandoffKind.SAFETY_REVIEW_REQUEST,
        HandoffKind.REPORT_REQUEST,
    ],
)
def test_request_handoff_does_not_require_a_reply_reference(
    kind: HandoffKind,
) -> None:
    handoff = make_handoff(kind)

    assert handoff.in_reply_to is None


@pytest.mark.parametrize(
    "kind",
    [
        HandoffKind.DIAGNOSTIC_RESULT,
        HandoffKind.SAFETY_REVIEW_RESULT,
        HandoffKind.REPORT_RESULT,
    ],
)
def test_result_handoff_requires_a_reply_reference(kind: HandoffKind) -> None:
    with pytest.raises(ValueError, match="in_reply_to must not be blank"):
        make_handoff(kind)


def test_handoff_normalizes_reference_lists_to_tuples() -> None:
    handoff = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        observation_ids=["OBS-001"],  # type: ignore[arg-type]
        action_ids=["ACT-001"],  # type: ignore[arg-type]
    )

    assert handoff.observation_ids == ("OBS-001",)
    assert handoff.action_ids == ("ACT-001",)


@pytest.mark.parametrize("field_name", ["observation_ids", "action_ids"])
def test_handoff_rejects_duplicate_references(field_name: str) -> None:
    values = {field_name: ("REF-001", "REF-001")}

    with pytest.raises(ValueError, match="must not contain duplicates"):
        make_handoff(HandoffKind.INVESTIGATION_REQUEST, **values)  # type: ignore[arg-type]


def test_handoff_rejects_route_outside_role_boundaries() -> None:
    with pytest.raises(ValueError, match="must route from coordinator to diagnostic"):
        AgentHandoff(
            handoff_id="HND-001",
            incident_id=INCIDENT_ID,
            kind=HandoffKind.INVESTIGATION_REQUEST,
            sender=AgentRole.REPORTER,
            recipient=AgentRole.DIAGNOSTIC,
            purpose="Reporter must not assign diagnostic work.",
            created_at=STARTED_AT,
        )


def test_request_rejects_reply_reference() -> None:
    with pytest.raises(ValueError, match="must not contain in_reply_to"):
        make_handoff(
            HandoffKind.INVESTIGATION_REQUEST,
            in_reply_to="HND-OLDER",
        )


def test_empty_ledger_has_no_pending_requests() -> None:
    ledger = HandoffLedger(incident_id=INCIDENT_ID)

    assert ledger.handoffs == ()
    assert ledger.pending_requests == ()


def test_ledger_tracks_valid_request_and_response() -> None:
    request = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        handoff_id="HND-001",
    )
    response = make_handoff(
        HandoffKind.DIAGNOSTIC_RESULT,
        handoff_id="HND-002",
        created_offset=2,
        in_reply_to=request.handoff_id,
        observation_ids=("OBS-001",),
    )

    ledger = HandoffLedger(INCIDENT_ID, (request, response))

    assert ledger.handoffs == (request, response)
    assert ledger.pending_requests == ()


def test_append_returns_new_ledger_without_mutating_previous_version() -> None:
    original = HandoffLedger(incident_id=INCIDENT_ID)
    request = make_handoff(HandoffKind.REPORT_REQUEST)

    updated = original.append(request)

    assert original.handoffs == ()
    assert updated.handoffs == (request,)
    assert updated.pending_requests == (request,)


def test_ledger_rejects_cross_incident_handoff() -> None:
    handoff = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        incident_id="INC-OTHER",
    )

    with pytest.raises(ValueError, match="match the ledger incident"):
        HandoffLedger(INCIDENT_ID, (handoff,))


def test_ledger_rejects_duplicate_handoff_ids() -> None:
    first = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        handoff_id="HND-001",
    )
    second = make_handoff(
        HandoffKind.SAFETY_REVIEW_REQUEST,
        handoff_id="HND-001",
        created_offset=2,
    )

    with pytest.raises(ValueError, match="unique handoff_id"):
        HandoffLedger(INCIDENT_ID, (first, second))


def test_ledger_requires_forward_moving_timestamps() -> None:
    first = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        handoff_id="HND-001",
        created_offset=2,
    )
    second = make_handoff(
        HandoffKind.SAFETY_REVIEW_REQUEST,
        handoff_id="HND-002",
        created_offset=1,
    )

    with pytest.raises(ValueError, match="timestamps must move forward"):
        HandoffLedger(INCIDENT_ID, (first, second))


def test_response_must_reference_earlier_request() -> None:
    response = make_handoff(
        HandoffKind.DIAGNOSTIC_RESULT,
        in_reply_to="HND-MISSING",
    )

    with pytest.raises(ValueError, match="earlier request"):
        HandoffLedger(INCIDENT_ID, (response,))


def test_response_kind_must_match_request_kind() -> None:
    request = make_handoff(
        HandoffKind.REPORT_REQUEST,
        handoff_id="HND-001",
    )
    response = make_handoff(
        HandoffKind.DIAGNOSTIC_RESULT,
        handoff_id="HND-002",
        created_offset=2,
        in_reply_to=request.handoff_id,
    )

    with pytest.raises(ValueError, match="response kind does not match"):
        HandoffLedger(INCIDENT_ID, (request, response))


def test_request_may_only_receive_one_response() -> None:
    request = make_handoff(
        HandoffKind.INVESTIGATION_REQUEST,
        handoff_id="HND-001",
    )
    first_response = make_handoff(
        HandoffKind.DIAGNOSTIC_RESULT,
        handoff_id="HND-002",
        created_offset=2,
        in_reply_to=request.handoff_id,
    )
    second_response = make_handoff(
        HandoffKind.DIAGNOSTIC_RESULT,
        handoff_id="HND-003",
        created_offset=3,
        in_reply_to=request.handoff_id,
    )

    with pytest.raises(ValueError, match="only receive one response"):
        HandoffLedger(INCIDENT_ID, (request, first_response, second_response))
