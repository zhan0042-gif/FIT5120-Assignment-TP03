"""Provider boundaries keep official-data integrations out of business services."""

from typing import Any, Protocol

from pydantic import BaseModel

from app.schemas.households import (
    AddressSuggestion,
    FireDanger,
    HouseholdLocation,
    Weather,
)


from app.schemas.rendezvous import RendezvousResult


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

    def resolve(
        self, address: str, *, provider_reference: str | None = None
    ) -> HouseholdLocation: ...

    def suggest(self, query: str, limit: int = 8) -> list[AddressSuggestion]: ...

    def reverse(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> list[AddressSuggestion]: ...


class SpatialProvider(Protocol):
    """Resolve static context from verified coordinates."""

    def get_context(self, latitude: float, longitude: float) -> SpatialResult: ...

    def get_fire_district(self, latitude: float, longitude: float) -> str: ...

    def get_fire_history_points(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class FireDangerClient(Protocol):
    """Return authoritative current FDR or signal that it is unavailable."""

    def get_fire_danger(self, fire_district: str) -> FireDanger: ...


class WeatherClient(Protocol):
    """Return authoritative current conditions or signal that they are unavailable."""

    def get_weather(self, latitude: float, longitude: float) -> Weather: ...


class RouteLeg(BaseModel):
    """One origin's travel estimate to the shared destination."""

    origin_index: int
    travel_seconds: int
    distance_meters: int
    traffic_delay_seconds: int = 0


class RoutingClient(Protocol):
    """Estimate travel time from several origins to one destination."""

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]: ...


class ExplanationClient(Protocol):
    """Turn a computed simulation result into a short plain-language explanation.

    The implementation never calculates: it receives figures that are already
    correct and writes prose about them.
    """

    def explain(self, result: RendezvousResult) -> str: ...
