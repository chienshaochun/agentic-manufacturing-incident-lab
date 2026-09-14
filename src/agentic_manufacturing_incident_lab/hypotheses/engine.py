"""Deterministic hypothesis scoring over collected observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol, runtime_checkable

from agentic_manufacturing_incident_lab.domain import (
    Hypothesis,
    HypothesisEffect,
    HypothesisSignal,
    HypothesisStatus,
    Incident,
    Observation,
)
from agentic_manufacturing_incident_lab.domain._validation import (
    require_text,
    require_timezone,
)


@dataclass(frozen=True, slots=True)
class HypothesisDefinition:
    """Stable identity, statement, and prior for one candidate cause."""

    hypothesis_id: str
    statement: str
    prior_confidence: float = 0.25

    def __post_init__(self) -> None:
        require_text(self.hypothesis_id, "hypothesis_id")
        require_text(self.statement, "statement")
        if (
            isinstance(self.prior_confidence, bool)
            or not 0.0 <= self.prior_confidence <= 1.0
        ):
            raise ValueError("prior_confidence must be between 0.0 and 1.0")


@runtime_checkable
class HypothesisPolicy(Protocol):
    """Interchangeable policy that projects observations into hypotheses."""

    name: str

    def evaluate(
        self,
        incident: Incident,
        observations: tuple[Observation, ...],
        *,
        evaluated_at: datetime,
    ) -> tuple[Hypothesis, ...]:
        """Return the current candidate explanations for an investigation."""


def evaluate_hypotheses(
    *,
    incident: Incident,
    definitions: tuple[HypothesisDefinition, ...],
    signals: tuple[HypothesisSignal, ...],
    evaluated_at: datetime,
    support_threshold: float = 0.90,
    rejection_threshold: float = 0.65,
    conflict_threshold: float = 0.65,
    observation_quality: Mapping[str, float] | None = None,
) -> tuple[Hypothesis, ...]:
    """Aggregate auditable signals into immutable hypothesis snapshots."""
    require_timezone(evaluated_at, "evaluated_at")
    if not 0.0 < support_threshold <= 1.0:
        raise ValueError("support_threshold must be in (0.0, 1.0]")
    if not 0.0 < rejection_threshold <= 1.0:
        raise ValueError("rejection_threshold must be in (0.0, 1.0]")
    if not 0.0 < conflict_threshold <= 1.0:
        raise ValueError("conflict_threshold must be in (0.0, 1.0]")
    quality_by_id = dict(observation_quality or {})
    for observation_id, quality in quality_by_id.items():
        require_text(observation_id, "observation_quality observation_id")
        if (
            isinstance(quality, bool)
            or not isinstance(quality, (int, float))
            or not 0.0 <= quality <= 1.0
        ):
            raise ValueError("observation quality must be between 0.0 and 1.0")

    definition_ids = tuple(item.hypothesis_id for item in definitions)
    if not definitions:
        raise ValueError("definitions must not be empty")
    if len(set(definition_ids)) != len(definition_ids):
        raise ValueError("definitions must have unique hypothesis_id values")
    if any(signal.hypothesis_id not in set(definition_ids) for signal in signals):
        raise ValueError("signals must reference a known hypothesis")

    pair_effects: dict[tuple[str, str], HypothesisEffect] = {}
    for signal in signals:
        pair = (signal.hypothesis_id, signal.observation_id)
        previous = pair_effects.setdefault(pair, signal.effect)
        if previous is not signal.effect:
            raise ValueError("one observation cannot produce conflicting signals")

    snapshots = []
    for definition in definitions:
        related = tuple(
            (signal, signal.weight * quality_by_id.get(signal.observation_id, 1.0))
            for signal in signals
            if signal.hypothesis_id == definition.hypothesis_id
            and signal.weight * quality_by_id.get(signal.observation_id, 1.0) > 0.0
        )
        support_signals = tuple(
            (signal, effective_weight) for signal, effective_weight in related
            if signal.effect is HypothesisEffect.SUPPORTS
        )
        contradiction_signals = tuple(
            (signal, effective_weight) for signal, effective_weight in related
            if signal.effect is HypothesisEffect.CONTRADICTS
        )
        support_score = min(1.0, sum(weight for _, weight in support_signals))
        contradiction_score = min(
            1.0,
            sum(weight for _, weight in contradiction_signals),
        )

        if not related:
            status = HypothesisStatus.OPEN
        elif (
            support_score >= conflict_threshold
            and contradiction_score >= conflict_threshold
        ):
            status = HypothesisStatus.CONFLICTED
        elif contradiction_score >= rejection_threshold:
            status = HypothesisStatus.REJECTED
        elif support_score >= support_threshold and contradiction_score < 0.25:
            status = HypothesisStatus.SUPPORTED
        else:
            status = HypothesisStatus.INCONCLUSIVE

        confidence = max(
            0.0,
            min(
                0.99,
                definition.prior_confidence
                + 0.70 * support_score
                - 0.70 * contradiction_score,
            ),
        )
        snapshots.append(
            Hypothesis(
                hypothesis_id=definition.hypothesis_id,
                incident_id=incident.incident_id,
                statement=definition.statement,
                status=status,
                confidence=confidence,
                supporting_observation_ids=tuple(
                    dict.fromkeys(item.observation_id for item, _ in support_signals)
                ),
                contradicting_observation_ids=tuple(
                    dict.fromkeys(
                        item.observation_id for item, _ in contradiction_signals
                    )
                ),
                rationale=(
                    f"support_score={support_score:.2f}; "
                    f"contradiction_score={contradiction_score:.2f}; "
                    f"quality_adjusted_signals={len(related)}"
                ),
                updated_at=evaluated_at,
            )
        )
    return tuple(snapshots)


class ConnectivityHypothesisPolicy:
    """Maintain competing station, shared-network, and telemetry hypotheses."""

    name = "station_connectivity_hypotheses_v1"

    def evaluate(
        self,
        incident: Incident,
        observations: tuple[Observation, ...],
        *,
        evaluated_at: datetime,
    ) -> tuple[Hypothesis, ...]:
        definitions = self._definitions(incident)
        signals = tuple(
            signal
            for observation in observations
            for signal in self._signals(incident, observation, definitions)
        )
        return evaluate_hypotheses(
            incident=incident,
            definitions=definitions,
            signals=signals,
            evaluated_at=evaluated_at,
            observation_quality={
                item.observation_id: item.quality_factor for item in observations
            },
        )

    @staticmethod
    def _definitions(incident: Incident) -> tuple[HypothesisDefinition, ...]:
        prefix = f"HYP-{incident.incident_id}"
        asset_id = incident.asset_id
        return (
            HypothesisDefinition(
                hypothesis_id=f"{prefix}-STATION",
                statement=f"The connectivity fault is isolated to {asset_id}.",
            ),
            HypothesisDefinition(
                hypothesis_id=f"{prefix}-SHARED",
                statement="Shared network infrastructure is unavailable.",
            ),
            HypothesisDefinition(
                hypothesis_id=f"{prefix}-TELEMETRY",
                statement=f"The telemetry path for {asset_id} is unavailable.",
            ),
        )

    @classmethod
    def _signals(
        cls,
        incident: Incident,
        observation: Observation,
        definitions: tuple[HypothesisDefinition, ...],
    ) -> tuple[HypothesisSignal, ...]:
        hypothesis_ids = {
            "station": definitions[0].hypothesis_id,
            "shared": definitions[1].hypothesis_id,
            "telemetry": definitions[2].hypothesis_id,
        }
        asset_id = observation.values.get("asset_id")
        signals: list[HypothesisSignal] = []
        reachable = observation.values.get("network_reachable")
        if isinstance(reachable, bool):
            affected = asset_id == incident.asset_id
            if affected and not reachable:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, True, 0.35,
                                    "The affected station is unreachable."),
                        cls._signal(hypothesis_ids["shared"], observation, True, 0.50,
                                    "An unreachable affected station may reflect shared infrastructure."),
                        cls._signal(hypothesis_ids["telemetry"], observation, False, 0.35,
                                    "Network loss prevents isolating a telemetry-only fault."),
                    )
                )
            elif affected and reachable:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, False, 1.00,
                                    "The affected station is reachable."),
                        cls._signal(hypothesis_ids["shared"], observation, False, 1.00,
                                    "The affected station is reachable through shared infrastructure."),
                        cls._signal(hypothesis_ids["telemetry"], observation, True, 0.35,
                                    "Healthy connectivity keeps a telemetry-path fault plausible."),
                    )
                )
            elif not affected and not reachable:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, False, 0.75,
                                    "A peer station is also unreachable."),
                        cls._signal(hypothesis_ids["shared"], observation, True, 0.50,
                                    "A peer station is also unreachable."),
                    )
                )
            elif not affected and reachable:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, True, 0.40,
                                    "A peer station remains reachable."),
                        cls._signal(hypothesis_ids["shared"], observation, False, 0.75,
                                    "A reachable peer contradicts shared network loss."),
                    )
                )

        telemetry_available = observation.values.get("telemetry_available")
        if asset_id == incident.asset_id and isinstance(telemetry_available, bool):
            if telemetry_available:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, False, 0.35,
                                    "The affected station still publishes telemetry."),
                        cls._signal(hypothesis_ids["telemetry"], observation, False, 1.00,
                                    "Telemetry is available."),
                    )
                )
            else:
                signals.extend(
                    (
                        cls._signal(hypothesis_ids["station"], observation, True, 0.25,
                                    "The affected station has no telemetry."),
                        cls._signal(hypothesis_ids["telemetry"], observation, True, 0.65,
                                    "The affected station has no telemetry."),
                    )
                )
        return tuple(signals)

    @staticmethod
    def _signal(
        hypothesis_id: str,
        observation: Observation,
        supports: bool,
        weight: float,
        rationale: str,
    ) -> HypothesisSignal:
        return HypothesisSignal(
            hypothesis_id=hypothesis_id,
            observation_id=observation.observation_id,
            effect=(
                HypothesisEffect.SUPPORTS
                if supports
                else HypothesisEffect.CONTRADICTS
            ),
            weight=weight,
            rationale=rationale,
        )


class ManufacturingSignalHypothesisPolicy:
    """Evaluate competing causes of a flatlined manufacturing signal."""

    name = "manufacturing_signal_hypotheses_v1"

    def evaluate(
        self,
        incident: Incident,
        observations: tuple[Observation, ...],
        *,
        evaluated_at: datetime,
    ) -> tuple[Hypothesis, ...]:
        definitions = self._definitions(incident)
        signals = tuple(
            signal
            for observation in observations
            for signal in self._signals(observation, definitions)
        )
        return evaluate_hypotheses(
            incident=incident,
            definitions=definitions,
            signals=signals,
            evaluated_at=evaluated_at,
            observation_quality={
                item.observation_id: item.quality_factor for item in observations
            },
        )

    @staticmethod
    def _definitions(incident: Incident) -> tuple[HypothesisDefinition, ...]:
        prefix = f"HYP-{incident.incident_id}"
        asset = incident.asset_id
        return (
            HypothesisDefinition(f"{prefix}-NETWORK", f"The network path for {asset} is unavailable."),
            HypothesisDefinition(f"{prefix}-TELEMETRY", f"The telemetry service for {asset} is unavailable."),
            HypothesisDefinition(f"{prefix}-CONFIG", f"Configuration drift affects {asset}."),
            HypothesisDefinition(f"{prefix}-MAINTENANCE", f"Planned maintenance explains the signal gap on {asset}."),
            HypothesisDefinition(f"{prefix}-SENSOR", f"Sensor data on {asset} is stale."),
        )

    @classmethod
    def _signals(
        cls,
        observation: Observation,
        definitions: tuple[HypothesisDefinition, ...],
    ) -> tuple[HypothesisSignal, ...]:
        ids = {
            suffix: next(item.hypothesis_id for item in definitions if item.hypothesis_id.endswith(suffix))
            for suffix in ("-NETWORK", "-TELEMETRY", "-CONFIG", "-MAINTENANCE", "-SENSOR")
        }
        signals: list[HypothesisSignal] = []

        codes = {
            code for code in str(observation.values.get("alarm_codes_csv", "")).split(",")
            if code
        }
        alarm_map = {
            "SENSOR_STALE": ("-SENSOR", "Alarm history contains SENSOR_STALE."),
            "CONFIG_VERSION_MISMATCH": ("-CONFIG", "Alarm history contains CONFIG_VERSION_MISMATCH."),
            "TELEMETRY_MISSING": ("-TELEMETRY", "Alarm history contains TELEMETRY_MISSING."),
        }
        for code, (suffix, rationale) in alarm_map.items():
            if code in codes:
                signals.append(cls._signal(ids[suffix], observation, True, 0.30, rationale))

        boolean_rules = (
            ("network_reachable", "-NETWORK", False),
            ("telemetry_available", "-TELEMETRY", False),
            ("configuration_matches", "-CONFIG", False),
            ("maintenance_active", "-MAINTENANCE", True),
            ("sensor_fresh", "-SENSOR", False),
        )
        for key, suffix, failure_value in boolean_rules:
            value = observation.values.get(key)
            if not isinstance(value, bool):
                continue
            supports = value is failure_value
            weight = 0.70 if supports and suffix in {"-SENSOR", "-CONFIG", "-TELEMETRY"} else 1.00
            signals.append(
                cls._signal(
                    ids[suffix],
                    observation,
                    supports,
                    weight,
                    f"Observed {key}={value}.",
                )
            )
        return tuple(signals)

    @staticmethod
    def _signal(
        hypothesis_id: str,
        observation: Observation,
        supports: bool,
        weight: float,
        rationale: str,
    ) -> HypothesisSignal:
        return HypothesisSignal(
            hypothesis_id=hypothesis_id,
            observation_id=observation.observation_id,
            effect=HypothesisEffect.SUPPORTS if supports else HypothesisEffect.CONTRADICTS,
            weight=weight,
            rationale=rationale,
        )
