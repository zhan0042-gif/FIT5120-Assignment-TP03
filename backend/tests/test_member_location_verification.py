from copy import deepcopy

from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdPlan
from app.services.plans import HouseholdPlanService


class CountingAddressClient:
    """Resolves to fixed coordinates and records every address it was asked for."""

    def __init__(self) -> None:
        self.resolved: list[str] = []

    def resolve(self, address: str, *, provider_reference: str | None = None):
        from app.schemas.households import HouseholdLocation

        self.resolved.append(address)
        return HouseholdLocation(
            address=address,
            latitude=-37.8125,
            longitude=144.9665,
            verification_status="verified",
        )


def _plan_with(usual_location: dict, complete_plan_data: dict) -> HouseholdPlan:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = usual_location
    data["members"][1]["usual_location"] = {"kind": "home"}
    return HouseholdPlan.model_validate(data)


def test_a_new_member_address_is_verified_and_gains_coordinates(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    address_client = CountingAddressClient()
    plan = _plan_with(
        {"kind": "work", "address": "200 Bourke Street Melbourne VIC 3000"},
        complete_plan_data,
    )

    saved = HouseholdPlanService(repository, address_client).save(household_id, plan)

    location = saved.members[0].usual_location
    assert location.verification_status == "verified"
    assert location.latitude == -37.8125
    assert location.longitude == 144.9665
    assert "200 Bourke Street Melbourne VIC 3000" in address_client.resolved


def test_an_already_verified_address_is_not_resolved_again(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    address_client = CountingAddressClient()
    plan = _plan_with(
        {
            "kind": "work",
            "address": "200 Bourke Street Melbourne VIC 3000",
            "latitude": -37.8125,
            "longitude": 144.9665,
            "verification_status": "verified",
        },
        complete_plan_data,
    )

    saved = HouseholdPlanService(repository, address_client).save(household_id, plan)

    assert saved.members[0].usual_location.latitude == -37.8125
    assert "200 Bourke Street Melbourne VIC 3000" not in address_client.resolved


def test_home_members_are_never_resolved(complete_plan_data: dict) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    address_client = CountingAddressClient()

    HouseholdPlanService(repository, address_client).save(
        household_id, _plan_with({"kind": "home"}, complete_plan_data)
    )

    # Only the two fixture destinations are resolved; no member address is.
    assert address_client.resolved == ["1 Example Road", "2 Safe Street"]


def test_a_selected_suggestion_is_resolved_in_place_of_typed_text(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    address_client = CountingAddressClient()
    plan = _plan_with(
        {
            "kind": "school",
            "address": "50 Flemington Rd",
            "selected_address": "50 Flemington Road Parkville VIC 3052",
        },
        complete_plan_data,
    )

    HouseholdPlanService(repository, address_client).save(household_id, plan)

    assert "50 Flemington Road Parkville VIC 3052" in address_client.resolved


def test_an_unresolvable_address_saves_without_coordinates(
    complete_plan_data: dict,
) -> None:
    class UnavailableAddressClient:
        def resolve(self, address: str, *, provider_reference: str | None = None):
            from app.core.exceptions import ExternalDataUnavailable

            raise ExternalDataUnavailable("The address provider is unavailable.")

    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = _plan_with(
        {"kind": "work", "address": "200 Bourke Street Melbourne VIC 3000"},
        complete_plan_data,
    )

    saved = HouseholdPlanService(repository, UnavailableAddressClient()).save(
        household_id, plan
    )

    location = saved.members[0].usual_location
    assert location.verification_status == "unverified"
    assert location.latitude is None
    assert location.address == "200 Bourke Street Melbourne VIC 3000"
