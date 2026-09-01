"""Central dependency wiring for the Iteration 1 runtime."""

from app.core.config import build_external_providers
from app.core.database import create_database_engine
from app.providers.data_spatial import DataSpatialProvider
from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.repositories.mysql import MySQLHouseholdRepository


_repository: HouseholdRepository = MySQLHouseholdRepository(create_database_engine())
_external_providers = build_external_providers()
_spatial_provider: SpatialProvider = DataSpatialProvider()


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
