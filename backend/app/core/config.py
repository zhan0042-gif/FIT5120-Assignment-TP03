"""Central runtime selection for deterministic mock or official live data."""

from dataclasses import dataclass
from datetime import timedelta
import math
import os
from pathlib import Path

from app.providers.bom import BOMWeatherClient
from app.providers.bom_fire_danger import BOMFireDangerClient
from app.providers.interfaces import (
    AddressClient,
    ExplanationClient,
    FireDangerClient,
    JudgementClient,
    RoutingClient,
    WeatherClient,
)
from app.providers.mock import (
    MockAddressClient,
    MockExplanationClient,
    MockFireDangerClient,
    MockJudgementClient,
    MockRoutingClient,
    MockWeatherClient,
)
from app.providers.tomtom import TomTomAddressClient
from app.providers.nvidia_explanation import (
    DisabledExplanationClient,
    NvidiaExplanationClient,
)
from app.providers.jev_judgement import DisabledJudgementClient
from app.providers.tomtom_routing import TomTomRoutingClient


@dataclass(frozen=True)
class ExternalProviders:
    address: AddressClient
    routing: RoutingClient
    explanation: ExplanationClient
    fire_danger: FireDangerClient
    weather: WeatherClient
    judgement: JudgementClient


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


def voice_mode() -> str:
    """Which judge answers voice commands in live data mode.

    Mock data mode always uses the mock judge. The live JEV client adds a third
    value once it exists.
    """
    mode = os.getenv("APP_VOICE_MODE", "off").strip().lower()
    if mode not in {"off", "mock"}:
        raise RuntimeError("APP_VOICE_MODE must be either 'off' or 'mock'.")
    return mode


def voice_log_settings() -> tuple[Path, bool]:
    """Where voice turns are logged, and whether transcripts and values are kept."""
    path = Path(os.getenv("VOICE_LOG_PATH", "logs/voice-turns.jsonl"))
    include_content = os.getenv("VOICE_LOG_CONTENT", "false").strip().lower() in {
        "1", "true", "yes",
    }
    return path, include_content


def _explanation_client(api_key: str | None) -> ExplanationClient:
    """Explanation is optional; a missing key disables it rather than the app."""
    if api_key and api_key.strip():
        return NvidiaExplanationClient(api_key=api_key)
    return DisabledExplanationClient()


def _judgement_client(mode: str) -> JudgementClient:
    """Voice control is optional; switched off, it refuses rather than stopping the app."""
    if mode == "mock":
        return MockJudgementClient()
    return DisabledJudgementClient()


def build_external_providers(mode: str | None = None) -> ExternalProviders:
    selected = (mode or data_mode()).strip().lower()
    if selected == "mock":
        return ExternalProviders(
            address=MockAddressClient(),
            routing=MockRoutingClient(),
            explanation=MockExplanationClient(),
            fire_danger=MockFireDangerClient(),
            weather=MockWeatherClient(),
            judgement=MockJudgementClient(),
        )
    if selected == "live":
        return ExternalProviders(
            address=TomTomAddressClient(api_key=os.getenv("TOMTOM_API_KEY")),
            routing=TomTomRoutingClient(api_key=os.getenv("TOMTOM_API_KEY")),
            explanation=_explanation_client(os.getenv("AI_API_KEY")),
            fire_danger=BOMFireDangerClient(),
            weather=BOMWeatherClient(),
            judgement=_judgement_client(voice_mode()),
        )
    raise RuntimeError("Provider mode must be either 'mock' or 'live'.")
