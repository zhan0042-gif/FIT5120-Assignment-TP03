"""Location, local-context aggregation, and preparation timing services."""

from datetime import datetime, timedelta, timezone

from app.core.exceptions import (
    AddressResolutionError,
    ExternalDataUnavailable,
    HouseholdNotFound,
)
from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    BushfireContext,
    EnvironmentalContext,
    FireDanger,
    HouseholdLocation,
    LocalContext,
    PlanCompletion,
    PreparationSupport,
    UnavailableFireDanger,
)


class LocationService:
    def __init__(self, repository: HouseholdRepository, address_client: AddressClient) -> None:
        self.repository = repository
        self.address_client = address_client

    def save(self, household_id: str, address: str) -> HouseholdLocation:
        if not self.repository.household_exists(household_id):
            raise HouseholdNotFound(f"Household '{household_id}' was not found.")
        try:
            location = self.address_client.resolve(address)
        except (AddressResolutionError, ExternalDataUnavailable):
            raise
        except Exception as exc:
            raise ExternalDataUnavailable("Address resolution is unavailable.") from exc
        self.repository.save_location(household_id, location)
        return location


class LocalContextService:
    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        fire_danger_client: FireDangerClient,
        weather_client: WeatherClient,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.fire_danger_client = fire_danger_client
        self.weather_client = weather_client

    def get(self, household_id: str) -> LocalContext:
        location = self.repository.get_location(household_id)
        try:
            spatial = self.spatial_provider.get_context(
                location.latitude, location.longitude
            )
            try:
                fire_danger = self.fire_danger_client.get_fire_danger(
                    spatial.fire_district
                )
                PreparationTimingService().ensure_fresh(
                    fire_danger, datetime.now(timezone.utc)
                )
            except ExternalDataUnavailable:
                fire_danger = UnavailableFireDanger()
            weather = self.weather_client.get_weather(
                location.latitude, location.longitude
            )
            return LocalContext(
                location=location,
                bushfire_context=BushfireContext(
                    is_bushfire_prone_area=spatial.is_bushfire_prone_area,
                    fire_district=spatial.fire_district,
                ),
                fire_danger=fire_danger,
                weather=weather,
                environmental_context=EnvironmentalContext(
                    fire_history_summary=spatial.fire_history_summary,
                    vegetation_context=spatial.vegetation_context,
                    terrain_context=spatial.terrain_context,
                ),
            )
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Local context provider data is unavailable."
            ) from exc


class PreparationTimingService:
    """Recommend review using supplied FDR values and plan completeness."""

    FDR_SEVERITY = {"No Rating": 0, "Moderate": 1, "High": 2, "Extreme": 3, "Catastrophic": 4}
    FIRE_DANGER_MAX_AGE = timedelta(hours=24)
    FIRE_DANGER_FUTURE_TOLERANCE = timedelta(minutes=5)

    def recommend(
        self,
        fire_danger: FireDanger,
        completion: PlanCompletion,
        *,
        now: datetime | None = None,
    ) -> PreparationSupport:
        self.ensure_fresh(fire_danger, now or datetime.now(timezone.utc))
        incomplete = [
            item.section
            for item in completion.sections
            if item.status == "needs_information"
        ]
        try:
            levels = [
                self.FDR_SEVERITY[value]
                for value in (
                    fire_danger.today,
                    fire_danger.tomorrow,
                    fire_danger.day_3,
                    fire_danger.day_4,
                )
            ]
        except KeyError as exc:
            raise ExternalDataUnavailable(
                f"Unsupported Fire Danger Rating supplied: {exc.args[0]}"
            ) from exc

        escalating = max(levels[1:], default=levels[0]) > levels[0]
        serious = max(levels) >= self.FDR_SEVERITY["High"]
        if escalating or serious:
            return PreparationSupport(
                status="review_recommended",
                message="Local fire conditions are expected to become more serious.",
                sections_to_review=incomplete,
            )
        if incomplete:
            return PreparationSupport(
                status="review_recommended",
                message="Review the incomplete sections of your household plan.",
                sections_to_review=incomplete,
            )
        return PreparationSupport(
            status="up_to_date",
            message="No immediate plan review is recommended.",
            sections_to_review=[],
        )

    def ensure_fresh(self, fire_danger: FireDanger, now: datetime) -> None:
        updated_at = fire_danger.source_updated_at
        if updated_at.tzinfo is None or updated_at.utcoffset() is None:
            raise ExternalDataUnavailable(
                "Fire Danger Rating issue time is unavailable."
            )
        age = now.astimezone(timezone.utc) - updated_at.astimezone(timezone.utc)
        if age > self.FIRE_DANGER_MAX_AGE:
            raise ExternalDataUnavailable(
                "Fire Danger Rating data is stale; preparation support is unavailable."
            )
        if age < -self.FIRE_DANGER_FUTURE_TOLERANCE:
            raise ExternalDataUnavailable(
                "Fire Danger Rating issue time is invalid."
            )


class PreparationSupportService:
    """Combine plan completion and FDR without depending on weather data."""

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        fire_danger_client: FireDangerClient,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.fire_danger_client = fire_danger_client

    def get(
        self, household_id: str, completion: PlanCompletion
    ) -> PreparationSupport:
        location = self.repository.get_location(household_id)
        try:
            spatial = self.spatial_provider.get_context(
                location.latitude, location.longitude
            )
            fire_danger = self.fire_danger_client.get_fire_danger(
                spatial.fire_district
            )
            return PreparationTimingService().recommend(fire_danger, completion)
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Preparation support provider data is unavailable."
            ) from exc
