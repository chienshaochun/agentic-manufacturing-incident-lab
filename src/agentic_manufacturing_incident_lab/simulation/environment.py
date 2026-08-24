"""Runtime environment that turns hidden scenario truth into observations."""

from datetime import datetime, timedelta

from agentic_manufacturing_incident_lab.domain.models import (
    Observation,
    ObservationKind,
    ScalarValue,
)
from agentic_manufacturing_incident_lab.simulation.scenario import (
    ScenarioBrief,
    ScenarioDefinition,
)


class SimulatedEnvironment:
    """A deterministic runtime view over one immutable scenario definition."""

    __slots__ = ("_observation_count", "_scenario")

    def __init__(self, scenario: ScenarioDefinition) -> None:
        self._scenario = scenario
        self._observation_count = 0

    @property
    def brief(self) -> ScenarioBrief:
        """Return the limited context safe to pass into an agent."""
        return self._scenario.to_brief()

    @property
    def observation_count(self) -> int:
        """Return the number of successful measurements recorded so far."""
        return self._observation_count

    @property
    def current_time(self) -> datetime:
        """Return deterministic simulated time after the latest measurement."""
        return self._scenario.incident.reported_at + timedelta(
            seconds=30 * self._observation_count
        )

    def measure_connectivity(self, asset_id: str) -> Observation:
        """Measure whether one known synthetic asset is network reachable."""
        asset = self._scenario.asset_truth(asset_id)
        reachable = asset.network_reachable
        state = "reachable" if reachable else "unreachable"
        return self._record_observation(
            source="simulated_connectivity_sensor",
            kind=ObservationKind.CONNECTIVITY,
            summary=f"{asset.asset_id} is {state} on the simulated network.",
            values={"asset_id": asset.asset_id, "network_reachable": reachable},
        )

    def measure_telemetry(self, asset_id: str) -> Observation:
        """Measure whether one known synthetic asset is reporting telemetry."""
        asset = self._scenario.asset_truth(asset_id)
        available = asset.telemetry_available
        state = "available" if available else "unavailable"
        return self._record_observation(
            source="simulated_telemetry_sensor",
            kind=ObservationKind.METRIC,
            summary=f"Telemetry for {asset.asset_id} is {state}.",
            values={"asset_id": asset.asset_id, "telemetry_available": available},
        )

    def _record_observation(
        self,
        *,
        source: str,
        kind: ObservationKind,
        summary: str,
        values: dict[str, ScalarValue],
    ) -> Observation:
        self._observation_count += 1
        sequence = self._observation_count
        return Observation(
            observation_id=f"{self._scenario.incident.incident_id}-OBS-{sequence:03d}",
            incident_id=self._scenario.incident.incident_id,
            source=source,
            kind=kind,
            summary=summary,
            observed_at=self.current_time,
            values=values,
        )
