"""Provider boundaries keep official-data integrations out of business services."""

from typing import Protocol

from app.schemas.households import (
    AddressSuggestion,
    FireDanger,
    HouseholdLocation,
    Weather,
)


class SpatialResult(Protocol):
    is_bushfire_prone_area: bool
    fire_district: str
    vegetation_context: str | None
    terrain_context: str | None
    fire_history_record_count: int | None
    fire_history_latest_year: int | None
    fire_history_latest_date: str | None
    fire_history_radius_km: float | None


class AddressClient(Protocol):
    """Supply partial suggestions and stricter final official resolution."""

    def resolve(self, address: str) -> HouseholdLocation: ...

    def suggest(self, query: str, limit: int = 8) -> list[AddressSuggestion]: ...

    def reverse(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> list[AddressSuggestion]: ...


class SpatialProvider(Protocol):
    """Resolve static context from verified coordinates."""

    def get_context(self, latitude: float, longitude: float) -> SpatialResult: ...

    def get_fire_district(self, latitude: float, longitude: float) -> str: ...


class FireDangerClient(Protocol):
    """Return authoritative current FDR or signal that it is unavailable."""

    def get_fire_danger(self, fire_district: str) -> FireDanger: ...


class WeatherClient(Protocol):
    """Return authoritative current conditions or signal that they are unavailable."""

    def get_weather(self, latitude: float, longitude: float) -> Weather: ...
