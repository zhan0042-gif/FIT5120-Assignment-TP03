"""Live external-provider wiring for the application runtime."""

from dataclasses import dataclass

from app.providers.bom import BOMWeatherClient
from app.providers.bom_fire_danger import BOMFireDangerClient
from app.providers.interfaces import AddressClient, FireDangerClient, WeatherClient
from app.providers.vicmap import VicmapAddressClient


@dataclass(frozen=True)
class ExternalProviders:
    address: AddressClient
    fire_danger: FireDangerClient
    weather: WeatherClient


def build_external_providers() -> ExternalProviders:
    """Build the official providers used by every non-test runtime."""

    return ExternalProviders(
        address=VicmapAddressClient(),
        fire_danger=BOMFireDangerClient(),
        weather=BOMWeatherClient(),
    )
