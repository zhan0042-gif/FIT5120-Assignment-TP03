from copy import deepcopy

import pytest

from app.core.exceptions import UnsupportedScenario
from app.schemas.households import HouseholdPlan
from app.services.scenarios import BasicScenarioService


def run(data: dict, scenario_id: str):
    return BasicScenarioService().run(HouseholdPlan.model_validate(data), scenario_id)


def test_vehicle_without_backup_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_transport_id"] = None
    result = run(complete_plan_data, "vehicle_unavailable")

    assert result.overall_status == "needs_attention"
    assert [check.status for check in result.checks] == ["fail", "not_checked"]


def test_vehicle_with_backup_but_no_driver_fails(complete_plan_data: dict) -> None:
    complete_plan_data["transports"][1]["driver_member_ids"] = []
    result = run(complete_plan_data, "vehicle_unavailable")

    assert result.checks[1].status == "fail"


def test_vehicle_with_unknown_backup_driver_fails(complete_plan_data: dict) -> None:
    complete_plan_data["transports"][1]["driver_member_ids"] = ["unknown"]

    assert run(complete_plan_data, "vehicle_unavailable").checks[1].status == "fail"


def test_vehicle_with_valid_backup_passes(complete_plan_data: dict) -> None:
    assert run(complete_plan_data, "vehicle_unavailable").overall_status == "pass"


@pytest.mark.parametrize("backup_member_id", [None, "m_001", "unknown"])
def test_person_without_different_backup_fails(
    complete_plan_data: dict, backup_member_id: str | None
) -> None:
    complete_plan_data["responsibilities"][0]["backup_member_id"] = backup_member_id

    assert run(complete_plan_data, "person_unavailable").overall_status == "needs_attention"


def test_person_with_different_backup_passes(complete_plan_data: dict) -> None:
    assert run(complete_plan_data, "person_unavailable").overall_status == "pass"


def test_destination_without_backup_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_destination"] = None

    assert run(complete_plan_data, "destination_unavailable").overall_status == "needs_attention"


def test_destination_scenario_handles_partial_plan() -> None:
    result = BasicScenarioService().run(HouseholdPlan(), "destination_unavailable")

    assert result.overall_status == "needs_attention"
    assert result.checks[0].check == "backup_destination"


def test_destination_with_same_address_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_destination"]["address"] = "1 example road"

    assert run(complete_plan_data, "destination_unavailable").overall_status == "needs_attention"


def test_destination_with_valid_backup_passes(complete_plan_data: dict) -> None:
    assert run(complete_plan_data, "destination_unavailable").overall_status == "pass"


def test_unknown_scenario_is_rejected(complete_plan: HouseholdPlan) -> None:
    with pytest.raises(UnsupportedScenario):
        BasicScenarioService().run(complete_plan, "unknown")


def test_scenario_library_is_exact() -> None:
    scenarios = BasicScenarioService().list_scenarios()

    assert [scenario.scenario_id for scenario in scenarios] == [
        "vehicle_unavailable",
        "person_unavailable",
        "destination_unavailable",
    ]
