"""Stable mock providers for local development and automated tests."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.households import FireDanger, HouseholdLocation, Weather


@dataclass(frozen=True)
class MockSpatialResult:
    latitude: float
    longitude: float
    is_bushfire_prone_area: bool
    fire_district: str
    fire_history_summary: str | None = None
    vegetation_context: str | None = None
    terrain_context: str | None = None


class MockAddressClient:
    """Resolve addresses without network access using stable Victoria examples."""

    _KNOWN_ADDRESSES = {
        "warrandyte vic 3113": (-37.74, 145.21),
        "melbourne vic 3000": (-37.8136, 144.9631),
    }

    def resolve(self, address: str) -> HouseholdLocation:
        standardized = " ".join(address.strip().split())
        coordinates = self._KNOWN_ADDRESSES.get(
            standardized.casefold(), (-37.814, 144.963)
        )
        return HouseholdLocation(
            address=standardized,
            latitude=coordinates[0],
            longitude=coordinates[1],
        )


class MockSpatialProvider:
    def get_context(self, latitude: float, longitude: float) -> MockSpatialResult:
        return MockSpatialResult(
            latitude=latitude,
            longitude=longitude,
            is_bushfire_prone_area=True,
            fire_district="Central",
        )


class MockFireDangerClient:
    def __init__(self, source_updated_at: datetime | None = None) -> None:
        # Development timestamp only; this is not a live CFA observation.
        self.source_updated_at = source_updated_at or datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

    def get_fire_danger(self, fire_district: str) -> FireDanger:
        return FireDanger(
            today="Moderate",
            tomorrow="High",
            day_3="High",
            day_4="Extreme",
            source_updated_at=self.source_updated_at,
        )


class MockWeatherClient:
    def __init__(self, forecast_time: datetime | None = None) -> None:
        # Development timestamp only; this is not a live BOM forecast.
        self.forecast_time = forecast_time or datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

    def get_weather(self, latitude: float, longitude: float) -> Weather:
        return Weather(
            temperature_c=28.0,
            relative_humidity=32,
            wind_speed_kmh=30,
            wind_direction="NW",
            forecast_time=self.forecast_time,
        )
