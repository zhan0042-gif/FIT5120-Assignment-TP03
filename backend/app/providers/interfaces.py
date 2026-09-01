"""Provider protocols keep service logic independent of future integrations."""

from typing import Protocol

from app.schemas.households import (
    FireDanger,
    HouseholdLocation,
    Weather,
)


class SpatialResult(Protocol):
    is_bushfire_prone_area: bool
    fire_district: str
    fire_history_summary: str | None
    vegetation_context: str | None
    terrain_context: str | None


class AddressClient(Protocol):
    def resolve(self, address: str) -> HouseholdLocation: ...

    def suggest(self, query: str, *, limit: int = 5) -> list[str]: ...


class SpatialProvider(Protocol):
    def get_context(self, latitude: float, longitude: float) -> SpatialResult: ...


class FireDangerClient(Protocol):
    def get_fire_danger(self, fire_district: str) -> FireDanger: ...


class WeatherClient(Protocol):
    def get_weather(self, latitude: float, longitude: float) -> Weather: ...
