"""Versioned JSON checkpoints for complete or partial investigation runs."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import tempfile
from datetime import datetime
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import Any, TypeVar, cast

from agentic_manufacturing_incident_lab.agent.memory import (
    MemoryFact,
    OpenQuestion,
    StepBudget,
    WorkingMemory,
)
from agentic_manufacturing_incident_lab.domain.execution import (
    ActionResult,
    ActionResultStatus,
)
from agentic_manufacturing_incident_lab.domain.models import (
    Action,
    ActionRisk,
    Evidence,
    Incident,
    IncidentSeverity,
    Observation,
    ObservationKind,
    ScalarValue,
)
from agentic_manufacturing_incident_lab.domain.task import TaskState, TaskStatus
from agentic_manufacturing_incident_lab.runtime.executor import (
    ActionExecutionRecord,
    ExecutionAttempt,
)
from agentic_manufacturing_incident_lab.runtime.run import InvestigationRun
from agentic_manufacturing_incident_lab.safety import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    SafetyAssessment,
    SafetyDisposition,
)

CHECKPOINT_SCHEMA_VERSION = 2
CHECKPOINT_KIND = "agentic_manufacturing_investigation"


class CheckpointError(ValueError):
    """Raised when checkpoint JSON is malformed, incompatible, or inconsistent."""


def serialize_checkpoint(run: InvestigationRun) -> str:
    """Serialize an investigation into deterministic, integrity-tagged JSON."""
    run_data = _encode_run(run)
    envelope = {
        "kind": CHECKPOINT_KIND,
        "payload_sha256": _checksum(run_data),
        "run": run_data,
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def deserialize_checkpoint(checkpoint_json: str) -> InvestigationRun:
    """Validate checkpoint JSON and reconstruct immutable domain records."""
    if not isinstance(checkpoint_json, str):
        raise CheckpointError("checkpoint must be a JSON string")
    try:
        raw = json.loads(checkpoint_json, object_pairs_hook=_object_without_duplicates)
    except (json.JSONDecodeError, CheckpointError) as error:
        raise CheckpointError(f"invalid checkpoint JSON: {error}") from error

    envelope = _require_object(raw, "checkpoint")
    _require_exact_keys(
        envelope,
        {"kind", "payload_sha256", "run", "schema_version"},
        "checkpoint",
    )
    version = envelope["schema_version"]
    if type(version) is not int or version != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointError(f"unsupported checkpoint schema_version: {version!r}")
    if envelope["kind"] != CHECKPOINT_KIND:
        raise CheckpointError(f"unsupported checkpoint kind: {envelope['kind']!r}")

    run_data = _require_object(envelope["run"], "checkpoint.run")
    checksum = envelope["payload_sha256"]
    if not isinstance(checksum, str) or not hmac.compare_digest(
        checksum,
        _checksum(run_data),
    ):
        raise CheckpointError("checkpoint payload checksum mismatch")

    try:
        return _decode_run(run_data)
    except CheckpointError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise CheckpointError(f"invalid checkpoint payload: {error}") from error


def save_checkpoint(path: str | PathLike[str], run: InvestigationRun) -> Path:
    """Atomically write one UTF-8 checkpoint and return its resolved path."""
    destination = Path(path).resolve()
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialize_checkpoint(run))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(destination)
    except OSError as error:
        raise CheckpointError(f"could not write checkpoint: {error}") from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return destination


def load_checkpoint(path: str | PathLike[str]) -> InvestigationRun:
    """Load and validate one UTF-8 checkpoint file."""
    source = Path(path).resolve()
    try:
        checkpoint_json = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CheckpointError(f"could not read checkpoint: {error}") from error
    return deserialize_checkpoint(checkpoint_json)


def _checksum(run_data: dict[str, Any]) -> str:
    canonical = json.dumps(
        run_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _encode_run(run: InvestigationRun) -> dict[str, Any]:
    return {
        "approval_decisions": [
            _encode_approval_decision(item) for item in run.approval_decisions
        ],
        "approval_requests": [
            _encode_approval_request(item) for item in run.approval_requests
        ],
        "evidence": [_encode_evidence(item) for item in run.evidence],
        "executions": [_encode_execution(record) for record in run.executions],
        "incident": _encode_incident(run.incident),
        "memory_states": [
            _encode_working_memory(memory) for memory in run.memory_states
        ],
        "safety_assessments": [
            _encode_safety_assessment(item) for item in run.safety_assessments
        ],
        "task_states": [_encode_task_state(state) for state in run.task_states],
    }


def _encode_incident(incident: Incident) -> dict[str, Any]:
    return {
        "asset_id": incident.asset_id,
        "description": incident.description,
        "goal": incident.goal,
        "incident_id": incident.incident_id,
        "reported_at": incident.reported_at.isoformat(),
        "severity": incident.severity.value,
        "title": incident.title,
    }


def _encode_task_state(state: TaskState) -> dict[str, Any]:
    return {
        "incident_id": state.incident_id,
        "reason": state.reason,
        "revision": state.revision,
        "status": state.status.value,
        "task_id": state.task_id,
        "updated_at": state.updated_at.isoformat(),
    }


def _encode_execution(record: ActionExecutionRecord) -> dict[str, Any]:
    result = record.result
    return {
        "action": _encode_action(record.action),
        "attempts": [
            {
                "attempt_number": attempt.attempt_number,
                "completed_at": attempt.completed_at.isoformat(),
                "error_code": attempt.error_code,
                "status": attempt.status.value,
                "summary": attempt.summary,
            }
            for attempt in record.attempts
        ],
        "observations": [
            {
                "incident_id": observation.incident_id,
                "kind": observation.kind.value,
                "observation_id": observation.observation_id,
                "observed_at": observation.observed_at.isoformat(),
                "source": observation.source,
                "summary": observation.summary,
                "values": dict(observation.values),
            }
            for observation in record.observations
        ],
        "result": {
            "action_id": result.action_id,
            "completed_at": result.completed_at.isoformat(),
            "error_code": result.error_code,
            "incident_id": result.incident_id,
            "observation_ids": list(result.observation_ids),
            "result_id": result.result_id,
            "status": result.status.value,
            "summary": result.summary,
        },
    }


def _encode_action(action: Action) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "incident_id": action.incident_id,
        "parameters": dict(action.parameters),
        "rationale": action.rationale,
        "requested_at": action.requested_at.isoformat(),
        "risk": action.risk.value,
        "tool_name": action.tool_name,
    }


def _encode_safety_assessment(assessment: SafetyAssessment) -> dict[str, Any]:
    return {
        "action_id": assessment.action_id,
        "assessed_at": assessment.assessed_at.isoformat(),
        "assessment_id": assessment.assessment_id,
        "disposition": assessment.disposition.value,
        "incident_id": assessment.incident_id,
        "policy_name": assessment.policy_name,
        "rationale": assessment.rationale,
    }


def _encode_approval_request(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "action": _encode_action(request.action),
        "assessment": _encode_safety_assessment(request.assessment),
        "reason": request.reason,
        "request_id": request.request_id,
        "requested_at": request.requested_at.isoformat(),
    }


def _encode_approval_decision(decision: ApprovalDecision) -> dict[str, Any]:
    return {
        "decided_at": decision.decided_at.isoformat(),
        "decided_by": decision.decided_by,
        "decision_id": decision.decision_id,
        "outcome": decision.outcome.value,
        "rationale": decision.rationale,
        "request": _encode_approval_request(decision.request),
    }


def _encode_evidence(evidence: Evidence) -> dict[str, Any]:
    return {
        "claim": evidence.claim,
        "confidence": evidence.confidence,
        "created_at": evidence.created_at.isoformat(),
        "evidence_id": evidence.evidence_id,
        "incident_id": evidence.incident_id,
        "observation_ids": list(evidence.observation_ids),
    }


def _encode_working_memory(memory: WorkingMemory) -> dict[str, Any]:
    return {
        "facts": [
            {
                "fact_id": fact.fact_id,
                "incident_id": fact.incident_id,
                "observation_ids": list(fact.observation_ids),
                "recorded_at": fact.recorded_at.isoformat(),
                "statement": fact.statement,
            }
            for fact in memory.facts
        ],
        "incident_id": memory.incident_id,
        "open_questions": [
            {
                "incident_id": question.incident_id,
                "opened_at": question.opened_at.isoformat(),
                "prompt": question.prompt,
                "question_id": question.question_id,
            }
            for question in memory.open_questions
        ],
        "revision": memory.revision,
        "step_budget": {
            "action_limit": memory.step_budget.action_limit,
            "actions_used": memory.step_budget.actions_used,
        },
        "task_id": memory.task_id,
        "updated_at": memory.updated_at.isoformat(),
    }


def _decode_run(data: dict[str, Any]) -> InvestigationRun:
    _require_exact_keys(
        data,
        {
            "approval_decisions",
            "approval_requests",
            "evidence",
            "executions",
            "incident",
            "memory_states",
            "safety_assessments",
            "task_states",
        },
        "run",
    )
    return InvestigationRun(
        incident=_decode_incident(_require_object(data["incident"], "incident")),
        task_states=tuple(
            _decode_task_state(_require_object(item, "task_state"))
            for item in _require_list(data["task_states"], "task_states")
        ),
        executions=tuple(
            _decode_execution(_require_object(item, "execution"))
            for item in _require_list(data["executions"], "executions")
        ),
        evidence=tuple(
            _decode_evidence(_require_object(item, "evidence"))
            for item in _require_list(data["evidence"], "evidence")
        ),
        memory_states=tuple(
            _decode_working_memory(_require_object(item, "working_memory"))
            for item in _require_list(data["memory_states"], "memory_states")
        ),
        safety_assessments=tuple(
            _decode_safety_assessment(_require_object(item, "safety_assessment"))
            for item in _require_list(
                data["safety_assessments"],
                "safety_assessments",
            )
        ),
        approval_requests=tuple(
            _decode_approval_request(_require_object(item, "approval_request"))
            for item in _require_list(data["approval_requests"], "approval_requests")
        ),
        approval_decisions=tuple(
            _decode_approval_decision(_require_object(item, "approval_decision"))
            for item in _require_list(
                data["approval_decisions"],
                "approval_decisions",
            )
        ),
    )


def _decode_incident(data: dict[str, Any]) -> Incident:
    _require_exact_keys(
        data,
        {
            "asset_id",
            "description",
            "goal",
            "incident_id",
            "reported_at",
            "severity",
            "title",
        },
        "incident",
    )
    return Incident(
        incident_id=_require_string(data["incident_id"], "incident_id"),
        title=_require_string(data["title"], "title"),
        description=_require_string(data["description"], "description"),
        asset_id=_require_string(data["asset_id"], "asset_id"),
        severity=_decode_enum(IncidentSeverity, data["severity"], "severity"),
        reported_at=_decode_datetime(data["reported_at"], "reported_at"),
        goal=_require_string(data["goal"], "goal"),
    )


def _decode_task_state(data: dict[str, Any]) -> TaskState:
    _require_exact_keys(
        data,
        {"incident_id", "reason", "revision", "status", "task_id", "updated_at"},
        "task_state",
    )
    return TaskState(
        task_id=_require_string(data["task_id"], "task_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        status=_decode_enum(TaskStatus, data["status"], "status"),
        revision=_require_integer(data["revision"], "revision"),
        updated_at=_decode_datetime(data["updated_at"], "updated_at"),
        reason=_require_string(data["reason"], "reason"),
    )


def _decode_execution(data: dict[str, Any]) -> ActionExecutionRecord:
    _require_exact_keys(
        data,
        {"action", "attempts", "observations", "result"},
        "execution",
    )
    action = _decode_action(_require_object(data["action"], "action"))

    result_data = _require_object(data["result"], "result")
    _require_exact_keys(
        result_data,
        {
            "action_id",
            "completed_at",
            "error_code",
            "incident_id",
            "observation_ids",
            "result_id",
            "status",
            "summary",
        },
        "action_result",
    )
    error_code = result_data["error_code"]
    if error_code is not None:
        error_code = _require_string(error_code, "error_code")
    result = ActionResult(
        result_id=_require_string(result_data["result_id"], "result_id"),
        action_id=_require_string(result_data["action_id"], "action_id"),
        incident_id=_require_string(result_data["incident_id"], "incident_id"),
        status=_decode_enum(ActionResultStatus, result_data["status"], "status"),
        summary=_require_string(result_data["summary"], "summary"),
        completed_at=_decode_datetime(result_data["completed_at"], "completed_at"),
        observation_ids=_decode_string_tuple(
            result_data["observation_ids"],
            "observation_ids",
        ),
        error_code=error_code,
    )

    observations = tuple(
        _decode_observation(_require_object(item, "observation"))
        for item in _require_list(data["observations"], "observations")
    )
    attempts = tuple(
        _decode_execution_attempt(_require_object(item, "execution_attempt"))
        for item in _require_list(data["attempts"], "attempts")
    )
    return ActionExecutionRecord(
        action=action,
        result=result,
        observations=observations,
        attempts=attempts,
    )


def _decode_execution_attempt(data: dict[str, Any]) -> ExecutionAttempt:
    _require_exact_keys(
        data,
        {"attempt_number", "completed_at", "error_code", "status", "summary"},
        "execution_attempt",
    )
    error_code = data["error_code"]
    if error_code is not None:
        error_code = _require_string(error_code, "error_code")
    return ExecutionAttempt(
        attempt_number=_require_integer(data["attempt_number"], "attempt_number"),
        status=_decode_enum(ActionResultStatus, data["status"], "status"),
        summary=_require_string(data["summary"], "summary"),
        completed_at=_decode_datetime(data["completed_at"], "completed_at"),
        error_code=error_code,
    )


def _decode_action(action_data: dict[str, Any]) -> Action:
    _require_exact_keys(
        action_data,
        {
            "action_id",
            "incident_id",
            "parameters",
            "rationale",
            "requested_at",
            "risk",
            "tool_name",
        },
        "action",
    )
    return Action(
        action_id=_require_string(action_data["action_id"], "action_id"),
        incident_id=_require_string(action_data["incident_id"], "incident_id"),
        tool_name=_require_string(action_data["tool_name"], "tool_name"),
        rationale=_require_string(action_data["rationale"], "rationale"),
        risk=_decode_enum(ActionRisk, action_data["risk"], "risk"),
        requested_at=_decode_datetime(action_data["requested_at"], "requested_at"),
        parameters=_decode_scalar_mapping(action_data["parameters"], "parameters"),
    )


def _decode_safety_assessment(data: dict[str, Any]) -> SafetyAssessment:
    _require_exact_keys(
        data,
        {
            "action_id",
            "assessed_at",
            "assessment_id",
            "disposition",
            "incident_id",
            "policy_name",
            "rationale",
        },
        "safety_assessment",
    )
    return SafetyAssessment(
        assessment_id=_require_string(data["assessment_id"], "assessment_id"),
        action_id=_require_string(data["action_id"], "action_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        policy_name=_require_string(data["policy_name"], "policy_name"),
        disposition=_decode_enum(
            SafetyDisposition,
            data["disposition"],
            "disposition",
        ),
        rationale=_require_string(data["rationale"], "rationale"),
        assessed_at=_decode_datetime(data["assessed_at"], "assessed_at"),
    )


def _decode_approval_request(data: dict[str, Any]) -> ApprovalRequest:
    _require_exact_keys(
        data,
        {"action", "assessment", "reason", "request_id", "requested_at"},
        "approval_request",
    )
    return ApprovalRequest(
        request_id=_require_string(data["request_id"], "request_id"),
        action=_decode_action(_require_object(data["action"], "action")),
        assessment=_decode_safety_assessment(
            _require_object(data["assessment"], "safety_assessment")
        ),
        reason=_require_string(data["reason"], "reason"),
        requested_at=_decode_datetime(data["requested_at"], "requested_at"),
    )


def _decode_approval_decision(data: dict[str, Any]) -> ApprovalDecision:
    _require_exact_keys(
        data,
        {"decided_at", "decided_by", "decision_id", "outcome", "rationale", "request"},
        "approval_decision",
    )
    return ApprovalDecision(
        decision_id=_require_string(data["decision_id"], "decision_id"),
        request=_decode_approval_request(
            _require_object(data["request"], "approval_request")
        ),
        outcome=_decode_enum(ApprovalOutcome, data["outcome"], "outcome"),
        decided_by=_require_string(data["decided_by"], "decided_by"),
        rationale=_require_string(data["rationale"], "rationale"),
        decided_at=_decode_datetime(data["decided_at"], "decided_at"),
    )


def _decode_observation(data: dict[str, Any]) -> Observation:
    _require_exact_keys(
        data,
        {
            "incident_id",
            "kind",
            "observation_id",
            "observed_at",
            "source",
            "summary",
            "values",
        },
        "observation",
    )
    return Observation(
        observation_id=_require_string(data["observation_id"], "observation_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        source=_require_string(data["source"], "source"),
        kind=_decode_enum(ObservationKind, data["kind"], "kind"),
        summary=_require_string(data["summary"], "summary"),
        observed_at=_decode_datetime(data["observed_at"], "observed_at"),
        values=_decode_scalar_mapping(data["values"], "values"),
    )


def _decode_evidence(data: dict[str, Any]) -> Evidence:
    _require_exact_keys(
        data,
        {
            "claim",
            "confidence",
            "created_at",
            "evidence_id",
            "incident_id",
            "observation_ids",
        },
        "evidence",
    )
    confidence = data["confidence"]
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        raise CheckpointError("confidence must be a finite number")
    return Evidence(
        evidence_id=_require_string(data["evidence_id"], "evidence_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        claim=_require_string(data["claim"], "claim"),
        observation_ids=_decode_string_tuple(
            data["observation_ids"],
            "observation_ids",
        ),
        confidence=float(confidence),
        created_at=_decode_datetime(data["created_at"], "created_at"),
    )


def _decode_working_memory(data: dict[str, Any]) -> WorkingMemory:
    _require_exact_keys(
        data,
        {
            "facts",
            "incident_id",
            "open_questions",
            "revision",
            "step_budget",
            "task_id",
            "updated_at",
        },
        "working_memory",
    )
    budget_data = _require_object(data["step_budget"], "step_budget")
    _require_exact_keys(
        budget_data,
        {"action_limit", "actions_used"},
        "step_budget",
    )
    return WorkingMemory(
        task_id=_require_string(data["task_id"], "task_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        revision=_require_integer(data["revision"], "revision"),
        facts=tuple(
            _decode_memory_fact(_require_object(item, "memory_fact"))
            for item in _require_list(data["facts"], "facts")
        ),
        open_questions=tuple(
            _decode_open_question(_require_object(item, "open_question"))
            for item in _require_list(data["open_questions"], "open_questions")
        ),
        step_budget=StepBudget(
            action_limit=_require_integer(
                budget_data["action_limit"],
                "action_limit",
            ),
            actions_used=_require_integer(
                budget_data["actions_used"],
                "actions_used",
            ),
        ),
        updated_at=_decode_datetime(data["updated_at"], "updated_at"),
    )


def _decode_memory_fact(data: dict[str, Any]) -> MemoryFact:
    _require_exact_keys(
        data,
        {"fact_id", "incident_id", "observation_ids", "recorded_at", "statement"},
        "memory_fact",
    )
    return MemoryFact(
        fact_id=_require_string(data["fact_id"], "fact_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        statement=_require_string(data["statement"], "statement"),
        observation_ids=_decode_string_tuple(
            data["observation_ids"],
            "observation_ids",
        ),
        recorded_at=_decode_datetime(data["recorded_at"], "recorded_at"),
    )


def _decode_open_question(data: dict[str, Any]) -> OpenQuestion:
    _require_exact_keys(
        data,
        {"incident_id", "opened_at", "prompt", "question_id"},
        "open_question",
    )
    return OpenQuestion(
        question_id=_require_string(data["question_id"], "question_id"),
        incident_id=_require_string(data["incident_id"], "incident_id"),
        prompt=_require_string(data["prompt"], "prompt"),
        opened_at=_decode_datetime(data["opened_at"], "opened_at"),
    )


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CheckpointError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise CheckpointError(f"{name} must be an array")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    name: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise CheckpointError(f"{name} is missing fields: {', '.join(missing)}")
    if unknown:
        raise CheckpointError(f"{name} has unknown fields: {', '.join(unknown)}")


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise CheckpointError(f"{name} must be a string")
    return value


def _require_integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise CheckpointError(f"{name} must be an integer")
    return value


def _decode_datetime(value: Any, name: str) -> datetime:
    text = _require_string(value, name)
    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise CheckpointError(f"{name} must be an ISO 8601 datetime") from error


EnumType = TypeVar("EnumType", bound=Enum)


def _decode_enum(
    enum_type: type[EnumType],
    value: Any,
    name: str,
) -> EnumType:
    text = _require_string(value, name)
    try:
        return enum_type(text)
    except ValueError as error:
        raise CheckpointError(f"invalid {name}: {text!r}") from error


def _decode_string_tuple(value: Any, name: str) -> tuple[str, ...]:
    return tuple(
        _require_string(item, name)
        for item in _require_list(value, name)
    )


def _decode_scalar_mapping(value: Any, name: str) -> dict[str, ScalarValue]:
    data = _require_object(value, name)
    result: dict[str, ScalarValue] = {}
    for key, item in data.items():
        if type(item) not in (str, int, float, bool, type(None)):
            raise CheckpointError(f"{name}.{key} must be a scalar value")
        if isinstance(item, float) and not math.isfinite(item):
            raise CheckpointError(f"{name}.{key} must be finite")
        result[key] = cast(ScalarValue, item)
    return result
