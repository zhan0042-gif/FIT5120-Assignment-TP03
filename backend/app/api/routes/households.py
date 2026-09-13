"""Iteration 1 household, plan, location, context, and test endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from app.core.exceptions import HouseholdNotFound

from app.core.dependencies import (
    get_explanation_client,
    get_routing_client,
    get_address_client,
    get_fire_danger_client,
    get_household_repository,
    get_spatial_provider,
    get_weather_client,
)
from app.providers.interfaces import (
    ExplanationClient,
    RoutingClient,
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    DeviceLocationRequest,
    HouseholdCreate,
    HouseholdCreated,
    HouseholdLocation,
    HouseholdPlan,
    HistoricalFirePoints,
    LocalContext,
    LocationRequest,
    PlanCompletion,
    PreparationSupport,
)
from app.schemas.explanation import RendezvousExplanation
from app.schemas.rendezvous import RendezvousResult
from app.schemas.scenarios import ScenarioTestRequest, ScenarioTestResult
from app.services.context import (
    HistoricalFireMapService,
    LocalContextService,
    LocationService,
    PreparationSupportService,
)
from app.services.plans import HouseholdPlanService, PlanCompletionService
from app.services.explanation import ExplanationService
from app.services.rendezvous import RendezvousSimulationService
from app.services.scenarios import BasicScenarioService


router = APIRouter(prefix="/households", tags=["households"])
RepositoryDependency = Annotated[HouseholdRepository, Depends(get_household_repository)]
RoutingDependency = Annotated[RoutingClient, Depends(get_routing_client)]
ExplanationDependency = Annotated[ExplanationClient, Depends(get_explanation_client)]


@router.post("", response_model=HouseholdCreated, status_code=status.HTTP_201_CREATED)
def create_household(
    repository: RepositoryDependency,
    request: HouseholdCreate | None = Body(default=None),
) -> HouseholdCreated:
    """Create the browser-owned household root used by later plan resources."""
    household_id = repository.create_household(
        display_name=request.display_name if request else None
    )
    return HouseholdCreated(household_id=household_id)


@router.put("/{household_id}/plan", response_model=HouseholdPlan)
def save_plan(
    household_id: str,
    plan: HouseholdPlan,
    repository: RepositoryDependency,
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> HouseholdPlan:
    """Validate, enrich, and transactionally persist the complete plan aggregate."""
    return HouseholdPlanService(repository, address_client).save(household_id, plan)


@router.get("/{household_id}/plan", response_model=HouseholdPlan)
def get_plan(household_id: str, repository: RepositoryDependency) -> HouseholdPlan:
    """Return the latest saved aggregate; an absent plan remains a 404 resource."""
    return repository.get_plan(household_id)


@router.get("/{household_id}/completion", response_model=PlanCompletion)
def get_completion(
    household_id: str, repository: RepositoryDependency
) -> PlanCompletion:
    """Derive completion and immediate checks from the latest saved plan."""
    return PlanCompletionService().evaluate(repository.get_plan(household_id))


@router.put("/{household_id}/location", response_model=HouseholdLocation)
def save_location(
    household_id: str,
    request: LocationRequest,
    repository: RepositoryDependency,
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> HouseholdLocation:
    """Save entered address text and attempt non-blocking official verification."""
    return LocationService(repository, address_client).save(
        household_id,
        request.address,
        request.selected_address,
        request.provider_reference,
    )


@router.get("/{household_id}/location", response_model=HouseholdLocation)
def get_location(
    household_id: str, repository: RepositoryDependency
) -> HouseholdLocation:
    """Return saved address data independently of local-context availability."""
    return repository.get_location(household_id)


@router.put("/{household_id}/location/device", response_model=HouseholdLocation)
def save_device_location(
    household_id: str,
    request: DeviceLocationRequest,
    repository: RepositoryDependency,
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> HouseholdLocation:
    """Save coordinates shared on demand without claiming postal verification."""
    return LocationService(repository, address_client).save_device_location(
        household_id, request.latitude, request.longitude
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
    """Aggregate cached spatial context with current official BOM information."""
    return _local_context_service(
        repository, spatial_provider, fire_danger_client, weather_client
    ).get(household_id)


@router.get(
    "/{household_id}/historical-fire-points",
    response_model=HistoricalFirePoints,
)
def get_historical_fire_points(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[SpatialProvider, Depends(get_spatial_provider)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> HistoricalFirePoints:
    """Return a bounded, household-scoped Historical Fire map dataset."""
    return HistoricalFireMapService(repository, spatial_provider).get(
        household_id, limit=limit
    )


@router.get("/{household_id}/preparation-support", response_model=PreparationSupport)
def get_preparation_support(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[SpatialProvider, Depends(get_spatial_provider)],
    fire_danger_client: Annotated[
        FireDangerClient, Depends(get_fire_danger_client)
    ],
) -> PreparationSupport:
    """Return rule-based review guidance only when official FDR is usable."""
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
    """Run a deterministic scenario against the latest saved plan and store it."""
    return BasicScenarioService(repository).run_for_household(
        household_id, request.scenario_id
    )


@router.get("/{household_id}/tests/{test_run_id}", response_model=ScenarioTestResult)
def get_preparedness_test_result(
    household_id: str,
    test_run_id: str,
    repository: RepositoryDependency,
) -> ScenarioTestResult:
    """Retrieve a stored test result scoped to its owning household."""
    return repository.get_test_result(household_id, test_run_id)


@router.post(
    "/{household_id}/rendezvous-simulation", response_model=RendezvousResult
)
def simulate_rendezvous(
    household_id: str,
    repository: RepositoryDependency,
    routing_client: RoutingDependency,
) -> RendezvousResult:
    """Estimate when every member reaches the primary evacuation destination."""
    return RendezvousSimulationService(repository, routing_client).simulate(household_id)


@router.post(
    "/{household_id}/rendezvous-explanation", response_model=RendezvousExplanation
)
def explain_rendezvous(
    household_id: str,
    result: RendezvousResult,
    repository: RepositoryDependency,
    explanation_client: ExplanationDependency,
) -> RendezvousExplanation:
    """Explain a simulation result the browser is already displaying.

    The result arrives in the request rather than being recomputed, so the prose
    can never describe different figures than the ones on screen.
    """
    if not repository.household_exists(household_id):
        raise HouseholdNotFound(f"Household '{household_id}' was not found.")
    return ExplanationService(explanation_client).explain(result)
