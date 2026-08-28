from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import ExternalDataUnavailable, HouseholdNotFound, LocationNotFound
from app.providers.mock import (
    MockAddressClient,
    MockFireDangerClient,
    MockSpatialProvider,
    MockWeatherClient,
)
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import CompletionSection, FireDanger, PlanCompletion
from app.services.context import (
    LocalContextService,
    LocationService,
    PreparationTimingService,
)


NOW = datetime(2026, 8, 28, 6, 0, tzinfo=timezone.utc)


def fire_danger(
    today: str = "Moderate",
    tomorrow: str = "Moderate",
    day_3: str = "Moderate",
    day_4: str = "Moderate",
    *,
    updated_at: datetime = NOW,
) -> FireDanger:
    return FireDanger.model_validate(
        {
            "today": today,
            "tomorrow": tomorrow,
            "day_3": day_3,
            "day_4": day_4,
            "source_updated_at": updated_at,
        }
    )


def completion(*incomplete: str) -> PlanCompletion:
    names = ["backup_transport", "backup_destination"]
    sections = [
        CompletionSection(
            section=name,
            status="needs_information" if name in incomplete else "complete",
        )
        for name in names
    ]
    return PlanCompletion(
        overall_status="needs_information" if incomplete else "complete",
        sections=sections,
    )


def test_local_context_aggregates_deterministic_mocks() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "  Warrandyte   VIC 3113  "
    )

    result = LocalContextService(
        repository,
        MockSpatialProvider(),
        MockFireDangerClient(),
        MockWeatherClient(),
    ).get(household_id)

    assert result.location.address == "Warrandyte VIC 3113"
    assert (result.location.latitude, result.location.longitude) == (-37.74, 145.21)
    assert result.bushfire_context.is_bushfire_prone_area is True
    assert result.bushfire_context.fire_district == "Central"
    assert result.fire_danger.today == "Moderate"
    assert result.fire_danger.source_updated_at.tzinfo is not None
    assert result.weather.temperature_c == 28.0
    assert result.weather.relative_humidity == 32
    assert result.weather.wind_speed_kmh == 30
    assert result.weather.wind_direction == "NW"
    assert result.weather.observed_at.tzinfo is not None
    assert result.weather.station_name == "Mock Melbourne Station"
    assert result.environmental_context.fire_history_summary is None
    assert result.environmental_context.vegetation_context is None
    assert result.environmental_context.terrain_context is None


def test_location_can_be_replaced_with_latest_resolved_value() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    service = LocationService(repository, MockAddressClient())

    service.save(household_id, "Warrandyte VIC 3113")
    updated = service.save(household_id, "  Melbourne   VIC 3000 ")

    assert updated.address == "Melbourne VIC 3000"
    assert (updated.latitude, updated.longitude) == (-37.8136, 144.9631)
    assert repository.get_location(household_id) == updated


class RecordingAddressClient:
    called = False

    def resolve(self, address: str):
        self.called = True
        return MockAddressClient().resolve(address)


def test_missing_household_is_rejected_before_address_provider_call() -> None:
    client = RecordingAddressClient()

    with pytest.raises(HouseholdNotFound):
        LocationService(InMemoryHouseholdRepository(), client).save(
            "missing", "Warrandyte VIC 3113"
        )

    assert client.called is False


class FailingAddressClient:
    def resolve(self, address: str):
        raise ValueError("bad provider payload")


def test_address_provider_failure_is_translated() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    with pytest.raises(ExternalDataUnavailable, match="Address resolution"):
        LocationService(repository, FailingAddressClient()).save(
            household_id, "Warrandyte VIC 3113"
        )


@dataclass(frozen=True)
class NonProneSpatialResult:
    is_bushfire_prone_area: bool = False
    fire_district: str = "Central"
    fire_history_summary: str | None = None
    vegetation_context: str | None = None
    terrain_context: str | None = None


class NonProneSpatialProvider:
    def get_context(self, latitude: float, longitude: float):
        return NonProneSpatialResult()


