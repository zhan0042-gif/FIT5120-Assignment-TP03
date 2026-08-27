from dataclasses import dataclass

import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.mock import (
    MockAddressClient,
    MockFireDangerClient,
    MockSpatialProvider,
    MockWeatherClient,
)
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import CompletionSection, PlanCompletion
from app.services.context import (
    LocalContextService,
    LocationService,
    PreparationTimingService,
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
    assert result.weather.wind_direction == "NW"


def test_low_non_escalating_conditions_need_no_review_when_complete() -> None:
    result = PreparationTimingService().recommend(
        ["Moderate"] * 4, completion()
    )

    assert result.status == "up_to_date"
    assert result.sections_to_review == []


def test_increasing_fire_danger_recommends_review() -> None:
    result = PreparationTimingService().recommend(
        ["Moderate", "High", "High", "Extreme"], completion()
    )

    assert result.status == "review_recommended"
    assert "more serious" in result.message


def test_incomplete_plan_recommends_specific_sections() -> None:
    result = PreparationTimingService().recommend(
        ["Moderate"] * 4, completion("backup_transport", "backup_destination")
    )

    assert result.status == "review_recommended"
    assert result.sections_to_review == ["backup_transport", "backup_destination"]


def test_unknown_provider_rating_is_not_silently_swallowed() -> None:
    with pytest.raises(ExternalDataUnavailable, match="Unsupported Fire Danger"):
        PreparationTimingService().recommend(
            ["Made Up Rating"] * 4, completion()
        )


@dataclass
class FailingSpatialProvider:
    def get_context(self, latitude: float, longitude: float):
        raise RuntimeError("provider offline")


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

