"""Central runtime selection for deterministic mock or official live data."""

from dataclasses import dataclass
from datetime import timedelta
import math
import os

from app.providers.bom import BOMWeatherClient
from app.providers.bom_fire_danger import BOMFireDangerClient
from app.providers.interfaces import (
    ActionDecisionClient,
    AddressClient,
    ExplanationClient,
    FireDangerClient,
    GuidanceRouter,
    LiveSessionClient,
    RoadDisruptionClient,
    RoutingClient,
    RoadRouteClient,
    WeatherClient,
)
from app.providers.mock import (
    MockActionDecisionClient,
    MockAddressClient,
    MockExplanationClient,
    MockFireDangerClient,
    MockGuidanceRouter,
    MockLiveSessionClient,
    MockRoadDisruptionClient,
    MockRoutingClient,
    MockWeatherClient,
)
from app.providers.nvidia_explanation import (
    DisabledExplanationClient,
    NvidiaExplanationClient,
)
from app.providers.nvidia_guidance_router import (
    DisabledGuidanceRouter,
    NvidiaGuidanceRouter,
)
from app.providers.openai_decisions import (
    DisabledActionDecisionClient,
    OpenAIDecisionsClient,
)
from app.providers.openai_live import (
    DisabledLiveSessionClient,
    OpenAILiveSessionClient,
)
from app.providers.road_disruptions import (
    DisabledRoadDisruptionClient,
    VictorianRoadDisruptionClient,
)
from app.providers.tomtom import TomTomAddressClient
from app.providers.tomtom_routing import TomTomRoutingClient
from app.providers.disabled_tomtom import DisabledTomTomAddressClient, DisabledTomTomRoutingClient


@dataclass(frozen=True)
class ExternalProviders:
    address: AddressClient
    routing: RoutingClient
    travel_routes: RoadRouteClient
    road_disruptions: RoadDisruptionClient
    explanation: ExplanationClient
    fire_danger: FireDangerClient
    weather: WeatherClient
    guidance_router: GuidanceRouter
    action_decision: ActionDecisionClient
    live_session: LiveSessionClient


def data_mode() -> str:
    mode = os.getenv("APP_DATA_MODE", "live").strip().lower()

    if mode not in {"mock", "live"}:
        raise RuntimeError(
            "APP_DATA_MODE must be either 'mock' or 'live'."
        )

    return mode


def repository_mode() -> str:
    mode = os.getenv(
        "APP_REPOSITORY_MODE",
        "mysql",
    ).strip().lower()

    if mode not in {"memory", "mysql"}:
        raise RuntimeError(
            "APP_REPOSITORY_MODE must be either 'memory' or 'mysql'."
        )

    return mode


def spatial_mode() -> str:
    mode = os.getenv(
        "APP_SPATIAL_MODE",
        "data",
    ).strip().lower()

    if mode not in {"mock", "data"}:
        raise RuntimeError(
            "APP_SPATIAL_MODE must be either 'mock' or 'data'."
        )

    return mode


def spatial_cache_max_age() -> timedelta:
    raw_hours = os.getenv(
        "APP_SPATIAL_CACHE_MAX_AGE_HOURS",
        "24",
    )

    try:
        hours = float(raw_hours)

    except ValueError as exc:
        raise RuntimeError(
            "APP_SPATIAL_CACHE_MAX_AGE_HOURS must be a positive finite number."
        ) from exc

    if not math.isfinite(hours) or hours <= 0:
        raise RuntimeError(
            "APP_SPATIAL_CACHE_MAX_AGE_HOURS must be a positive finite number."
        )

    return timedelta(
        hours=hours
    )


def _explanation_client(
    api_key: str | None,
) -> ExplanationClient:
    """Explanation is optional; a missing key disables it rather than the app."""

    if api_key and api_key.strip():
        return NvidiaExplanationClient(
            api_key=api_key
        )

    return DisabledExplanationClient()


def _guidance_router(
    api_key: str | None,
) -> GuidanceRouter:
    """Typed questions are optional; a missing key disables them rather than the app."""

    if api_key and api_key.strip():
        return NvidiaGuidanceRouter(
            api_key=api_key
        )

    return DisabledGuidanceRouter()


def _road_disruption_client(
    api_key: str | None,
) -> RoadDisruptionClient:
    """Road disruptions are optional and must not prevent application startup."""

    if api_key and api_key.strip():
        return VictorianRoadDisruptionClient(
            api_key=api_key
        )

    return DisabledRoadDisruptionClient()


def _action_decision_client(
    api_key: str | None,
) -> ActionDecisionClient:
    """Voice is optional; a missing key disables it rather than the app."""

    if api_key and api_key.strip():
        return OpenAIDecisionsClient(
            api_key=api_key
        )

    return DisabledActionDecisionClient()


def _live_session_client(
    api_key: str | None,
) -> LiveSessionClient:
    """Voice is optional; a missing key disables it rather than the app."""

    if api_key and api_key.strip():
        return OpenAILiveSessionClient(
            api_key=api_key
        )

    return DisabledLiveSessionClient()


def build_external_providers(
    mode: str | None = None,
) -> ExternalProviders:
    selected = (
        mode or data_mode()
    ).strip().lower()

    if selected == "mock":
        return ExternalProviders(
            address=MockAddressClient(),
            routing=MockRoutingClient(),
            travel_routes=DisabledTomTomRoutingClient(),
            road_disruptions=MockRoadDisruptionClient(),
            explanation=MockExplanationClient(),
            fire_danger=MockFireDangerClient(),
            weather=MockWeatherClient(),
            guidance_router=MockGuidanceRouter(),
            action_decision=MockActionDecisionClient(),
            live_session=MockLiveSessionClient(),
        )

    if selected == "live":
        api_key = os.getenv("TOMTOM_API_KEY")
        configured = bool(api_key and api_key.strip())
        routing = TomTomRoutingClient(api_key=api_key) if configured else DisabledTomTomRoutingClient()
        return ExternalProviders(
            address=TomTomAddressClient(api_key=api_key) if configured else DisabledTomTomAddressClient(),
            routing=routing,
            travel_routes=routing,
            road_disruptions=_road_disruption_client(
                os.getenv(
                    "VIC_ROAD_DISRUPTIONS_API_KEY"
                )
            ),
            explanation=_explanation_client(
                os.getenv(
                    "AI_API_KEY"
                )
            ),
            fire_danger=BOMFireDangerClient(),
            weather=BOMWeatherClient(),
            guidance_router=_guidance_router(
                os.getenv(
                    "AI_API_KEY"
                )
            ),
            action_decision=_action_decision_client(
                os.getenv(
                    "OPENAI_API_KEY"
                )
            ),
            live_session=_live_session_client(
                os.getenv(
                    "OPENAI_API_KEY"
                )
            ),
        )

    raise RuntimeError(
        "Provider mode must be either 'mock' or 'live'."
    )
