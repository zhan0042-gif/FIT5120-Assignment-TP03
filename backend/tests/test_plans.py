from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.core.exceptions import PlanValidationError
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdPlan
from app.services.plans import (
    HouseholdPlanService,
    ImmediateCheckService,
    PlanCompletionService,
)


def test_valid_plan_can_be_saved_and_retrieved(complete_plan: HouseholdPlan) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    HouseholdPlanService(repository).save(household_id, complete_plan)

    assert repository.get_plan(household_id) == complete_plan


def test_partial_plan_can_be_saved_and_completion_reports_all_gaps() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    partial_plan = HouseholdPlan()

    saved = HouseholdPlanService(repository).save(household_id, partial_plan)
    completion = PlanCompletionService().evaluate(saved)

    assert saved == partial_plan
    assert completion.overall_status == "needs_information"
    assert [section.section for section in completion.sections] == [
        "household_profile",
        "transport",
        "backup_transport",
        "primary_destination",
        "backup_destination",
        "responsibilities",
    ]
    assert all(section.status == "needs_information" for section in completion.sections)
    assert completion.immediate_checks == []


def test_explicit_no_private_transport_saves_without_fake_resource() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = HouseholdPlan(has_private_transport=False)

    saved = HouseholdPlanService(repository).save(household_id, plan)
    completion = PlanCompletionService().evaluate(saved)
    statuses = {section.section: section.status for section in completion.sections}

    assert saved.has_private_transport is False
    assert saved.transports == []
    assert statuses["transport"] == "complete"
    assert statuses["backup_transport"] == "complete"
    assert completion.immediate_checks == []


def test_unanswered_transport_still_needs_information() -> None:
    completion = PlanCompletionService().evaluate(HouseholdPlan())
    statuses = {section.section: section.status for section in completion.sections}

    assert statuses["transport"] == "needs_information"
    assert statuses["backup_transport"] == "needs_information"


def test_real_primary_transport_preserves_normal_completion_behavior(
    complete_plan: HouseholdPlan,
) -> None:
    completion = PlanCompletionService().evaluate(complete_plan)
    statuses = {section.section: section.status for section in completion.sections}

    assert complete_plan.has_private_transport is True
    assert statuses["transport"] == "complete"
    assert statuses["backup_transport"] == "complete"


def test_other_arrangement_is_allowed_with_no_private_transport() -> None:
    plan = HouseholdPlan.model_validate(
        {
            "has_private_transport": False,
            "transports": [
                {
                    "transport_id": "t_other",
                    "transport_type": "other",
                    "display_name": "Community transport",
                }
            ],
        }
    )

    HouseholdPlanService.validate(plan)
    assert plan.transports[0].display_name == "Community transport"


def test_private_vehicle_cannot_contradict_explicit_no_private_transport() -> None:
    with pytest.raises(ValidationError, match="has_private_transport"):
        HouseholdPlan.model_validate(
            {
                "has_private_transport": False,
                "transports": [
                    {
                        "transport_id": "t_car",
                        "transport_type": "car",
                    }
                ],
            }
        )


def test_fake_no_transport_resource_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HouseholdPlan.model_validate(
            {
                "transports": [
                    {
                        "transport_id": "t_fake",
                        "transport_type": "none",
                        "display_name": "No private transport available",
                    }
                ]
            }
        )


def test_pet_and_livestock_animals_save_and_load_with_optional_support() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = HouseholdPlan.model_validate(
        {
            "animals": [
                {
                    "animal_id": "a_pet",
                    "category": "pet",
                    "animal_type": "dog",
                    "display_name": "Buddy",
                    "support_notes": None,
                },
                {
                    "animal_id": "a_stock",
                    "category": "livestock",
                    "animal_type": "horse",
                    "display_name": "Star",
                    "support_notes": "Needs a float",
                },
            ]
        }
    )

    saved = HouseholdPlanService(repository).save(household_id, plan)

    assert saved.animals == plan.animals
    assert saved.animals[0].category == "pet"
    assert saved.animals[0].support_notes is None
    assert saved.animals[1].category == "livestock"
    assert saved.animals[1].support_notes == "Needs a float"


