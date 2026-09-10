from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository, get_spatial_provider
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdLocationContext


@dataclass(frozen=True)
class MapSpatialResult:
    is_bushfire_prone_area: bool = True
    fire_district: str = "Central"
    vegetation_context: str | None = None
    terrain_context: str | None = None
    fire_history_record_count: int = 0
    fire_history_latest_year: int | None = None
    fire_history_latest_date: str | None = None
    fire_history_radius_km: float = 20


class MapSpatialProvider:
    def __init__(self, points: list[dict], total_count: int | None = None) -> None:
        self.points = points
        self.total_count = len(points) if total_count is None else total_count
        self.full_calls = 0
        self.point_calls: list[tuple[float, float, float, int]] = []

    def get_context(self, latitude: float, longitude: float) -> MapSpatialResult:
        self.full_calls += 1
        dated = [
            point["start_date"]
            for point in self.points
            if point.get("start_date") is not None
        ]
        seasons = [
            point["season"]
            for point in self.points
            if point.get("season") is not None
        ]
        return MapSpatialResult(
            fire_history_record_count=self.total_count,
            fire_history_latest_year=max(seasons, default=None),
            fire_history_latest_date=(
                max(dated).isoformat() if dated else None
            ),
        )

    def get_fire_district(self, latitude: float, longitude: float) -> str:
        return "Central"

    def get_fire_history_points(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
        limit: int,
    ) -> list[dict]:
        self.point_calls.append((latitude, longitude, radius_km, limit))
        return self.points[:limit]


@pytest.fixture
def map_api():
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def save_verified_location(
    repository: InMemoryHouseholdRepository, household_id: str
) -> None:
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="84 Yarra Street, Warrandyte VIC 3113",
            canonical_address="84 Yarra Street, Warrandyte VIC 3113",
            latitude=-37.74,
            longitude=145.21,
            verification_status="verified",
        ),
    )


def sample_points() -> list[dict]:
    return [
        {
            "latitude": -37.70,
            "longitude": 145.20,
            "season": 2025,
            "start_date": date(2025, 2, 3),
        },
        {
            "latitude": -37.71,
            "longitude": 145.19,
            "season": 2024,
            "start_date": None,
        },
    ]


def test_historical_fire_map_returns_structured_response_with_default_limit(
    map_api,
) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)
    provider = MapSpatialProvider(sample_points())
    app.dependency_overrides[get_spatial_provider] = lambda: provider

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points"
    )

    assert response.status_code == 200
    assert response.json() == {
        "household_location": {
            "latitude": -37.74,
            "longitude": 145.21,
        },
        "search_radius_km": 20.0,
        "total_count": 2,
        "returned_count": 2,
        "truncated": False,
        "points": [
            {
                "latitude": -37.70,
                "longitude": 145.20,
                "season": 2025,
                "start_date": "2025-02-03",
            },
            {
                "latitude": -37.71,
                "longitude": 145.19,
                "season": 2024,
                "start_date": None,
            },
        ],
    }
    assert provider.full_calls == 1
    assert provider.point_calls == [(-37.74, 145.21, 20.0, 500)]


def test_historical_fire_map_is_supported_by_default_mock_provider(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points"
    )

    assert response.status_code == 200
    assert response.json()["search_radius_km"] == 20.0
    assert response.json()["total_count"] == 0
    assert response.json()["returned_count"] == 0
    assert response.json()["truncated"] is False
    assert response.json()["points"] == []


def test_historical_fire_map_applies_custom_limit_and_reports_truncation(
    map_api,
) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)
    provider = MapSpatialProvider(sample_points(), total_count=3)
    app.dependency_overrides[get_spatial_provider] = lambda: provider

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points?limit=1"
    )

    assert response.status_code == 200
    assert response.json()["total_count"] == 3
    assert response.json()["returned_count"] == 1
    assert response.json()["truncated"] is True
    assert len(response.json()["points"]) == 1
    assert provider.point_calls == [(-37.74, 145.21, 20.0, 1)]


def test_historical_fire_map_reuses_fresh_summary_count_and_radius(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)
    repository.save_location_context(
        household_id,
        HouseholdLocationContext(
            is_bushfire_prone_area=True,
            fire_district="Central",
            fire_history_record_count=8,
            fire_history_latest_year=2025,
            fire_history_latest_date="2025-02-03",
            fire_history_radius_km=12.5,
            generated_at=datetime.now(timezone.utc),
        ),
    )
    provider = MapSpatialProvider(sample_points(), total_count=99)
    app.dependency_overrides[get_spatial_provider] = lambda: provider

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points?limit=2"
    )

    assert response.status_code == 200
    assert response.json()["search_radius_km"] == 12.5
    assert response.json()["total_count"] == 8
    assert response.json()["returned_count"] == 2
    assert response.json()["truncated"] is True
    assert provider.full_calls == 0
    assert provider.point_calls == [(-37.74, 145.21, 12.5, 2)]


def test_historical_fire_map_rejects_limit_above_maximum(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)
    provider = MapSpatialProvider(sample_points())
    app.dependency_overrides[get_spatial_provider] = lambda: provider

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points?limit=1001"
    )

    assert response.status_code == 422
    assert provider.full_calls == 0
    assert provider.point_calls == []


def test_historical_fire_map_requires_a_saved_location(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points"
    )

    assert response.status_code == 404


def test_historical_fire_map_rejects_an_unverified_location(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(address="Unverified address"),
    )

    response = client.get(
        f"/api/v1/households/{household_id}/historical-fire-points"
    )

    assert response.status_code == 409
    assert "address is saved" in response.json()["detail"]


def test_local_context_does_not_fetch_historical_fire_points(map_api) -> None:
    client, repository = map_api
    household_id = repository.create_household()
    save_verified_location(repository, household_id)
    provider = MapSpatialProvider(sample_points())
    app.dependency_overrides[get_spatial_provider] = lambda: provider

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 200
    assert "points" not in response.json()["environmental_context"]
    assert provider.point_calls == []
