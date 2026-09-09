from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import spatial_cache_max_age
from app.providers.mock import MockFireDangerClient, MockWeatherClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import (
    HouseholdLocation,
    HouseholdLocationContext,
    PlanCompletion,
)
from app.services.context import (
    HouseholdStaticContextResolver,
    LocalContextService,
    PreparationSupportService,
)


NOW = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class RefreshedSpatialResult:
    is_bushfire_prone_area: bool = False
    fire_district: str = "Mallee"
    vegetation_context: str | None = None
    terrain_context: str | None = None
    fire_history_record_count: int = 7
    fire_history_latest_year: int = 2025
    fire_history_latest_date: str = "2025-02-03"
    fire_history_radius_km: float = 20


class RefreshTrackingSpatialProvider:
    def __init__(self) -> None:
        self.full_calls = 0
        self.district_calls = 0

    def get_context(self, latitude: float, longitude: float):
        self.full_calls += 1
        return RefreshedSpatialResult()

    def get_fire_district(self, latitude: float, longitude: float) -> str:
        self.district_calls += 1
        return "Mallee"

    def get_fire_history_points(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
        limit: int,
    ) -> list[dict]:
        return []


def repository_with_cache(
    generated_at: datetime,
) -> tuple[InMemoryHouseholdRepository, str]:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="84 Yarra Street, Warrandyte VIC 3113",
            latitude=-37.74,
            longitude=145.21,
            verification_status="verified",
        ),
    )
    repository.save_location_context(
        household_id,
        HouseholdLocationContext(
            is_bushfire_prone_area=True,
            fire_district="Central",
            fire_history_record_count=2,
            fire_history_latest_year=2024,
            fire_history_latest_date="2024-02-03",
            fire_history_radius_km=20,
            generated_at=generated_at,
        ),
    )
    return repository, household_id


def completion() -> PlanCompletion:
    return PlanCompletion(overall_status="complete", sections=[])


def resolver(repository, provider) -> HouseholdStaticContextResolver:
    return HouseholdStaticContextResolver(
        repository,
        provider,
        cache_max_age=timedelta(hours=24),
        now_provider=lambda: NOW,
    )


def test_spatial_cache_default_and_environment_override(monkeypatch) -> None:
    monkeypatch.delenv("APP_SPATIAL_CACHE_MAX_AGE_HOURS", raising=False)
    assert spatial_cache_max_age() == timedelta(hours=24)

    monkeypatch.setenv("APP_SPATIAL_CACHE_MAX_AGE_HOURS", "6.5")
    assert spatial_cache_max_age() == timedelta(hours=6.5)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "infinity", "invalid"])
def test_invalid_spatial_cache_max_age_fails_safely(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("APP_SPATIAL_CACHE_MAX_AGE_HOURS", value)

    with pytest.raises(RuntimeError, match="positive finite"):
        spatial_cache_max_age()


def test_cache_at_exact_max_age_is_fresh_and_naive_time_is_utc() -> None:
    repository, household_id = repository_with_cache(
        (NOW - timedelta(hours=24)).replace(tzinfo=None)
    )
    provider = RefreshTrackingSpatialProvider()

    district = resolver(repository, provider).get_fire_district(household_id)

    assert district == "Central"
    assert provider.full_calls == 0
    assert provider.district_calls == 0


def test_expired_cache_is_rebuilt_for_local_context() -> None:
    old_generated_at = NOW - timedelta(hours=24, microseconds=1)
    repository, household_id = repository_with_cache(old_generated_at)
    provider = RefreshTrackingSpatialProvider()
    service = LocalContextService(
        repository, provider, MockFireDangerClient(), MockWeatherClient()
    )
    service.static_context = resolver(repository, provider)

    result = service.get(household_id)
    refreshed = repository.get_location_context(household_id)

    assert result.bushfire_context.fire_district == "Mallee"
    assert provider.full_calls == 1
    assert refreshed is not None
    assert refreshed.generated_at == NOW
    assert refreshed.generated_at > old_generated_at


def test_expired_cache_uses_narrow_district_for_preparation() -> None:
    repository, household_id = repository_with_cache(
        NOW - timedelta(hours=25)
    )
    provider = RefreshTrackingSpatialProvider()
    service = PreparationSupportService(
        repository, provider, MockFireDangerClient()
    )
    service.static_context = resolver(repository, provider)

    result = service.get(household_id, completion())

    assert result.status == "review_recommended"
    assert provider.full_calls == 0
    assert provider.district_calls == 1
    assert repository.get_location_context(household_id).fire_district == "Central"


def test_future_generated_at_is_not_trusted() -> None:
    repository, household_id = repository_with_cache(NOW + timedelta(seconds=1))
    provider = RefreshTrackingSpatialProvider()

    district = resolver(repository, provider).get_fire_district(household_id)

    assert district == "Mallee"
    assert provider.district_calls == 1


def test_location_change_invalidates_even_a_fresh_cache() -> None:
    repository, household_id = repository_with_cache(NOW)

    repository.save_location(
        household_id,
        HouseholdLocation(
            address="Melbourne VIC 3000",
            latitude=-37.8136,
            longitude=144.9631,
            verification_status="verified",
        ),
    )

    assert repository.get_location_context(household_id) is None