def test_false_bpa_and_missing_optional_context_do_not_block_required_context() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Melbourne VIC 3000"
    )

    result = LocalContextService(
        repository,
        NonProneSpatialProvider(),
        MockFireDangerClient(),
        MockWeatherClient(),
    ).get(household_id)

    assert result.bushfire_context.is_bushfire_prone_area is False
    assert result.environmental_context.model_dump() == {
        "fire_history_summary": None,
        "vegetation_context": None,
        "terrain_context": None,
    }


def test_local_context_requires_a_saved_location() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    with pytest.raises(LocationNotFound):
        LocalContextService(
            repository,
            MockSpatialProvider(),
            MockFireDangerClient(),
            MockWeatherClient(),
        ).get(household_id)


def test_low_non_escalating_conditions_need_no_review_when_complete() -> None:
    result = PreparationTimingService().recommend(
        fire_danger(), completion(), now=NOW
    )

    assert result.status == "up_to_date"
    assert result.sections_to_review == []


def test_no_rating_alone_does_not_recommend_review() -> None:
    result = PreparationTimingService().recommend(
        fire_danger("No Rating", "No Rating", "No Rating", "No Rating"),
        completion(),
        now=NOW,
    )

    assert result.status == "up_to_date"


def test_increasing_fire_danger_recommends_review() -> None:
    result = PreparationTimingService().recommend(
        fire_danger("Moderate", "High", "High", "Extreme"),
        completion(),
        now=NOW,
    )

    assert result.status == "review_recommended"
    assert "more serious" in result.message


def test_incomplete_plan_recommends_specific_sections() -> None:
    result = PreparationTimingService().recommend(
        fire_danger(),
        completion("backup_transport", "backup_destination"),
        now=NOW,
    )

    assert result.status == "review_recommended"
    assert result.sections_to_review == ["backup_transport", "backup_destination"]


def test_unknown_provider_rating_is_not_silently_swallowed() -> None:
    invalid = FireDanger.model_construct(
        today="Made Up Rating",
        tomorrow="Made Up Rating",
        day_3="Made Up Rating",
        day_4="Made Up Rating",
        source_updated_at=NOW,
    )
    with pytest.raises(ExternalDataUnavailable, match="Unsupported Fire Danger"):
        PreparationTimingService().recommend(invalid, completion(), now=NOW)


def test_fresh_fire_danger_may_generate_recommendation() -> None:
    result = PreparationTimingService().recommend(
        fire_danger("High", "High", "Extreme", "Extreme"),
        completion(),
        now=NOW,
    )

    assert result.status == "review_recommended"


def test_stale_fire_danger_cannot_generate_recommendation() -> None:
    stale = fire_danger(updated_at=NOW - timedelta(hours=25))

    with pytest.raises(ExternalDataUnavailable, match="stale"):
        PreparationTimingService().recommend(stale, completion(), now=NOW)


def test_timezone_less_fire_danger_cannot_generate_recommendation() -> None:
    unavailable = fire_danger(updated_at=NOW.replace(tzinfo=None))

    with pytest.raises(ExternalDataUnavailable, match="issue time is unavailable"):
        PreparationTimingService().recommend(unavailable, completion(), now=NOW)


@dataclass
class FailingSpatialProvider:
    def get_context(self, latitude: float, longitude: float):
        raise RuntimeError("provider offline")


class InvalidWeatherClient:
    def get_weather(self, latitude: float, longitude: float):
        return {"temperature_c": "not-a-number"}


def test_provider_failure_becomes_external_data_unavailable() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    with pytest.raises(ExternalDataUnavailable, match="provider data"):
        LocalContextService(
            repository,
            FailingSpatialProvider(),
            MockFireDangerClient(),
            MockWeatherClient(),
        ).get(household_id)


def test_provider_parse_failure_becomes_external_data_unavailable() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    with pytest.raises(ExternalDataUnavailable, match="provider data"):
        LocalContextService(
            repository,
            MockSpatialProvider(),
            MockFireDangerClient(),
            InvalidWeatherClient(),
        ).get(household_id)
