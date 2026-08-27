"""Location, local-context aggregation, and preparation timing services."""

from app.core.exceptions import ExternalDataUnavailable
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
    HouseholdLocation,
    LocalContext,
    PlanCompletion,
    PreparationSupport,
)


class LocationService:
    def __init__(self, repository: HouseholdRepository, address_client: AddressClient) -> None:
        self.repository = repository
        self.address_client = address_client

    def save(self, household_id: str, address: str) -> HouseholdLocation:
        try:
            location = self.address_client.resolve(address)
        except ExternalDataUnavailable:
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
            fire_danger = self.fire_danger_client.get_fire_danger(
                spatial.fire_district
            )
            weather = self.weather_client.get_weather(
                location.latitude, location.longitude
            )
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Local context provider data is unavailable."
            ) from exc

        return LocalContext(
            location=location,
            bushfire_context=BushfireContext(
                is_bushfire_prone_area=spatial.is_bushfire_prone_area,
                fire_district=spatial.fire_district,
            ),
            fire_danger=fire_danger,
            weather=weather,
            environmental_context=EnvironmentalContext(
                vegetation=spatial.vegetation,
                terrain=spatial.terrain,
            ),
        )


class PreparationTimingService:
    """Recommend review using supplied FDR values and plan completeness."""

    FDR_SEVERITY = {"No Rating": 0, "Moderate": 1, "High": 2, "Extreme": 3, "Catastrophic": 4}

    def recommend(
        self, fire_danger_values: list[str], completion: PlanCompletion
    ) -> PreparationSupport:
        incomplete = [
            item.section
            for item in completion.sections
            if item.status == "needs_information"
        ]
        try:
            levels = [self.FDR_SEVERITY[value] for value in fire_danger_values]
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

