from agentic_manufacturing_incident_lab.agent import RuleBasedPlanner, SingleAgentRunner
from agentic_manufacturing_incident_lab.domain import HypothesisStatus
from agentic_manufacturing_incident_lab.hypotheses import (
    ConnectivityHypothesisPolicy,
)
from agentic_manufacturing_incident_lab.runtime import (
    deserialize_checkpoint,
    serialize_checkpoint,
)
from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)
from agentic_manufacturing_incident_lab.tools import build_diagnostic_registry


def _run_with_hypotheses():
    environment = SimulatedEnvironment(build_station_connectivity_scenario(seed=43))
    brief = environment.brief
    return SingleAgentRunner(
        policy=RuleBasedPlanner(),
        registry=build_diagnostic_registry(environment),
        hypothesis_policy=ConnectivityHypothesisPolicy(),
    ).run(
        incident=brief.incident,
        known_asset_ids=brief.known_asset_ids,
    )


def test_runtime_persists_competing_hypotheses_with_grounding() -> None:
    run = _run_with_hypotheses()

    station = next(
        item for item in run.hypotheses
        if item.hypothesis_id.endswith("-STATION")
    )
    shared = next(
        item for item in run.hypotheses
        if item.hypothesis_id.endswith("-SHARED")
    )
    assert station.status is HypothesisStatus.SUPPORTED
    assert station.supporting_observation_ids == tuple(
        observation.observation_id for observation in run.observations
    )
    assert shared.status is HypothesisStatus.REJECTED


def test_checkpoint_round_trip_preserves_hypotheses() -> None:
    run = _run_with_hypotheses()

    restored = deserialize_checkpoint(serialize_checkpoint(run))

    assert restored == run
    assert restored.hypotheses == run.hypotheses
