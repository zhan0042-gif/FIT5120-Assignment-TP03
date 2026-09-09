from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.exceptions import ExternalDataUnavailable, HouseholdNotFound, LocationNotFound
from app.providers.mock import (
    MockAddressClient,
    MockFireDangerClient,
    MockSpatialProvider,
    MockWeatherClient,
)
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import (
    CompletionSection,
    FireDanger,
    FireDangerContext,
    HouseholdLocation,
    HouseholdLocationContext,
    PlanCompletion,
)
from app.services.context import (
    LocalContextService,
    LocationService,
    PreparationSupportService,
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
    names = [
        "household_profile",
        "transport",
        "backup_transport",
        "primary_destination",
        "backup_destination",
        "responsibilities",
    ]
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


@pytest.mark.parametrize(
    "payload",
    [
        {
            "availability": "available",
            "today": None,
            "tomorrow": "Moderate",
            "day_3": "Moderate",
            "day_4": "Moderate",
            "source_updated_at": NOW,
            "message": None,
        },
        {
            "availability": "unavailable",
            "today": "No Rating",
            "tomorrow": None,
            "day_3": None,
            "day_4": None,
            "source_updated_at": None,
            "message": "Official data is unavailable.",
        },
    ],
)
def test_fire_danger_availability_union_rejects_invalid_combinations(
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(FireDangerContext).validate_python(payload)


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
    assert result.fire_danger.availability == "available"
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


def test_device_location_uses_coordinates_without_claiming_address_verification() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    service = LocationService(repository, MockAddressClient())

    saved = service.save_device_location(household_id, -37.8136, 144.9631)
    context = LocalContextService(
        repository,
        MockSpatialProvider(),
        MockFireDangerClient(),
        MockWeatherClient(),
    ).get(household_id)

    assert saved.address == ""
    assert saved.location_source == "device_location"
    assert saved.verification_status == "unverified"
    assert saved.canonical_address is None
    assert (context.location.latitude, context.location.longitude) == pytest.approx(
        (-37.8136, 144.9631)
    )


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


def test_address_provider_failure_keeps_the_saved_address_unverified() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    location = LocationService(repository, FailingAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    assert location.address == "Warrandyte VIC 3113"
    assert location.verification_status == "unverified"
    assert location.latitude is None


class CanonicalAddressClient:
    def resolve(self, address: str):
        assert address == "788 drummond st, carlton north vic 3054"
        return HouseholdLocation(
            address="788 DRUMMOND STREET CARLTON NORTH VIC 3054",
            latitude=-37.7861013,
            longitude=144.9712111,
        )


def test_manual_address_keeps_raw_text_and_persists_provider_canonical_result() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    location = LocationService(repository, CanonicalAddressClient()).save(
        household_id, "  788 drummond st,  carlton north vic 3054  "
    )

    assert location.address == "788 drummond st, carlton north vic 3054"
    assert location.canonical_address == "788 DRUMMOND STREET CARLTON NORTH VIC 3054"
    assert location.verification_status == "verified"
    assert (location.latitude, location.longitude) == pytest.approx(
        (-37.7861013, 144.9712111)
    )


def test_selected_official_address_is_saved_as_verified() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()

    location = LocationService(repository, MockAddressClient()).save(
        household_id,
        "1 Treasury Place, East Melbourne VIC 3002",
        "Melbourne VIC 3000",
    )

    assert location.address == "1 Treasury Place, East Melbourne VIC 3002"
    assert location.canonical_address == "Melbourne VIC 3000"
    assert location.verification_status == "verified"
    assert location.latitude is not None


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


class CountingSpatialProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_context(self, latitude: float, longitude: float):
        self.calls += 1
        return NonProneSpatialResult()


class PreparationSpatialProvider:
    def __init__(self, district: str = "Central") -> None:
        self.district = district
        self.full_calls = 0
        self.district_calls = 0

    def get_context(self, latitude: float, longitude: float):
        self.full_calls += 1
        raise AssertionError("preparation support requested full spatial context")

    def get_fire_district(self, latitude: float, longitude: float) -> str:
        self.district_calls += 1
        assert (latitude, longitude) == (-37.74, 145.21)
        return self.district


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


def test_static_context_is_cached_and_address_change_invalidates_it() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )
    spatial = CountingSpatialProvider()
    service = LocalContextService(
        repository, spatial, MockFireDangerClient(), MockWeatherClient()
    )

    service.get(household_id)
    service.get(household_id)

    assert spatial.calls == 1
    assert repository.get_location_context(household_id) is not None

    LocationService(repository, MockAddressClient()).save(
        household_id, "Melbourne VIC 3000"
    )
    assert repository.get_location_context(household_id) is None

    service.get(household_id)
    assert spatial.calls == 2


def test_local_context_cache_hit_uses_cached_fields_without_full_lookup() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )
    repository.save_location_context(
        household_id,
        HouseholdLocationContext(
            is_bushfire_prone_area=False,
            fire_district="Mallee",
            fire_history_record_count=2,
            fire_history_latest_year=2023,
            fire_history_latest_date="2023-01-05",
            fire_history_radius_km=15,
            generated_at=datetime.now(timezone.utc),
        ),
    )
    spatial = PreparationSpatialProvider()

    result = LocalContextService(
        repository, spatial, MockFireDangerClient(), MockWeatherClient()
    ).get(household_id)

    assert result.bushfire_context.is_bushfire_prone_area is False
    assert result.bushfire_context.fire_district == "Mallee"
    assert result.environmental_context.fire_history_summary == (
        "2 historical bushfire records were found within 15 km. "
        "The latest recorded burn season was 2023. "
        "The most recent dated record was 2023-01-05."
    )
    assert spatial.full_calls == 0
    assert spatial.district_calls == 0


def test_preparation_support_uses_cached_fire_district() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )
    repository.save_location_context(
        household_id,
        HouseholdLocationContext(
            is_bushfire_prone_area=True,
            fire_district="Central",
            fire_history_record_count=4,
            fire_history_latest_year=2025,
            fire_history_latest_date="2025-02-03",
            fire_history_radius_km=20,
            generated_at=datetime.now(timezone.utc),
        ),
    )
    spatial = PreparationSpatialProvider()

    result = PreparationSupportService(
        repository, spatial, MockFireDangerClient()
    ).get(household_id, completion())

    assert result.status == "review_recommended"
    assert spatial.full_calls == 0
    assert spatial.district_calls == 0


