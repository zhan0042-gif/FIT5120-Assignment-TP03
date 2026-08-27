"""Application dependency wiring for the in-memory Iteration 1 runtime."""

from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.providers.mock import (
    MockAddressClient,
    MockFireDangerClient,
    MockSpatialProvider,
    MockWeatherClient,
)
from app.repositories.households import HouseholdRepository, InMemoryHouseholdRepository


_repository = InMemoryHouseholdRepository()
_address_client = MockAddressClient()
_spatial_provider = MockSpatialProvider()
_fire_danger_client = MockFireDangerClient()
_weather_client = MockWeatherClient()


def get_household_repository() -> HouseholdRepository:
    return _repository


def get_address_client() -> AddressClient:
    return _address_client


def get_spatial_provider() -> SpatialProvider:
    return _spatial_provider


def get_fire_danger_client() -> FireDangerClient:
    return _fire_danger_client


def get_weather_client() -> WeatherClient:
    return _weather_client

