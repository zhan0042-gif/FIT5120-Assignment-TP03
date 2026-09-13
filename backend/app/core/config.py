"""Central runtime selection for deterministic mock or official live data."""

from dataclasses import dataclass
from datetime import timedelta
import math
import os

from app.providers.bom import BOMWeatherClient
from app.providers.bom_fire_danger import BOMFireDangerClient
from app.providers.interfaces import (
    AddressClient,
    ExplanationClient,
    FireDangerClient,
    RoutingClient,
    WeatherClient,
)
from app.providers.mock import (
    MockAddressClient,
    MockExplanationClient,
    MockFireDangerClient,
    MockRoutingClient,
    MockWeatherClient,
)
from app.providers.tomtom import TomTomAddressClient
from app.providers.nvidia_explanation import NvidiaExplanationClient
from app.providers.tomtom_routing import TomTomRoutingClient


@dataclass(frozen=True)
class ExternalProviders:
    address: AddressClient
    routing: RoutingClient
    explanation: ExplanationClient
    fire_danger: FireDangerClient
    weather: WeatherClient


def data_mode() -> str:
    mode = os.getenv("APP_DATA_MODE", "live").strip().lower()
    if mode not in {"mock", "live"}:
        raise RuntimeError("APP_DATA_MODE must be either 'mock' or 'live'.")
    return mode


def repository_mode() -> str:
    mode = os.getenv("APP_REPOSITORY_MODE", "mysql").strip().lower()
    if mode not in {"memory", "mysql"}:
        raise RuntimeError("APP_REPOSITORY_MODE must be either 'memory' or 'mysql'.")
    return mode


def spatial_mode() -> str:
    mode = os.getenv("APP_SPATIAL_MODE", "data").strip().lower()
    if mode not in {"mock", "data"}:
        raise RuntimeError("APP_SPATIAL_MODE must be either 'mock' or 'data'.")
    return mode


def spatial_cache_max_age() -> timedelta:
    raw_hours = os.getenv("APP_SPATIAL_CACHE_MAX_AGE_HOURS", "24")
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
    return timedelta(hours=hours)


def build_external_providers(mode: str | None = None) -> ExternalProviders:
    selected = (mode or data_mode()).strip().lower()
    if selected == "mock":
        return ExternalProviders(
            address=MockAddressClient(),
            routing=MockRoutingClient(),
            explanation=MockExplanationClient(),
            fire_danger=MockFireDangerClient(),
            weather=MockWeatherClient(),
        )
    if selected == "live":
        return ExternalProviders(
            address=TomTomAddressClient(api_key=os.getenv("TOMTOM_API_KEY")),
            routing=TomTomRoutingClient(api_key=os.getenv("TOMTOM_API_KEY")),
            explanation=NvidiaExplanationClient(api_key=os.getenv("AI_API_KEY")),
            fire_danger=BOMFireDangerClient(),
            weather=BOMWeatherClient(),
        )
    raise RuntimeError("Provider mode must be either 'mock' or 'live'.")
