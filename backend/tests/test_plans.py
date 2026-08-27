from copy import deepcopy

import pytest

from app.core.exceptions import PlanValidationError
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdPlan
from app.services.plans import HouseholdPlanService, PlanCompletionService


def test_valid_plan_can_be_saved_and_retrieved(complete_plan: HouseholdPlan) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    HouseholdPlanService(repository).save(household_id, complete_plan)

    assert repository.get_plan(household_id) == complete_plan


def test_invalid_driver_member_reference_is_rejected(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["transports"][0]["driver_member_ids"] = ["missing_member"]

    with pytest.raises(PlanValidationError, match="unknown driver"):
        HouseholdPlanService.validate(HouseholdPlan.model_validate(data))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("primary_transport_id", "missing", "primary_transport_id"),
        ("backup_transport_id", "missing", "backup_transport_id"),
    ],
)
def test_invalid_transport_reference_is_rejected(
    complete_plan_data: dict, field: str, value: str, message: str
) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"][field] = value

    with pytest.raises(PlanValidationError, match=message):
        HouseholdPlanService.validate(HouseholdPlan.model_validate(data))


def test_invalid_responsibility_references_are_rejected(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["responsibilities"][0]["primary_member_id"] = "missing"

    with pytest.raises(PlanValidationError, match="unknown primary member"):
        HouseholdPlanService.validate(HouseholdPlan.model_validate(data))


def test_same_primary_and_backup_person_is_rejected(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["responsibilities"][0]["backup_member_id"] = "m_001"

    with pytest.raises(PlanValidationError, match="different backup member"):
        HouseholdPlanService.validate(HouseholdPlan.model_validate(data))


def test_complete_plan_completion(complete_plan: HouseholdPlan) -> None:
    result = PlanCompletionService().evaluate(complete_plan)

    assert result.overall_status == "complete"
    assert all(section.status == "complete" for section in result.sections)


@pytest.mark.parametrize(
    ("mutation", "missing_section"),
    [
        (lambda data: data["arrangements"].update(backup_transport_id=None), "backup_transport"),
        (lambda data: data["arrangements"].update(backup_destination=None), "backup_destination"),
        (lambda data: data.update(responsibilities=[]), "responsibilities"),
    ],
)
def test_incomplete_plan_sections(
    complete_plan_data: dict, mutation, missing_section: str
) -> None:
    mutation(complete_plan_data)
    result = PlanCompletionService().evaluate(
        HouseholdPlan.model_validate(complete_plan_data)
    )

    statuses = {section.section: section.status for section in result.sections}
    assert result.overall_status == "needs_information"
    assert statuses[missing_section] == "needs_information"

