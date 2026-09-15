from app.core.exceptions import ExternalDataUnavailable
from app.providers.mock import MockRoadDisruptionClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import (
    Arrangements,
    BackupArrangement,
    Destination,
    HouseholdPlan,
)
from app.services.travel_disruptions import TravelDisruptionService


def verified_destination(
    destination_id: str,
    name: str,
    latitude: float,
    longitude: float,
) -> Destination:
    return Destination(
        destination_id=destination_id,
        display_name=name,
        address=f"{name} address",
        latitude=latitude,
        longitude=longitude,
        verification_status="verified",
    )


def repository_with_plan(plan: HouseholdPlan):
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(household_id, plan)
    return repository, household_id


def test_primary_destination_disruptions_are_returned():
    destination = verified_destination(
        "destination_primary",
        "Primary destination",
        -37.8136,
        144.9631,
    )

    plan = HouseholdPlan(
        arrangements=Arrangements(
            primary_destination=destination,
        )
    )

    repository, household_id = repository_with_plan(plan)

    result = TravelDisruptionService(
        repository,
        MockRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "available"
    assert result.primary_destination is not None
    assert result.primary_destination.destination_id == "destination_primary"
    assert result.primary_destination.destination_name == "Primary destination"
    assert result.primary_destination.active_disruption_count == 1
    assert len(result.primary_destination.disruptions) == 1


def test_backup_destinations_are_returned():
    backup = verified_destination(
        "destination_backup",
        "Backup destination",
        -37.82,
        144.97,
    )

    plan = HouseholdPlan(
        arrangements=Arrangements(
            backup_arrangements=[
                BackupArrangement(
                    destination=backup,
                )
            ],
        )
    )

    repository, household_id = repository_with_plan(plan)

    result = TravelDisruptionService(
        repository,
        MockRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "available"
    assert result.primary_destination is None
    assert len(result.backup_destinations) == 1
    assert (
        result.backup_destinations[0].destination_id
        == "destination_backup"
    )


def test_primary_and_backup_destinations_are_both_checked():
    primary = verified_destination(
        "primary",
        "Primary",
        -37.8136,
        144.9631,
    )

    backup = verified_destination(
        "backup",
        "Backup",
        -37.82,
        144.97,
    )

    plan = HouseholdPlan(
        arrangements=Arrangements(
            primary_destination=primary,
            backup_arrangements=[
                BackupArrangement(destination=backup)
            ],
        )
    )

    repository, household_id = repository_with_plan(plan)

    result = TravelDisruptionService(
        repository,
        MockRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "available"
    assert result.primary_destination is not None
    assert len(result.backup_destinations) == 1


def test_unverified_destinations_are_not_used():
    destination = Destination(
        destination_id="destination_unverified",
        display_name="Unverified destination",
        address="Some address",
        verification_status="unverified",
    )

    plan = HouseholdPlan(
        arrangements=Arrangements(
            primary_destination=destination,
        )
    )

    repository, household_id = repository_with_plan(plan)

    result = TravelDisruptionService(
        repository,
        MockRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "not_applicable"
    assert result.primary_destination is None
    assert "verify" in result.unavailable_reason.lower()


def test_no_destinations_is_not_applicable():
    repository, household_id = repository_with_plan(
        HouseholdPlan()
    )

    result = TravelDisruptionService(
        repository,
        MockRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "not_applicable"
    assert result.unavailable_reason is not None


class FailingRoadDisruptionClient:
    def nearby_disruptions(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ):
        raise ExternalDataUnavailable(
            "Current road-disruption information is temporarily unavailable."
        )


def test_provider_failure_returns_unavailable():
    destination = verified_destination(
        "primary",
        "Primary",
        -37.8136,
        144.9631,
    )

    plan = HouseholdPlan(
        arrangements=Arrangements(
            primary_destination=destination,
        )
    )

    repository, household_id = repository_with_plan(plan)

    result = TravelDisruptionService(
        repository,
        FailingRoadDisruptionClient(),
    ).get(household_id)

    assert result.status == "unavailable"
    assert result.unavailable_reason is not None
    assert "temporarily unavailable" in result.unavailable_reason