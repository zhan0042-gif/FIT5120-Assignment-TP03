"""Central dependency wiring for the Iteration 1 runtime."""

from app.core.config import (
    build_external_providers,
    repository_mode,
    spatial_mode,
)
from app.core.database import create_database_engine
from app.providers.data_spatial import DataSpatialProvider
from app.providers.interfaces import (
    AddressClient,
    ExplanationClient,
    FireDangerClient,
    GuidanceRouter,
    RoutingClient,
    RoadRouteClient,
    SpatialProvider,
    WeatherClient,
    RoadDisruptionClient,
)
from app.providers.mock import MockSpatialProvider
from app.repositories.households import HouseholdRepository, InMemoryHouseholdRepository
from app.repositories.mysql import MySQLHouseholdRepository
from app.schemas.safety_guidance import GuidanceEntryDefinition
from app.services.rate_limit import AskRateLimit
from app.services.safety_guidance import DEFAULT_ENTRIES


_repository: HouseholdRepository = (
    InMemoryHouseholdRepository()
    if repository_mode() == "memory"
    else MySQLHouseholdRepository(create_database_engine())
)
_external_providers = build_external_providers()
_spatial_provider: SpatialProvider = (
    MockSpatialProvider() if spatial_mode() == "mock" else DataSpatialProvider()
)


def get_household_repository() -> HouseholdRepository:
    return _repository


def get_address_client() -> AddressClient:
    return _external_providers.address


def get_explanation_client() -> ExplanationClient:
    return _external_providers.explanation


def get_routing_client() -> RoutingClient:
    return _external_providers.routing

def get_road_disruption_client() -> RoadDisruptionClient:
    return _external_providers.road_disruptions


def get_spatial_provider() -> SpatialProvider:
    return _spatial_provider


def get_fire_danger_client() -> FireDangerClient:
    return _external_providers.fire_danger


def get_weather_client() -> WeatherClient:
    return _external_providers.weather




def get_travel_route_client() -> RoadRouteClient:
    return _external_providers.travel_routes


def get_safety_guidance_entries() -> list[GuidanceEntryDefinition]:
    return DEFAULT_ENTRIES


def get_guidance_router() -> GuidanceRouter:
    return _external_providers.guidance_router


_guidance_rate_limit = AskRateLimit()


def get_guidance_rate_limit() -> AskRateLimit:
    return _guidance_rate_limit