def test_preparation_support_cache_miss_uses_only_district_lookup() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )
    spatial = PreparationSpatialProvider()

    result = PreparationSupportService(
        repository, spatial, MockFireDangerClient()
    ).get(household_id, completion())

    assert result.status == "review_recommended"
    assert spatial.full_calls == 0
    assert spatial.district_calls == 1
    assert repository.get_location_context(household_id) is None


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
        completion(
            "transport",
            "backup_transport",
            "primary_destination",
            "backup_destination",
            "responsibilities",
        ),
        now=NOW,
    )

    assert result.status == "review_recommended"
    assert result.message == (
        "Current or forecast fire danger conditions indicate it is time to review "
        "your household preparedness plan."
    )
    assert result.sections_to_review == [
        "transport",
        "backup_transport",
        "primary_destination",
        "backup_destination",
        "responsibilities",
    ]
    assert "bushfire will" not in result.message.casefold()
    assert "evacuation is required" not in result.message.casefold()


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


class UnavailableFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise ExternalDataUnavailable("Official FDR is unavailable.")


class UnavailableWeatherClient:
    def get_weather(self, latitude: float, longitude: float):
        raise ExternalDataUnavailable("Official weather is unavailable.")


class UnexpectedFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise RuntimeError("unexpected parser defect")


def test_explicit_fire_danger_unavailability_is_partial() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    result = LocalContextService(
        repository,
        MockSpatialProvider(),
        UnavailableFireDangerClient(),
        MockWeatherClient(),
    ).get(household_id)

    assert result.location.address == "Warrandyte VIC 3113"
    assert result.bushfire_context.fire_district == "Central"
    assert result.weather.station_name == "Mock Melbourne Station"
    assert result.environmental_context.vegetation_context is None
    assert result.fire_danger.model_dump() == {
        "availability": "unavailable",
        "today": None,
        "tomorrow": None,
        "day_3": None,
        "day_4": None,
        "source_updated_at": None,
        "source_url": None,
        "message": (
            "Current fire danger information is not available from the official source."
        ),
    }


def test_stale_fire_danger_is_not_exposed_by_local_context() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    result = LocalContextService(
        repository,
        MockSpatialProvider(),
        MockFireDangerClient(
            source_updated_at=datetime.now(timezone.utc) - timedelta(hours=25)
        ),
        MockWeatherClient(),
    ).get(household_id)

    assert result.fire_danger.availability == "unavailable"
    assert result.fire_danger.today is None


def test_explicit_weather_unavailability_preserves_spatial_context() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    result = LocalContextService(
        repository,
        MockSpatialProvider(),
        MockFireDangerClient(),
        UnavailableWeatherClient(),
    ).get(household_id)

    assert result.bushfire_context.fire_district == "Central"
    assert result.fire_danger.availability == "available"
    assert result.weather is None


def test_unexpected_fire_danger_error_is_not_converted_to_partial_context() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    LocationService(repository, MockAddressClient()).save(
        household_id, "Warrandyte VIC 3113"
    )

    with pytest.raises(ExternalDataUnavailable, match="provider data"):
        LocalContextService(
            repository,
            MockSpatialProvider(),
            UnexpectedFireDangerClient(),
            MockWeatherClient(),
        ).get(household_id)


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