def test_duplicate_animal_ids_are_rejected() -> None:
    plan = HouseholdPlan.model_validate(
        {
            "animals": [
                {"animal_id": "a_001", "category": "pet", "animal_type": "dog"},
                {
                    "animal_id": "a_001",
                    "category": "livestock",
                    "animal_type": "goat",
                },
            ]
        }
    )

    with pytest.raises(PlanValidationError, match="animal_id values must be unique"):
        HouseholdPlanService.validate(plan)


def test_optional_reference_must_be_valid_when_supplied() -> None:
    plan = HouseholdPlan(arrangements={"primary_transport_id": "missing"})

    with pytest.raises(PlanValidationError, match="primary_transport_id"):
        HouseholdPlanService.validate(plan)


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


def test_responsibility_primary_without_backup_saves(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["responsibilities"][0]["backup_member_id"] = None
    plan = HouseholdPlan.model_validate(data)

    HouseholdPlanService.validate(plan)


def test_different_responsibility_backup_person_saves(
    complete_plan: HouseholdPlan,
) -> None:
    HouseholdPlanService.validate(complete_plan)


def test_duplicate_destination_ids_are_rejected(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"]["backup_destination"]["destination_id"] = "d_001"

    with pytest.raises(PlanValidationError, match="destination_id values must be unique"):
        HouseholdPlanService.validate(HouseholdPlan.model_validate(data))


def test_complete_plan_completion(complete_plan: HouseholdPlan) -> None:
    result = PlanCompletionService().evaluate(complete_plan)

    assert result.overall_status == "complete"
    assert all(section.status == "complete" for section in result.sections)
    assert result.immediate_checks == []


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


def test_immediate_checks_require_a_primary_arrangement() -> None:
    checks = ImmediateCheckService().evaluate(HouseholdPlan())

    assert checks == []


def test_missing_backups_and_people_are_reported_deterministically(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"]["backup_transport_id"] = None
    data["arrangements"]["backup_destination"] = None
    data["responsibilities"][0]["backup_member_id"] = None

    checks = ImmediateCheckService().evaluate(HouseholdPlan.model_validate(data))

    assert [check.check for check in checks] == [
        "missing_backup_transport",
        "missing_backup_destination",
        "missing_backup_person",
    ]
    assert checks[2].message == (
        'No backup person is assigned for "Drive household".'
    )
    assert "r_001" not in checks[2].message


def test_missing_backup_person_uses_generic_message_without_task_or_ids() -> None:
    plan = HouseholdPlan.model_validate(
        {
            "members": [
                {
                    "member_id": "m_001",
                    "display_name": "Maya",
                    "is_dependant": False,
                    "mobility_support_required": False,
                }
            ],
            "responsibilities": [
                {
                    "responsibility_id": "r_secret",
                    "task_name": "   ",
                    "primary_member_id": "m_001",
                    "backup_member_id": None,
                }
            ],
        }
    )

    message = ImmediateCheckService().evaluate(plan)[0].message

    assert message == "A responsibility has no backup person assigned."
    assert "r_secret" not in message


def test_immediate_check_messages_contain_no_internal_ids(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"]["backup_transport_id"] = None
    data["arrangements"]["backup_destination"] = None
    data["responsibilities"][0]["task_name"] = "Collect children"
    data["responsibilities"][0]["backup_member_id"] = None

    checks = ImmediateCheckService().evaluate(HouseholdPlan.model_validate(data))
    messages = " ".join(check.message for check in checks)

    assert "Collect children" in messages
    assert not any(prefix in messages for prefix in ("r_", "m_", "t_", "a_"))


def test_shared_transport_saves_and_is_reported(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    data = deepcopy(complete_plan_data)
    data["arrangements"]["backup_transport_id"] = "t_001"

    saved = HouseholdPlanService(repository).save(
        household_id, HouseholdPlan.model_validate(data)
    )
    checks = ImmediateCheckService().evaluate(saved)

    assert saved.arrangements.backup_transport_id == "t_001"
    assert [check.check for check in checks] == ["shared_transport_resource"]


def test_fixing_missing_backup_transport_removes_check(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["arrangements"]["backup_transport_id"] = None
    incomplete = HouseholdPlan.model_validate(data)
    fixed = HouseholdPlan.model_validate(complete_plan_data)

    assert "missing_backup_transport" in {
        check.check for check in ImmediateCheckService().evaluate(incomplete)
    }
    assert "missing_backup_transport" not in {
        check.check for check in ImmediateCheckService().evaluate(fixed)
    }
