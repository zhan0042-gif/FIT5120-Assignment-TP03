from copy import deepcopy

import pytest

from app.core.exceptions import ScenarioNotApplicable, UnsupportedScenario
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdPlan
from app.services.scenarios import BasicScenarioService


def run(data: dict, scenario_id: str):
    return BasicScenarioService().run(HouseholdPlan.model_validate(data), scenario_id)


def test_vehicle_without_backup_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_transport_id"] = None
    result = run(complete_plan_data, "vehicle_unavailable")

    assert result.overall_status == "needs_attention"
    assert [check.status for check in result.checks] == ["fail", "not_checked"]
    assert result.first_problem is not None
    assert result.result_reason == (
        "The primary transport is unavailable and no independent backup transport is recorded."
    )


def test_vehicle_with_same_primary_and_backup_fails(
    complete_plan_data: dict,
) -> None:
    complete_plan_data["arrangements"]["backup_transport_id"] = "t_001"

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
    result = run(complete_plan_data, "vehicle_unavailable")

    assert result.overall_status == "pass"
    assert result.first_problem is None
    assert "independent backup transport" in result.result_reason


@pytest.mark.parametrize("backup_member_id", [None, "m_001", "unknown"])
def test_person_without_different_backup_fails(
    complete_plan_data: dict, backup_member_id: str | None
) -> None:
    complete_plan_data["responsibilities"][0]["backup_member_id"] = backup_member_id

    assert run(complete_plan_data, "person_unavailable").overall_status == "needs_attention"


def test_person_with_different_backup_passes(complete_plan_data: dict) -> None:
    result = run(complete_plan_data, "person_unavailable")

    assert result.overall_status == "pass"
    assert result.result_reason


def test_person_scenario_uses_latest_repository_plan(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    without_backup = deepcopy(complete_plan_data)
    without_backup["responsibilities"][0]["backup_member_id"] = None
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(without_backup)
    )
    service = BasicScenarioService(repository)

    first = service.run_for_household(household_id, "person_unavailable")
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(complete_plan_data)
    )
    second = service.run_for_household(household_id, "person_unavailable")

    assert first.overall_status == "needs_attention"
    assert second.overall_status == "pass"


def test_destination_without_backup_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_destination"] = None

    assert run(complete_plan_data, "destination_unavailable").overall_status == "needs_attention"


def test_irrelevant_destination_scenario_is_rejected() -> None:
    with pytest.raises(ScenarioNotApplicable, match="No primary destination"):
        BasicScenarioService().run(HouseholdPlan(), "destination_unavailable")


def test_destination_with_same_address_fails(complete_plan_data: dict) -> None:
    complete_plan_data["arrangements"]["backup_destination"]["address"] = "1 example road"

    assert run(complete_plan_data, "destination_unavailable").overall_status == "needs_attention"


def test_destination_with_valid_backup_passes(complete_plan_data: dict) -> None:
    result = run(complete_plan_data, "destination_unavailable")

    assert result.overall_status == "pass"
    assert result.result_reason == "An independent backup destination is recorded."


def test_unknown_scenario_is_rejected(complete_plan: HouseholdPlan) -> None:
    with pytest.raises(UnsupportedScenario):
        BasicScenarioService().run(complete_plan, "unknown")


def test_scenario_library_is_exact(complete_plan: HouseholdPlan) -> None:
    scenarios = BasicScenarioService().list_scenarios(complete_plan)

    assert [scenario.scenario_id for scenario in scenarios] == [
        "vehicle_unavailable",
        "person_unavailable",
        "destination_unavailable",
    ]
    assert all(scenario.enabled for scenario in scenarios)
    assert all(scenario.disabled_reason is None for scenario in scenarios)


def test_empty_plan_disables_all_scenarios_with_reasons() -> None:
    scenarios = BasicScenarioService().list_scenarios(HouseholdPlan())

    assert [scenario.enabled for scenario in scenarios] == [False, False, False]
    assert [scenario.disabled_reason for scenario in scenarios] == [
        "No primary transport is currently recorded.",
        "No primary responsible person is currently recorded.",
        "No primary destination is currently recorded.",
    ]


def test_explicit_no_private_transport_does_not_enable_vehicle_scenario() -> None:
    plan = HouseholdPlan(has_private_transport=False)

    vehicle = BasicScenarioService().list_scenarios(plan)[0]

    assert vehicle.scenario_id == "vehicle_unavailable"
    assert vehicle.enabled is False
    with pytest.raises(ScenarioNotApplicable):
        BasicScenarioService().run(plan, "vehicle_unavailable")


@pytest.mark.parametrize(
    ("scenario_id", "mutation"),
    [
        (
            "vehicle_unavailable",
            lambda data: data["arrangements"].update(primary_transport_id=None),
        ),
        (
            "person_unavailable",
            lambda data: data.update(responsibilities=[]),
        ),
        (
            "destination_unavailable",
            lambda data: data["arrangements"].update(primary_destination=None),
        ),
    ],
)
def test_each_scenario_relevance_uses_its_primary_arrangement(
    complete_plan_data: dict, scenario_id: str, mutation
) -> None:
    mutation(complete_plan_data)

    scenarios = BasicScenarioService().list_scenarios(
        HouseholdPlan.model_validate(complete_plan_data)
    )
    scenario = next(item for item in scenarios if item.scenario_id == scenario_id)

    assert scenario.enabled is False
    assert scenario.disabled_reason is not None


def test_completed_results_are_distinct_and_persisted(
    complete_plan: HouseholdPlan,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(household_id, complete_plan)
    service = BasicScenarioService(repository)

    first = service.run_for_household(household_id, "vehicle_unavailable")
    second = service.run_for_household(household_id, "vehicle_unavailable")
    stored = repository.get_test_results(household_id)

    assert first.test_run_id.startswith("test_")
    assert first.test_run_id != second.test_run_id
    assert first.tested_at.tzinfo is not None
    assert [result.test_run_id for result in stored] == [
        first.test_run_id,
        second.test_run_id,
    ]
    assert stored[0].scenario_id == "vehicle_unavailable"
    assert stored[0].checks == first.checks
    assert repository.get_test_result(household_id, first.test_run_id) == first
