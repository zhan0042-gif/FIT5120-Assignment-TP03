"""Stable mock providers for local development and automated tests."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from app.providers.interfaces import RouteLeg
from app.schemas.travel_disruptions import RoadDisruption
from app.schemas.rendezvous import RendezvousResult
from app.schemas.safety_guidance import GuidanceCatalogueItem
from app.schemas.households import (
    AddressSuggestion,
    FireDanger,
    HouseholdLocation,
    Weather,
)
from app.schemas.live import ActionDecision, LiveSessionRef, LiveSessionResponse, LiveTransport
from app.services.voice_actions import NONE_ACTION, normalise


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


class MockRoadDisruptionClient:
    """Stable offline road-disruption data for development and tests."""

    def nearby_disruptions(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> list[RoadDisruption]:
        if radius_km <= 0:
            return []

        return [
            RoadDisruption(
                disruption_id="mock-disruption-1",
                event_type="Hazard",
                event_subtype="Road Damage",
                road_name="Mock Road",
                description="Example reported road disruption.",
                impact="Traffic affected",
                status="Active",
                latitude=latitude + 0.01,
                longitude=longitude + 0.01,
                distance_km=1.4,
            )
        ]


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


_STOP_WORDS = frozenset(
    "the and for you are can how what should when why who does did not with that this "
    "have has get our your my its any all out into from about which there their would "
    "could was were will".split()
)


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9']+", text.lower())
        if len(word) >= 3 and word not in _STOP_WORDS
    }


class MockGuidanceRouter:
    """Deterministic word-overlap matching for tests and APP_DATA_MODE=mock.

    A question matches an entry when it shares at least two content words with the
    entry's question and phrasings. It exists so tests exercise our code rather
    than a hosted model, and is not meant to be good at the job.
    """

    def route(self, question: str, catalogue: Sequence[GuidanceCatalogueItem]) -> list[str]:
        words = _content_words(question)
        scored: list[tuple[int, str]] = []
        for item in catalogue:
            text = " ".join([item.question, *item.asked_as])
            score = len(words & _content_words(text))
            if score >= 2:
                scored.append((score, item.id))
        scored.sort(key=lambda pair: -pair[0])  # stable: catalogue order breaks ties
        return [entry_id for _, entry_id in scored[:2]]



class MockActionDecisionClient:
    """Deterministic keyword matching for tests and APP_DATA_MODE=mock.

    The first keyword found in the request wins, so order matters. It exists so tests
    exercise our code rather than a hosted model, and is not meant to be good.
    """

    _KEYWORDS: tuple[tuple[str, str], ...] = (
        ("history", "show_fire_history"),
        ("weather", "read_weather"),
        ("danger", "read_fire_danger"),
        ("complete", "read_plan_completion"),
        ("disruption", "check_travel_disruptions"),
        ("map", "open_fire_map"),
        ("overview", "open_overview"),
        ("travel readiness", "open_travel_readiness"),
        ("test my plan", "open_scenarios"),
        ("my plan", "open_plan"),
        ("again", "repeat_last"),
        ("back", "go_back"),
        ("leave", "ask_safety_question"),
        ("pack", "ask_safety_question"),
        ("kit", "ask_safety_question"),
        ("dog", "ask_safety_question"),
        ("cat", "ask_safety_question"),
        ("pet", "ask_safety_question"),
        ("stay", "ask_safety_question"),
    )

    _FEELINGS: tuple[tuple[str, str], ...] = (
        ("hurry", "urgent"),
        ("right now", "urgent"),
        ("quick", "urgent"),
        ("scared", "worried"),
        ("worried", "worried"),
        ("afraid", "worried"),
        ("nervous", "worried"),
        ("not working", "frustrated"),
        ("ugh", "frustrated"),
        ("annoying", "frustrated"),
        ("haha", "playful"),
        ("lol", "playful"),
        ("funny", "playful"),
    )

    def decide(self, utterance: str, page: str, last_readout: str) -> ActionDecision:
        text = utterance.lower()
        emotion = next((feeling for word, feeling in self._FEELINGS if word in text), "calm")
        for keyword, action in self._KEYWORDS:
            if keyword in text:
                return normalise(action, 0.9).model_copy(update={"emotion": emotion})
        return normalise(NONE_ACTION, 0.0).model_copy(update={"emotion": emotion})


class MockLiveSessionClient:
    """Returns a fixed fake answer so tests and APP_DATA_MODE=mock never reach OpenAI."""

    def create(self, sdp: str) -> LiveSessionResponse:
        return LiveSessionResponse(
            session=LiveSessionRef(id="live_mock"),
            transport=LiveTransport(sdp="v=0\r\no=mock-answer\r\n"),
        )
