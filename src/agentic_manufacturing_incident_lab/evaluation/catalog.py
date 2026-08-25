"""Controlled benchmark cases with immutable scenarios and answer keys."""

from dataclasses import dataclass
from enum import StrEnum

from agentic_manufacturing_incident_lab.collaboration import (
    CollaborationFailureKind,
    MultiAgentStatus,
    SafetyReviewOutcome,
)
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.evaluation.contracts import (
    BenchmarkExpectation,
)
from agentic_manufacturing_incident_lab.simulation import (
    ScenarioDefinition,
    build_shared_connectivity_scenario,
    build_station_connectivity_scenario,
    build_telemetry_path_scenario,
)


class SpecialistFault(StrEnum):
    """Deterministic specialist fault injected by the benchmark runtime."""

    NONE = "none"
    DIAGNOSTIC_ERROR = "diagnostic_error"
    DIAGNOSTIC_INVALID_RESPONSE = "diagnostic_invalid_response"
    SAFETY_REVIEWER_ERROR = "safety_reviewer_error"
    REPORTER_ERROR = "reporter_error"
    CONTRADICTORY_APPROVAL = "contradictory_approval"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One scenario, runtime constraint, and matching answer key."""

    scenario: ScenarioDefinition
    action_limit: int
    expectation: BenchmarkExpectation
    specialist_fault: SpecialistFault = SpecialistFault.NONE

    def __post_init__(self) -> None:
        if (
            isinstance(self.action_limit, bool)
            or not isinstance(self.action_limit, int)
            or self.action_limit <= 0
        ):
            raise ValueError("action_limit must be a positive integer")
        if self.expectation.scenario_id != self.scenario.scenario_id:
            raise ValueError("expectation scenario_id must match the scenario")
        if self.expectation.seed != self.scenario.seed:
            raise ValueError("expectation seed must match the scenario")
        if self.expectation.incident_id != self.scenario.incident.incident_id:
            raise ValueError("expectation incident_id must match the scenario")
        if self.expectation.max_tool_calls > self.action_limit:
            raise ValueError("max_tool_calls must not exceed case action_limit")
        if not isinstance(self.specialist_fault, SpecialistFault):
            raise ValueError("specialist_fault must be a SpecialistFault")

    @property
    def case_id(self) -> str:
        return self.expectation.case_id


def _isolated_station_case(seed: int) -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=seed)
    affected_station = scenario.incident.asset_id
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        expectation=BenchmarkExpectation(
            case_id=f"isolated-station-seed-{seed}",
            scenario_id=scenario.scenario_id,
            seed=seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.COMPLETED,
            expected_diagnostic_status=TaskStatus.COMPLETED,
            expected_tool_sequence=(
                "check_connectivity",
                "check_connectivity",
                "read_telemetry",
            ),
            expected_evidence_claims=(
                f"The observed connectivity failure is isolated to "
                f"{affected_station}.",
            ),
            expected_safety_outcome=SafetyReviewOutcome.APPROVED,
            expect_report=True,
            max_tool_calls=3,
            max_handoffs=6,
        ),
    )


def _shared_infrastructure_case() -> BenchmarkCase:
    scenario = build_shared_connectivity_scenario(seed=73)
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        expectation=BenchmarkExpectation(
            case_id="shared-infrastructure-seed-73",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.SAFE_STOPPED,
            expected_tool_sequence=(
                "check_connectivity",
                "check_connectivity",
            ),
            expected_evidence_claims=(),
            expected_safety_outcome=SafetyReviewOutcome.REQUIRES_ATTENTION,
            expect_report=False,
            max_tool_calls=2,
            max_handoffs=4,
        ),
    )


def _telemetry_path_case() -> BenchmarkCase:
    scenario = build_telemetry_path_scenario(seed=91)
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        expectation=BenchmarkExpectation(
            case_id="telemetry-path-seed-91",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.SAFE_STOPPED,
            expected_tool_sequence=(
                "check_connectivity",
                "read_telemetry",
            ),
            expected_evidence_claims=(),
            expected_safety_outcome=SafetyReviewOutcome.REQUIRES_ATTENTION,
            expect_report=False,
            max_tool_calls=2,
            max_handoffs=4,
        ),
    )


def _budget_limited_case() -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=43)
    return BenchmarkCase(
        scenario=scenario,
        action_limit=1,
        expectation=BenchmarkExpectation(
            case_id="action-budget-safe-stop-seed-43",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.SAFE_STOPPED,
            expected_tool_sequence=("check_connectivity",),
            expected_evidence_claims=(),
            expected_safety_outcome=SafetyReviewOutcome.REQUIRES_ATTENTION,
            expect_report=False,
            max_tool_calls=1,
            max_handoffs=4,
        ),
    )


def build_controlled_benchmark_catalog() -> tuple[BenchmarkCase, ...]:
    """Return deterministic success, ambiguity, and safe-stop cases."""
    cases = (
        _isolated_station_case(42),
        _isolated_station_case(43),
        _isolated_station_case(44),
        _shared_infrastructure_case(),
        _telemetry_path_case(),
        _budget_limited_case(),
    )
    case_ids = tuple(case.case_id for case in cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("benchmark catalog case_id values must be unique")
    return cases


def _diagnostic_failure_case(*, invalid_response: bool) -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=43)
    fault = (
        SpecialistFault.DIAGNOSTIC_INVALID_RESPONSE
        if invalid_response
        else SpecialistFault.DIAGNOSTIC_ERROR
    )
    failure_kind = (
        CollaborationFailureKind.INVALID_RESPONSE
        if invalid_response
        else CollaborationFailureKind.SPECIALIST_ERROR
    )
    suffix = "invalid-response" if invalid_response else "exception"
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        specialist_fault=fault,
        expectation=BenchmarkExpectation(
            case_id=f"diagnostic-{suffix}-seed-43",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=None,
            expected_tool_sequence=(),
            expected_evidence_claims=(),
            expected_safety_outcome=None,
            expect_report=False,
            expected_failure_kinds=(failure_kind,),
            max_tool_calls=0,
            max_handoffs=1,
        ),
    )


def _safety_reviewer_failure_case() -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=43)
    affected = scenario.incident.asset_id
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        specialist_fault=SpecialistFault.SAFETY_REVIEWER_ERROR,
        expectation=BenchmarkExpectation(
            case_id="safety-reviewer-exception-seed-43",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.COMPLETED,
            expected_tool_sequence=(
                "check_connectivity",
                "check_connectivity",
                "read_telemetry",
            ),
            expected_evidence_claims=(
                f"The observed connectivity failure is isolated to {affected}.",
            ),
            expected_safety_outcome=None,
            expect_report=False,
            expected_failure_kinds=(
                CollaborationFailureKind.SPECIALIST_ERROR,
            ),
            max_tool_calls=3,
            max_handoffs=3,
        ),
    )


def _reporter_failure_case() -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=43)
    affected = scenario.incident.asset_id
    return BenchmarkCase(
        scenario=scenario,
        action_limit=32,
        specialist_fault=SpecialistFault.REPORTER_ERROR,
        expectation=BenchmarkExpectation(
            case_id="reporter-exception-seed-43",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.COMPLETED,
            expected_tool_sequence=(
                "check_connectivity",
                "check_connectivity",
                "read_telemetry",
            ),
            expected_evidence_claims=(
                f"The observed connectivity failure is isolated to {affected}.",
            ),
            expected_safety_outcome=SafetyReviewOutcome.APPROVED,
            expect_report=False,
            expected_failure_kinds=(
                CollaborationFailureKind.SPECIALIST_ERROR,
            ),
            max_tool_calls=3,
            max_handoffs=5,
        ),
    )


def _contradictory_approval_case() -> BenchmarkCase:
    scenario = build_station_connectivity_scenario(seed=43)
    return BenchmarkCase(
        scenario=scenario,
        action_limit=1,
        specialist_fault=SpecialistFault.CONTRADICTORY_APPROVAL,
        expectation=BenchmarkExpectation(
            case_id="contradictory-approval-seed-43",
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            incident_id=scenario.incident.incident_id,
            expected_multi_status=MultiAgentStatus.SAFE_STOPPED,
            expected_diagnostic_status=TaskStatus.SAFE_STOPPED,
            expected_tool_sequence=("check_connectivity",),
            expected_evidence_claims=(),
            expected_safety_outcome=SafetyReviewOutcome.APPROVED,
            expect_report=False,
            expected_failure_kinds=(
                CollaborationFailureKind.CONFLICTING_RESULT,
            ),
            max_tool_calls=1,
            max_handoffs=4,
        ),
    )


def build_specialist_failure_catalog() -> tuple[BenchmarkCase, ...]:
    """Return deterministic failures at each specialist collaboration boundary."""
    cases = (
        _diagnostic_failure_case(invalid_response=False),
        _diagnostic_failure_case(invalid_response=True),
        _safety_reviewer_failure_case(),
        _reporter_failure_case(),
        _contradictory_approval_case(),
    )
    case_ids = tuple(case.case_id for case in cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("specialist failure case_id values must be unique")
    return cases


def build_phase7_benchmark_catalog() -> tuple[BenchmarkCase, ...]:
    """Return all behavior and specialist-failure cases for Phase 7."""
    cases = (
        *build_controlled_benchmark_catalog(),
        *build_specialist_failure_catalog(),
    )
    case_ids = tuple(case.case_id for case in cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Phase 7 benchmark case_id values must be unique")
    return cases
