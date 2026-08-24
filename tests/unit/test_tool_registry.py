from datetime import UTC, datetime
from typing import Mapping

import pytest

from agentic_manufacturing_incident_lab.domain.models import Action, ActionRisk, ScalarValue
from agentic_manufacturing_incident_lab.tools import (
    DuplicateToolError,
    ToolParameter,
    ToolParameterError,
    ToolParameterType,
    ToolRegistry,
    ToolResponse,
    ToolRiskMismatchError,
    ToolSpec,
    UnknownToolError,
)


class RecordingTool:
    def __init__(self, spec: ToolSpec) -> None:
        self.spec = spec
        self.calls: list[dict[str, ScalarValue]] = []

    def invoke(self, parameters: Mapping[str, ScalarValue]) -> ToolResponse:
        self.calls.append(dict(parameters))
        return ToolResponse(summary=f"Measured {parameters['asset_id']}.")


def make_spec(
    name: str = "check_connectivity",
    risk: ActionRisk = ActionRisk.READ_ONLY,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Check whether a synthetic asset is reachable.",
        risk=risk,
        parameters=(
            ToolParameter(
                name="asset_id",
                description="Synthetic asset identifier.",
                value_type=ToolParameterType.STRING,
            ),
            ToolParameter(
                name="attempts",
                description="Number of simulated attempts.",
                value_type=ToolParameterType.INTEGER,
                required=False,
            ),
        ),
    )


def make_action(
    *,
    tool_name: str = "check_connectivity",
    risk: ActionRisk = ActionRisk.READ_ONLY,
    parameters: Mapping[str, ScalarValue] | None = None,
) -> Action:
    return Action(
        action_id="ACT-001",
        incident_id="INC-001",
        tool_name=tool_name,
        rationale="Check the affected station.",
        risk=risk,
        requested_at=datetime(2026, 8, 24, 9, 1, tzinfo=UTC),
        parameters={"asset_id": "ST-02"} if parameters is None else parameters,
    )


def test_registry_executes_registered_tool_after_validation() -> None:
    tool = RecordingTool(make_spec())
    registry = ToolRegistry([tool])

    response = registry.execute(
        make_action(parameters={"asset_id": "ST-02", "attempts": 3})
    )

    assert response.summary == "Measured ST-02."
    assert tool.calls == [{"asset_id": "ST-02", "attempts": 3}]


def test_registry_exposes_sorted_specs_without_handlers() -> None:
    telemetry = RecordingTool(make_spec(name="read_telemetry"))
    connectivity = RecordingTool(make_spec(name="check_connectivity"))
    registry = ToolRegistry([telemetry, connectivity])

    assert [spec.name for spec in registry.specs] == [
        "check_connectivity",
        "read_telemetry",
    ]
    assert all(not hasattr(spec, "invoke") for spec in registry.specs)


def test_registry_rejects_duplicate_tool_name() -> None:
    registry = ToolRegistry([RecordingTool(make_spec())])

    with pytest.raises(DuplicateToolError, match="already registered"):
        registry.register(RecordingTool(make_spec()))


def test_registry_rejects_unknown_tool_without_invoking_handler() -> None:
    tool = RecordingTool(make_spec())
    registry = ToolRegistry([tool])

    with pytest.raises(UnknownToolError, match="not registered"):
        registry.execute(make_action(tool_name="run_shell"))

    assert tool.calls == []


def test_registry_rejects_missing_required_parameter() -> None:
    tool = RecordingTool(make_spec())
    registry = ToolRegistry([tool])

    with pytest.raises(ToolParameterError, match="missing.*asset_id"):
        registry.execute(make_action(parameters={}))

    assert tool.calls == []


def test_registry_rejects_unknown_parameter() -> None:
    tool = RecordingTool(make_spec())
    registry = ToolRegistry([tool])

    with pytest.raises(ToolParameterError, match="unknown.*command"):
        registry.execute(
            make_action(parameters={"asset_id": "ST-02", "command": "shutdown"})
        )

    assert tool.calls == []


@pytest.mark.parametrize(
    ("parameters", "expected_type"),
    [
        ({"asset_id": 2}, "string"),
        ({"asset_id": "ST-02", "attempts": True}, "integer"),
        ({"asset_id": "ST-02", "attempts": 1.5}, "integer"),
    ],
)
def test_registry_rejects_wrong_parameter_type(
    parameters: Mapping[str, ScalarValue],
    expected_type: str,
) -> None:
    tool = RecordingTool(make_spec())
    registry = ToolRegistry([tool])

    with pytest.raises(ToolParameterError, match=f"must be {expected_type}"):
        registry.execute(make_action(parameters=parameters))

    assert tool.calls == []


def test_registry_rejects_action_risk_mismatch() -> None:
    tool = RecordingTool(make_spec(risk=ActionRisk.HIGH_IMPACT))
    registry = ToolRegistry([tool])

    with pytest.raises(ToolRiskMismatchError, match="does not match"):
        registry.execute(make_action(risk=ActionRisk.READ_ONLY))

    assert tool.calls == []


def test_tool_spec_rejects_duplicate_parameter_names() -> None:
    duplicate = ToolParameter(
        name="asset_id",
        description="Synthetic asset identifier.",
        value_type=ToolParameterType.STRING,
    )

    with pytest.raises(ValueError, match="unique names"):
        ToolSpec(
            name="check_connectivity",
            description="Check whether an asset is reachable.",
            risk=ActionRisk.READ_ONLY,
            parameters=(duplicate, duplicate),
        )


@pytest.mark.parametrize("name", ["CheckConnectivity", "check-connectivity", "1st_tool"])
def test_tool_spec_requires_lower_snake_case_name(name: str) -> None:
    with pytest.raises(ValueError, match="lower_snake_case"):
        make_spec(name=name)
