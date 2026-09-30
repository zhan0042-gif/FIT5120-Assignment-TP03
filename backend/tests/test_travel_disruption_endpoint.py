import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import (
    get_household_repository,
    get_road_disruption_client,
)
from app.providers.mock import MockRoadDisruptionClient
from app.providers.road_disruptions import DisabledRoadDisruptionClient
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
    assert body["primary_destination"]["destination_address"] == "Example address"
    assert body["primary_destination"]["latitude"] == -37.8136
    assert body["primary_destination"]["longitude"] == 144.9631
    assert body["primary_destination"]["disruptions"][0]["latitude"] is not None


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


def test_missing_road_key_returns_feature_unavailable():
    repository, household_id = build_repository()

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_road_disruption_client] = (
        lambda: DisabledRoadDisruptionClient()
    )

    client = TestClient(app)

    try:
        response = client.get(
            f"/api/v1/households/{household_id}/travel-disruptions"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "not configured" in response.json()["unavailable_reason"]


def test_backend_starts_without_road_key_in_live_mode():
    environment = os.environ.copy()
    environment.update(
        {
            "APP_DATA_MODE": "live",
            "APP_REPOSITORY_MODE": "memory",
            "APP_SPATIAL_MODE": "mock",
            "TOMTOM_API_KEY": "test-key",
        }
    )
    environment.pop("VIC_ROAD_DISRUPTIONS_API_KEY", None)

    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from fastapi.testclient import TestClient; "
                "from app.main import app; "
                "client = TestClient(app); "
                "assert client.get('/api/health').status_code == 200; "
                "assert client.post('/api/v1/households').status_code == 201"
            ),
        ],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
