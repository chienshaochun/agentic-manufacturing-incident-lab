"""Fair comparison between single-agent and coordinated multi-agent runs."""

from dataclasses import dataclass

from agentic_manufacturing_incident_lab.agent import (
    RuleBasedPlanner,
    SingleAgentRunner,
)
from agentic_manufacturing_incident_lab.collaboration import (
    CoordinatorAgent,
    DiagnosticAgent,
    MultiAgentRun,
    ReporterAgent,
    SafetyReviewOutcome,
    SafetyReviewerAgent,
)
from agentic_manufacturing_incident_lab.domain.models import ScalarValue
from agentic_manufacturing_incident_lab.domain.task import TaskStatus
from agentic_manufacturing_incident_lab.runtime import InvestigationRun
from agentic_manufacturing_incident_lab.simulation import (
    ScenarioDefinition,
    SimulatedEnvironment,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


ActionSignature = tuple[
    str,
    str,
    tuple[tuple[str, ScalarValue], ...],
]
ObservationSignature = tuple[
    str,
    str,
    tuple[tuple[str, ScalarValue], ...],
]
EvidenceSignature = tuple[str, float]


def _action_signatures(run: InvestigationRun) -> tuple[ActionSignature, ...]:
    """Return action meaning without run-specific IDs or timestamps."""
    return tuple(
        (
            record.action.tool_name,
            record.action.risk.value,
            tuple(sorted(record.action.parameters.items())),
        )
        for record in run.executions
    )


def _observation_signatures(
    run: InvestigationRun,
) -> tuple[ObservationSignature, ...]:
    """Return measured meaning without generated IDs or timestamps."""
    return tuple(
        (
            observation.source,
            observation.kind.value,
            tuple(sorted(observation.values.items())),
        )
        for observation in run.observations
    )


def _evidence_signatures(run: InvestigationRun) -> tuple[EvidenceSignature, ...]:
    """Return evidence conclusions without generated record metadata."""
    return tuple((item.claim, item.confidence) for item in run.evidence)


@dataclass(frozen=True, slots=True)
class AgentComparison:
    """One isolated A/B run plus derived diagnostic and governance metrics."""

    scenario_id: str
    seed: int
    single_run: InvestigationRun
    multi_run: MultiAgentRun

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        incident_id = self.single_run.incident.incident_id
        if self.multi_run.ledger.incident_id != incident_id:
            raise ValueError("comparison runs must describe the same incident")
        if (
            self.multi_run.diagnostic is not None
            and self.multi_run.diagnostic.run.incident != self.single_run.incident
        ):
            raise ValueError("comparison diagnostic inputs must be identical")

    @property
    def multi_diagnostic_run(self) -> InvestigationRun | None:
        """Return the diagnostic specialist run when that role responded."""
        if self.multi_run.diagnostic is None:
            return None
        return self.multi_run.diagnostic.run

    @property
    def diagnostic_status_match(self) -> bool:
        """Whether both diagnostic paths reached the same task status."""
        multi_diagnostic = self.multi_diagnostic_run
        return (
            multi_diagnostic is not None
            and self.single_run.final_state.status
            is multi_diagnostic.final_state.status
        )

    @property
    def action_plan_match(self) -> bool:
        """Whether both paths selected the same tools, risk, and parameters."""
        multi_diagnostic = self.multi_diagnostic_run
        return (
            multi_diagnostic is not None
            and _action_signatures(self.single_run)
            == _action_signatures(multi_diagnostic)
        )

    @property
    def observation_match(self) -> bool:
        """Whether both isolated environments returned equivalent measurements."""
        multi_diagnostic = self.multi_diagnostic_run
        return (
            multi_diagnostic is not None
            and _observation_signatures(self.single_run)
            == _observation_signatures(multi_diagnostic)
        )

    @property
    def evidence_match(self) -> bool:
        """Whether both diagnostic paths reached equivalent evidence claims."""
        multi_diagnostic = self.multi_diagnostic_run
        return (
            multi_diagnostic is not None
            and _evidence_signatures(self.single_run)
            == _evidence_signatures(multi_diagnostic)
        )

    @property
    def single_action_count(self) -> int:
        return len(self.single_run.executions)

    @property
    def multi_diagnostic_action_count(self) -> int:
        multi_diagnostic = self.multi_diagnostic_run
        return len(multi_diagnostic.executions) if multi_diagnostic else 0

    @property
    def diagnostic_action_delta(self) -> int:
        """Additional diagnostic tool calls made by the multi-agent path."""
        return self.multi_diagnostic_action_count - self.single_action_count

    @property
    def coordination_handoff_count(self) -> int:
        """Structured messages added by multi-agent governance."""
        return len(self.multi_run.ledger.handoffs)

    @property
    def safety_review_outcome(self) -> SafetyReviewOutcome | None:
        if self.multi_run.safety_review is None:
            return None
        return self.multi_run.safety_review.outcome

    @property
    def report_generated(self) -> bool:
        return self.multi_run.report is not None

    @property
    def collaboration_failure_count(self) -> int:
        return len(self.multi_run.failures)

    @property
    def single_status(self) -> TaskStatus:
        return self.single_run.final_state.status


def run_single_multi_comparison(
    scenario: ScenarioDefinition,
    *,
    action_limit: int = 32,
) -> AgentComparison:
    """Run the same scenario in two isolated environments and compare outcomes."""
    single_environment = SimulatedEnvironment(scenario)
    multi_environment = SimulatedEnvironment(scenario)
    brief = scenario.to_brief()

    single_run = SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(single_environment),
        action_limit=action_limit,
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    multi_run = CoordinatorAgent(
        diagnostic=DiagnosticAgent(
            policy=RuleBasedPlanner(),
            registry=build_diagnostic_registry(multi_environment),
            action_limit=action_limit,
        ),
        safety_reviewer=SafetyReviewerAgent(),
        reporter=ReporterAgent(),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )

    return AgentComparison(
        scenario_id=scenario.scenario_id,
        seed=scenario.seed,
        single_run=single_run,
        multi_run=multi_run,
    )
