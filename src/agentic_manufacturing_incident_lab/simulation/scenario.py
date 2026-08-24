"""Scenario records that separate agent-visible context from evaluator truth."""

from dataclasses import dataclass
from enum import StrEnum

from agentic_manufacturing_incident_lab.domain._validation import require_text
from agentic_manufacturing_incident_lab.domain.models import Incident


class AssetRole(StrEnum):
    """Role played by a synthetic asset in a manufacturing scenario."""

    STATION = "station"
    TELEMETRY_GATEWAY = "telemetry_gateway"


@dataclass(frozen=True, slots=True)
class AssetTruth:
    """Hidden state of one synthetic asset, available to tools and evaluators."""

    asset_id: str
    role: AssetRole
    network_reachable: bool
    telemetry_available: bool
    configuration_version: str
    alarm_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.asset_id, "asset_id")
        require_text(self.configuration_version, "configuration_version")
        alarm_codes = tuple(self.alarm_codes)
        for alarm_code in alarm_codes:
            require_text(alarm_code, "alarm_code")
        if len(set(alarm_codes)) != len(alarm_codes):
            raise ValueError("alarm_codes must not contain duplicates")
        object.__setattr__(self, "alarm_codes", alarm_codes)


@dataclass(frozen=True, slots=True)
class ScenarioBrief:
    """The limited scenario context that may be given to an agent."""

    scenario_id: str
    incident: Incident
    known_asset_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.scenario_id, "scenario_id")
        known_asset_ids = tuple(self.known_asset_ids)
        if not known_asset_ids:
            raise ValueError("known_asset_ids must contain at least one asset")
        for asset_id in known_asset_ids:
            require_text(asset_id, "asset_id")
        if len(set(known_asset_ids)) != len(known_asset_ids):
            raise ValueError("known_asset_ids must not contain duplicates")
        object.__setattr__(self, "known_asset_ids", known_asset_ids)


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """Complete synthetic case including the answer key hidden from the agent."""

    scenario_id: str
    seed: int
    title: str
    incident: Incident
    assets: tuple[AssetTruth, ...]
    faulted_asset_id: str
    root_cause_code: str

    def __post_init__(self) -> None:
        for field_name in ("scenario_id", "title", "faulted_asset_id", "root_cause_code"):
            require_text(getattr(self, field_name), field_name)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")

        assets = tuple(self.assets)
        if not assets:
            raise ValueError("assets must contain at least one asset")
        asset_ids = tuple(asset.asset_id for asset in assets)
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("assets must have unique asset_id values")
        if self.incident.asset_id not in asset_ids:
            raise ValueError("incident asset_id must exist in assets")
        if self.faulted_asset_id not in asset_ids:
            raise ValueError("faulted_asset_id must exist in assets")
        object.__setattr__(self, "assets", assets)

    def to_brief(self) -> ScenarioBrief:
        """Return an agent-visible view with no root cause or asset truth fields."""
        return ScenarioBrief(
            scenario_id=self.scenario_id,
            incident=self.incident,
            known_asset_ids=tuple(asset.asset_id for asset in self.assets),
        )

    def asset_truth(self, asset_id: str) -> AssetTruth:
        """Return hidden state for a simulator tool or evaluator."""
        require_text(asset_id, "asset_id")
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        raise KeyError(f"unknown asset_id: {asset_id}")
