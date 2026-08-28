"""Central dependency wiring for the Iteration 1 runtime."""

from app.core.config import build_external_providers
from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.providers.mock import MockSpatialProvider
from app.repositories.households import HouseholdRepository, InMemoryHouseholdRepository


_repository = InMemoryHouseholdRepository()
_external_providers = build_external_providers()
_spatial_provider = MockSpatialProvider()


def get_household_repository() -> HouseholdRepository:
    return _repository


def get_address_client() -> AddressClient:
    return _external_providers.address


def get_spatial_provider() -> SpatialProvider:
    return _spatial_provider


def get_fire_danger_client() -> FireDangerClient:
    return _external_providers.fire_danger


def get_weather_client() -> WeatherClient:
    return _external_providers.weather
