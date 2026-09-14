"""Operational metrics that measure how an agent reached its outcome."""

from dataclasses import dataclass

from agentic_manufacturing_incident_lab.domain import (
    ActionResultStatus,
    HypothesisStatus,
)
from agentic_manufacturing_incident_lab.recovery import RecoveryDisposition
from agentic_manufacturing_incident_lab.runtime import InvestigationRun


@dataclass(frozen=True, slots=True)
class AgentOperationalMetrics:
    """Process-quality measurements independent from answer-key correctness."""

    hypothesis_resolution_rate: float | None
    unsupported_claim_rate: float
    redundant_tool_call_rate: float
    actions_to_evidence: int | None
    recovery_success_rate: float | None


def measure_agent_operations(
    run: InvestigationRun | None,
) -> AgentOperationalMetrics:
    """Measure hypothesis, claim, tool-use, evidence, and recovery behavior."""
    if run is None:
        return AgentOperationalMetrics(None, 0.0, 0.0, None, None)

    hypothesis_resolution_rate = None
    if run.hypotheses:
        resolved = sum(
            item.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.REJECTED}
            for item in run.hypotheses
        )
        hypothesis_resolution_rate = resolved / len(run.hypotheses)

    known_observations = {item.observation_id for item in run.observations}
    supported = tuple(
        item
        for item in run.hypotheses
        if item.status is HypothesisStatus.SUPPORTED
    )
    unsupported_claims = 0
    for evidence in run.evidence:
        evidence_observations = set(evidence.observation_ids)
        grounded = evidence_observations.issubset(known_observations)
        hypothesis_backed = any(
            set(item.supporting_observation_ids).issubset(evidence_observations)
            for item in supported
        )
        if not grounded or not hypothesis_backed:
            unsupported_claims += 1
    unsupported_claim_rate = (
        unsupported_claims / len(run.evidence) if run.evidence else 0.0
    )

    seen: set[tuple[str, tuple[tuple[str, object], ...]]] = set()
    duplicate_count = 0
    for record in run.executions:
        signature = (
            record.action.tool_name,
            tuple(sorted(record.action.parameters.items())),
        )
        if signature in seen:
            duplicate_count += 1
        seen.add(signature)
    redundant_tool_call_rate = (
        duplicate_count / len(run.executions) if run.executions else 0.0
    )

    recovery_attempts = tuple(
        item
        for item in run.recovery_assessments
        if item.disposition is RecoveryDisposition.TRY_ALTERNATIVE
    )
    recovery_success_rate = None
    if recovery_attempts:
        successful = 0
        for assessment in recovery_attempts:
            if any(
                record.action.tool_name == assessment.alternative_tool_name
                and dict(record.action.parameters)
                == dict(assessment.alternative_parameters)
                and record.result.status is ActionResultStatus.SUCCEEDED
                for record in run.executions
            ):
                successful += 1
        recovery_success_rate = successful / len(recovery_attempts)

    return AgentOperationalMetrics(
        hypothesis_resolution_rate=hypothesis_resolution_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        redundant_tool_call_rate=redundant_tool_call_rate,
        actions_to_evidence=len(run.executions) if run.evidence else None,
        recovery_success_rate=recovery_success_rate,
    )

