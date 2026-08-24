"""Take deterministic measurements from the Phase 2 simulated environment."""

from agentic_manufacturing_incident_lab.simulation import (
    SimulatedEnvironment,
    build_station_connectivity_scenario,
)


def main() -> None:
    """Compare measurements from an affected station and a healthy peer."""
    scenario = build_station_connectivity_scenario(seed=43)
    environment = SimulatedEnvironment(scenario)

    affected = environment.measure_connectivity("ST-02")
    reference = environment.measure_connectivity("ST-01")
    telemetry = environment.measure_telemetry("ST-02")

    print("Phase 2 simulated measurements")
    for observation in (affected, reference, telemetry):
        print(
            f"{observation.observation_id} | "
            f"{observation.observed_at.isoformat()} | "
            f"{observation.summary}"
        )
    print(f"Recorded observations: {environment.observation_count}")


if __name__ == "__main__":
    main()
