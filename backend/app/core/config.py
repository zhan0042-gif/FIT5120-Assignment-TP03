"""Central runtime selection for deterministic mock or official live data."""

from dataclasses import dataclass
import os

from app.providers.bom import BOMWeatherClient
from app.providers.cfa import CFAFireDangerClient
from app.providers.interfaces import AddressClient, FireDangerClient, WeatherClient
from app.providers.mock import MockAddressClient, MockFireDangerClient, MockWeatherClient
from app.providers.vicmap import VicmapAddressClient


@dataclass(frozen=True)
class ExternalProviders:
    address: AddressClient
    fire_danger: FireDangerClient
    weather: WeatherClient


def data_mode() -> str:
    mode = os.getenv("APP_DATA_MODE", "mock").strip().lower()
    if mode not in {"mock", "live"}:
        raise RuntimeError("APP_DATA_MODE must be either 'mock' or 'live'.")
    return mode


def build_external_providers(mode: str | None = None) -> ExternalProviders:
    selected = (mode or data_mode()).strip().lower()
    if selected == "mock":
        return ExternalProviders(
            address=MockAddressClient(),
            fire_danger=MockFireDangerClient(),
            weather=MockWeatherClient(),
        )
    if selected == "live":
        return ExternalProviders(
            address=VicmapAddressClient(),
            fire_danger=CFAFireDangerClient(),
            weather=BOMWeatherClient(),
        )
    raise RuntimeError("Provider mode must be either 'mock' or 'live'.")
