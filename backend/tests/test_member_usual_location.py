from copy import deepcopy

from app.schemas.households import HouseholdPlan, MemberUsualLocation


def test_member_without_usual_location_still_validates(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    for member in data["members"]:
        member.pop("usual_location", None)

    plan = HouseholdPlan.model_validate(data)

    assert plan.members[0].usual_location is None


def test_home_kind_needs_no_address() -> None:
    location = MemberUsualLocation(kind="home")

    assert location.address == ""
    assert location.latitude is None
    assert location.verification_status == "unverified"


def test_verified_work_location_round_trips(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "200 Bourke Street, Melbourne VIC 3000",
        "latitude": -37.8125,
        "longitude": 144.9665,
        "verification_status": "verified",
    }

    plan = HouseholdPlan.model_validate(data)

    assert plan.members[0].usual_location.kind == "work"
    assert plan.members[0].usual_location.latitude == -37.8125
    assert plan.members[0].usual_location.verification_status == "verified"
