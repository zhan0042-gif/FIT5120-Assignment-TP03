"""Stable mock providers for local development and automated tests."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from app.providers.interfaces import RouteLeg
from app.schemas.rendezvous import RendezvousResult
from app.schemas.households import AddressSuggestion, FireDanger, HouseholdLocation, Weather


@dataclass(frozen=True)
class MockSpatialResult:
    latitude: float
    longitude: float
    is_bushfire_prone_area: bool
    fire_district: str
    vegetation_context: str | None = None
    terrain_context: str | None = None
    fire_history_record_count: int | None = None
    fire_history_latest_year: int | None = None
    fire_history_latest_date: str | None = None
    fire_history_radius_km: float | None = None


class MockAddressClient:
    """Resolve addresses without network access using stable Victoria examples."""

    _KNOWN_ADDRESSES = {
        "warrandyte vic 3113": (-37.74, 145.21),
        "melbourne vic 3000": (-37.8136, 144.9631),
    }

    def resolve(
        self, address: str, *, provider_reference: str | None = None
    ) -> HouseholdLocation:
        standardized = " ".join(address.strip().split())
        coordinates = self._KNOWN_ADDRESSES.get(
            standardized.casefold(), (-37.814, 144.963)
        )
        return HouseholdLocation(
            address=standardized,
            latitude=coordinates[0],
            longitude=coordinates[1],
        )

    def suggest(self, query: str, limit: int = 8) -> list[AddressSuggestion]:
        normalized = " ".join(query.strip().split()).casefold()
        results = []
        for address, (latitude, longitude) in self._KNOWN_ADDRESSES.items():
            if normalized in address:
                results.append(
                    AddressSuggestion(
                        address=address.title(),
                        latitude=latitude,
                        longitude=longitude,
                    )
                )
        return results[:limit]

    def reverse(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> list[AddressSuggestion]:
        nearest = min(
            self._KNOWN_ADDRESSES.items(),
            key=lambda item: (
                (item[1][0] - latitude) ** 2 + (item[1][1] - longitude) ** 2
            ),
        )
        address, coordinates = nearest
        return [
            AddressSuggestion(
                address=address.title(),
                latitude=coordinates[0],
                longitude=coordinates[1],
            )
        ][:limit]


class MockSpatialProvider:
    def get_context(self, latitude: float, longitude: float) -> MockSpatialResult:
        return MockSpatialResult(
            latitude=latitude,
            longitude=longitude,
            is_bushfire_prone_area=True,
            fire_district="Central",
        )

    def get_fire_district(self, latitude: float, longitude: float) -> str:
        return "Central"

    def get_fire_history_points(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
        limit: int,
    ) -> list[dict]:
        return []

    def get_nearest_fire_history_point(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> dict | None:
        return None


class MockFireDangerClient:
    def __init__(self, source_updated_at: datetime | None = None) -> None:
        # Development timestamp only; this is not an official FDR issue time.
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
    def __init__(self, observed_at: datetime | None = None) -> None:
        # Development timestamp only; this is not a live BOM observation.
        self.observed_at = observed_at or datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

    def get_weather(self, latitude: float, longitude: float) -> Weather:
        return Weather(
            temperature_c=28.0,
            relative_humidity=32,
            wind_speed_kmh=30,
            wind_direction="NW",
            observed_at=self.observed_at,
            station_name="Mock Melbourne Station",
        )


def _haversine_metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    earth_radius_metres = 6_371_000.0
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * earth_radius_metres * asin(sqrt(h))


class MockRoutingClient:
    """Straight-line estimates for tests and APP_DATA_MODE=mock.

    Deterministic and offline. Never used in live mode: a straight line is not
    a travel time, and the service must never present one as if it were.
    """

    AVERAGE_SPEED_METRES_PER_SECOND = 11.0  # ~40 km/h urban average

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]:
        legs: list[RouteLeg] = []
        for index, origin in enumerate(origins):
            metres = int(_haversine_metres(origin, destination))
            legs.append(
                RouteLeg(
                    origin_index=index,
                    travel_seconds=int(metres / self.AVERAGE_SPEED_METRES_PER_SECOND),
                    distance_meters=metres,
                    traffic_delay_seconds=0,
                )
            )
        return legs


class MockExplanationClient:
    """A fixed passage for tests and APP_DATA_MODE=mock.

    Deliberately says nothing a real model could get wrong, so a test that
    fails is a test about our code rather than about a sentence.
    """

    def explain(self, result: RendezvousResult) -> str:
        slowest = max(
            result.member_etas, key=lambda eta: eta.travel_seconds, default=None
        )
        if slowest is None:
            return "There is not enough detail in this plan to comment on."
        return (
            f"{slowest.display_name or 'One member'} takes the longest to reach "
            f"{result.destination_name}, so the household is not together until "
            "that journey finishes. Consider whether anyone could start closer."
        )
