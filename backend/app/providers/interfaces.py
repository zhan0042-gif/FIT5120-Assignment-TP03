"""Provider boundaries keep official-data integrations out of business services."""

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from app.schemas.households import (
    AddressSuggestion,
    FireDanger,
    HouseholdLocation,
    Weather,
)
from app.schemas.live import ActionDecision, LiveSessionResponse
from app.schemas.rendezvous import RendezvousResult
from app.schemas.safety_guidance import GuidanceCatalogueItem
from app.schemas.travel_disruptions import RoadDisruption
from app.schemas.travel_routes import RoadRoute


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
        self,
        address: str,
        *,
        provider_reference: str | None = None,
    ) -> HouseholdLocation: ...

    def suggest(
        self,
        query: str,
        limit: int = 8,
    ) -> list[AddressSuggestion]: ...

    def reverse(
        self,
        latitude: float,
        longitude: float,
        limit: int = 5,
    ) -> list[AddressSuggestion]: ...


class SpatialProvider(Protocol):
    """Resolve static context from verified coordinates."""

    def get_context(
        self,
        latitude: float,
        longitude: float,
    ) -> SpatialResult: ...

    def get_fire_district(
        self,
        latitude: float,
        longitude: float,
    ) -> str: ...

    def get_fire_history_points(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def get_nearest_fire_history_point(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> dict[str, Any] | None: ...


class FireDangerClient(Protocol):
    """Return authoritative current FDR or signal that it is unavailable."""

    def get_fire_danger(
        self,
        fire_district: str,
    ) -> FireDanger: ...


class WeatherClient(Protocol):
    """Return authoritative current conditions or signal that they are unavailable."""

    def get_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> Weather: ...


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


class RoadRouteClient(Protocol):
    """Return one actual driving route, without route-safety analysis."""

    def road_route(self, origin: tuple[float, float], destination: tuple[float, float]) -> RoadRoute: ...


class RoadDisruptionClient(Protocol):
    """Return current official road disruptions near a location."""

    def nearby_disruptions(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> list[RoadDisruption]: ...


class ExplanationClient(Protocol):
    """Turn a computed simulation result into a short plain-language explanation.

    The implementation never calculates: it receives figures that are already
    correct and writes prose about them.
    """

    def explain(
        self,
        result: RendezvousResult,
    ) -> str: ...


class GuidanceRouter(Protocol):
    """Choose which reviewed safety entries answer a typed question.

    The implementation returns entry ids only. Nothing it says is shown to a user:
    the service checks every id against the catalogue and the browser displays the
    reviewed text. It must raise ExternalDataUnavailable when it cannot be reached.
    """

    def route(
        self,
        question: str,
        catalogue: Sequence[GuidanceCatalogueItem],
    ) -> list[str]: ...


class ActionDecisionClient(Protocol):
    """Choose one voice action from the closed list for what a person said.

    The implementation returns an action id and a confidence only. Nothing it says
    is shown or spoken: the browser runs the handler for the id it returns. It must
    raise ExternalDataUnavailable when it cannot be reached.
    """

    def decide(
        self,
        utterance: str,
        page: str,
        last_readout: str,
    ) -> ActionDecision: ...


class LiveSessionClient(Protocol):
    """Create a GPT-Live voice session from a browser's WebRTC offer.

    It must raise ExternalDataUnavailable when the session cannot be created.
    """

    def create(
        self,
        sdp: str,
    ) -> LiveSessionResponse: ...
