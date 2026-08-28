"""Iteration 1 household, plan, location, context, and test endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.core.dependencies import (
    get_address_client,
    get_fire_danger_client,
    get_household_repository,
    get_spatial_provider,
    get_weather_client,
)
from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    HouseholdCreate,
    HouseholdCreated,
    HouseholdLocation,
    HouseholdPlan,
    LocalContext,
    LocationRequest,
    PlanCompletion,
    PreparationSupport,
)
from app.schemas.scenarios import ScenarioTestRequest, ScenarioTestResult
from app.services.context import (
    LocalContextService,
    LocationService,
    PreparationSupportService,
)
from app.services.plans import HouseholdPlanService, PlanCompletionService
from app.services.scenarios import BasicScenarioService


router = APIRouter(prefix="/households", tags=["households"])
RepositoryDependency = Annotated[HouseholdRepository, Depends(get_household_repository)]


@router.post("", response_model=HouseholdCreated, status_code=status.HTTP_201_CREATED)
def create_household(
    repository: RepositoryDependency,
    request: HouseholdCreate | None = Body(default=None),
) -> HouseholdCreated:
    household_id = repository.create_household(
        display_name=request.display_name if request else None
    )
    return HouseholdCreated(household_id=household_id)


@router.put("/{household_id}/plan", response_model=HouseholdPlan)
def save_plan(
    household_id: str, plan: HouseholdPlan, repository: RepositoryDependency
) -> HouseholdPlan:
    return HouseholdPlanService(repository).save(household_id, plan)


@router.get("/{household_id}/plan", response_model=HouseholdPlan)
def get_plan(household_id: str, repository: RepositoryDependency) -> HouseholdPlan:
    return repository.get_plan(household_id)


@router.get("/{household_id}/completion", response_model=PlanCompletion)
def get_completion(
    household_id: str, repository: RepositoryDependency
) -> PlanCompletion:
    return PlanCompletionService().evaluate(repository.get_plan(household_id))


@router.put("/{household_id}/location", response_model=HouseholdLocation)
def save_location(
    household_id: str,
    request: LocationRequest,
    repository: RepositoryDependency,
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> HouseholdLocation:
    return LocationService(repository, address_client).save(
        household_id, request.address
    )


def _local_context_service(
    repository: HouseholdRepository,
    spatial_provider: SpatialProvider,
    fire_danger_client: FireDangerClient,
    weather_client: WeatherClient,
) -> LocalContextService:
    return LocalContextService(
        repository, spatial_provider, fire_danger_client, weather_client
    )


@router.get("/{household_id}/local-context", response_model=LocalContext)
def get_local_context(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[SpatialProvider, Depends(get_spatial_provider)],
    fire_danger_client: Annotated[
        FireDangerClient, Depends(get_fire_danger_client)
    ],
    weather_client: Annotated[WeatherClient, Depends(get_weather_client)],
) -> LocalContext:
    return _local_context_service(
        repository, spatial_provider, fire_danger_client, weather_client
    ).get(household_id)


@router.get("/{household_id}/preparation-support", response_model=PreparationSupport)
def get_preparation_support(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[SpatialProvider, Depends(get_spatial_provider)],
    fire_danger_client: Annotated[
        FireDangerClient, Depends(get_fire_danger_client)
    ],
) -> PreparationSupport:
    plan = repository.get_plan(household_id)
    completion = PlanCompletionService().evaluate(plan)
    return PreparationSupportService(
        repository, spatial_provider, fire_danger_client
    ).get(household_id, completion)


@router.post(
    "/{household_id}/tests",
    response_model=ScenarioTestResult,
    status_code=status.HTTP_201_CREATED,
)
def run_preparedness_test(
    household_id: str,
    request: ScenarioTestRequest,
    repository: RepositoryDependency,
) -> ScenarioTestResult:
    return BasicScenarioService(repository).run_for_household(
        household_id, request.scenario_id
    )
