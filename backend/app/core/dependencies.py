"""Central dependency wiring for the Iteration 1 runtime."""

from app.core.config import (
    build_external_providers,
    repository_mode,
    spatial_mode,
    voice_log_settings,
)
from app.core.database import create_database_engine
from app.providers.data_spatial import DataSpatialProvider
from app.providers.interfaces import (
    AddressClient,
    ExplanationClient,
    FireDangerClient,
    JudgementClient,
    RoutingClient,
    SpatialProvider,
    WeatherClient,
)
from app.providers.mock import MockSpatialProvider
from app.repositories.households import HouseholdRepository, InMemoryHouseholdRepository
from app.repositories.mysql import MySQLHouseholdRepository
from app.services.voice_log import VoiceTurnLogger


_repository: HouseholdRepository = (
    InMemoryHouseholdRepository()
    if repository_mode() == "memory"
    else MySQLHouseholdRepository(create_database_engine())
)
_external_providers = build_external_providers()
_spatial_provider: SpatialProvider = (
    MockSpatialProvider() if spatial_mode() == "mock" else DataSpatialProvider()
)
_voice_log_path, _voice_log_content = voice_log_settings()
_voice_turn_logger = VoiceTurnLogger(_voice_log_path, include_content=_voice_log_content)


def get_household_repository() -> HouseholdRepository:
    return _repository


def get_address_client() -> AddressClient:
    return _external_providers.address


def get_explanation_client() -> ExplanationClient:
    return _external_providers.explanation


def get_routing_client() -> RoutingClient:
    return _external_providers.routing


def get_spatial_provider() -> SpatialProvider:
    return _spatial_provider


def get_fire_danger_client() -> FireDangerClient:
    return _external_providers.fire_danger


def get_weather_client() -> WeatherClient:
    return _external_providers.weather


def get_judgement_client() -> JudgementClient:
    return _external_providers.judgement


def get_voice_turn_logger() -> VoiceTurnLogger:
    return _voice_turn_logger
