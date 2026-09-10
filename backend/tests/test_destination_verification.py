from copy import deepcopy

from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdPlan
from app.services.plans import HouseholdPlanService


class UnavailableAddressClient:
    def resolve(self, address: str):
        from app.core.exceptions import ExternalDataUnavailable

        raise ExternalDataUnavailable("The address provider is unavailable.")


def test_manual_destination_address_saves_unverified_when_provider_is_unavailable(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = deepcopy(complete_plan_data)
    destination = plan["arrangements"]["primary_destination"]
    destination["address"] = "999 Manual Road Nowhere VIC 3999"
    destination["latitude"] = -37.8
    destination["longitude"] = 145.2

    saved = HouseholdPlanService(repository, UnavailableAddressClient()).save(
        household_id, HouseholdPlan.model_validate(plan)
    ).arrangements.primary_destination

    assert saved is not None
    assert saved.address == "999 Manual Road Nowhere VIC 3999"
    assert saved.verification_status == "unverified"
    assert saved.canonical_address is None
    assert saved.latitude is None
    assert saved.longitude is None
