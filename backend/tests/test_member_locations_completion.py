from copy import deepcopy

from app.schemas.households import HouseholdPlan
from app.services.plans import PlanCompletionService


def _section(completion, name):
    return next(item for item in completion.sections if item.section == name)


def test_member_locations_needs_information_when_absent(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    for member in data["members"]:
        member.pop("usual_location", None)

    completion = PlanCompletionService().evaluate(HouseholdPlan.model_validate(data))

    assert len(completion.sections) == 7
    assert _section(completion, "member_locations").status == "needs_information"
    assert completion.overall_status == "needs_information"


def test_member_locations_complete_when_every_member_has_one(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    for member in data["members"]:
        member["usual_location"] = {"kind": "home"}

    completion = PlanCompletionService().evaluate(HouseholdPlan.model_validate(data))

    assert _section(completion, "member_locations").status == "complete"


def test_one_member_missing_a_location_blocks_the_section(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    data["members"][1].pop("usual_location", None)

    completion = PlanCompletionService().evaluate(HouseholdPlan.model_validate(data))

    assert _section(completion, "member_locations").status == "needs_information"


def test_plan_with_no_members_is_not_complete_for_locations() -> None:
    completion = PlanCompletionService().evaluate(HouseholdPlan())

    assert _section(completion, "member_locations").status == "needs_information"
