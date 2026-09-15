from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import (
    get_household_repository,
    get_road_disruption_client,
)
from app.providers.mock import MockRoadDisruptionClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import (
    Arrangements,
    Destination,
    HouseholdPlan,
)


def verified_destination() -> Destination:
    return Destination(
        destination_id="destination_primary",
        display_name="Primary destination",
        address="Example address",
        latitude=-37.8136,
        longitude=144.9631,
        verification_status="verified",
    )


def build_repository():
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    repository.save_plan(
        household_id,
        HouseholdPlan(
            arrangements=Arrangements(
                primary_destination=verified_destination(),
            )
        ),
    )

    return repository, household_id


def test_travel_disruption_endpoint_returns_available_result():
    repository, household_id = build_repository()

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_road_disruption_client] = (
        lambda: MockRoadDisruptionClient()
    )

    client = TestClient(app)

    try:
        response = client.get(
            f"/api/v1/households/{household_id}/travel-disruptions"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "available"
    assert body["primary_destination"] is not None
    assert (
        body["primary_destination"]["destination_id"]
        == "destination_primary"
    )
    assert (
        body["primary_destination"]["active_disruption_count"]
        == 1
    )


def test_travel_disruption_endpoint_accepts_radius():
    repository, household_id = build_repository()

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_road_disruption_client] = (
        lambda: MockRoadDisruptionClient()
    )

    client = TestClient(app)

    try:
        response = client.get(
            f"/api/v1/households/{household_id}/travel-disruptions"
            "?radius_km=20"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "available"
    assert (
        body["primary_destination"]["search_radius_km"]
        == 20
    )


def test_travel_disruption_endpoint_rejects_invalid_radius():
    repository, household_id = build_repository()

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_road_disruption_client] = (
        lambda: MockRoadDisruptionClient()
    )

    client = TestClient(app)

    try:
        response = client.get(
            f"/api/v1/households/{household_id}/travel-disruptions"
            "?radius_km=0"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422