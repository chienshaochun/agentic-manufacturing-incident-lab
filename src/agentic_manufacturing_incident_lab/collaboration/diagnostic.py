"""Read-only diagnostic specialist used by the multi-agent workflow."""

from datetime import timedelta

from agentic_manufacturing_incident_lab.agent import (
    PlanningPolicy,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.collaboration.contracts import (
    AgentHandoff,
    AgentRole,
    HandoffKind,
)
from agentic_manufacturing_incident_lab.collaboration.products import (
    DiagnosticWorkProduct,
)
from agentic_manufacturing_incident_lab.domain.models import (
    ActionRisk,
    Incident,
)
from agentic_manufacturing_incident_lab.runtime import RetryPolicy
from agentic_manufacturing_incident_lab.tools import ToolRegistry


class DiagnosticAgent:
    """Execute a bounded investigation using read-only diagnostic tools."""

    __slots__ = ("_runner",)

    def __init__(
        self,
        *,
        policy: PlanningPolicy,
        registry: ToolRegistry,
        action_limit: int = 32,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if any(spec.risk is not ActionRisk.READ_ONLY for spec in registry.specs):
            raise ValueError("DiagnosticAgent may only receive read-only tools")
        self._runner = SingleAgentRunner(
            policy=policy,
            registry=registry,
            action_limit=action_limit,
            retry_policy=retry_policy,
        )

    def handle(
        self,
        request: AgentHandoff,
        *,
        incident: Incident,
        known_asset_ids: tuple[str, ...],
    ) -> DiagnosticWorkProduct:
        """Run one investigation request and return referenced diagnostic output."""
        if request.kind is not HandoffKind.INVESTIGATION_REQUEST:
            raise ValueError("DiagnosticAgent requires investigation_request")
        if request.recipient is not AgentRole.DIAGNOSTIC:
            raise ValueError("investigation request must target DiagnosticAgent")
        if request.incident_id != incident.incident_id:
            raise ValueError("investigation request must match the incident")

        run = self._runner.run(
            incident=incident,
            known_asset_ids=known_asset_ids,
        )
        handoff = AgentHandoff(
            handoff_id=f"HND-{incident.incident_id}-DIAGNOSTIC-RESULT",
            incident_id=incident.incident_id,
            kind=HandoffKind.DIAGNOSTIC_RESULT,
            sender=AgentRole.DIAGNOSTIC,
            recipient=AgentRole.COORDINATOR,
            purpose=(
                f"Diagnostic investigation ended with {run.final_state.status.value}: "
                f"{run.final_state.reason}"
            ),
            created_at=run.final_state.updated_at + timedelta(seconds=1),
            observation_ids=tuple(
                observation.observation_id for observation in run.observations
            ),
            action_ids=tuple(
                record.action.action_id for record in run.executions
            ),
            in_reply_to=request.handoff_id,
        )
        return DiagnosticWorkProduct(run=run, handoff=handoff)
