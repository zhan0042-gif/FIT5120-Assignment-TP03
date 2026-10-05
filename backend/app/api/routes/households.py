"""Iteration 1 household, plan, location, context, and test endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import Response

from app.core.dependencies import (
    get_address_client,
    get_explanation_client,
    get_fire_danger_client,
    get_household_repository,
    get_road_disruption_client,
    get_routing_client,
    get_guidance_router,
    get_safety_guidance_entries,
    get_travel_route_client,
    get_spatial_provider,
    get_weather_client,
)
from app.core.exceptions import HouseholdNotFound, LocationNotFound
from app.providers.interfaces import (
    AddressClient,
    GuidanceRouter,
    ExplanationClient,
    FireDangerClient,
    RoadDisruptionClient,
    RoutingClient,
    RoadRouteClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.schemas.explanation import RendezvousExplanation
from app.schemas.households import (
    DeviceLocationRequest,
    HistoricalFirePoints,
    HouseholdCreate,
    HouseholdCreated,
    HouseholdLocation,
    HouseholdPlan,
    LocalContext,
    LocationRequest,
    PlanCompletion,
    PreparednessPlanExportRequest,
    PreparationSupport,
)
from app.schemas.rendezvous import RendezvousResult
from app.schemas.safety_guidance import (
    GuidanceAnswer,
    GuidanceEntryDefinition,
    GuidanceQuestion,
    SafetyGuidance,
)
from app.schemas.scenarios import ScenarioTestRequest, ScenarioTestResult
from app.schemas.travel_disruptions import TravelDisruptionResult
from app.schemas.travel_routes import TravelRouteResult
from app.services.context import (
    HistoricalFireMapService,
    LocalContextService,
    LocationService,
    PreparationSupportService,
)
from app.services.explanation import ExplanationService
from app.services.plans import HouseholdPlanService, PlanCompletionService
from app.services.preparedness_pdf import PreparednessPdfService
from app.services.rendezvous import RendezvousSimulationService
from app.services.safety_guidance import SafetyGuidanceService
from app.services.safety_guidance_ask import GuidanceAskService
from app.services.scenarios import BasicScenarioService
from app.services.travel_disruptions import TravelDisruptionService
from app.services.travel_routes import TravelRouteService


router = APIRouter(prefix="/households", tags=["households"])

RepositoryDependency = Annotated[
    HouseholdRepository,
    Depends(get_household_repository),
]

RoutingDependency = Annotated[
    RoutingClient,
    RoadRouteClient,
    Depends(get_routing_client),
]

RoadDisruptionDependency = Annotated[
    RoadDisruptionClient,
    Depends(get_road_disruption_client),
]

ExplanationDependency = Annotated[
    ExplanationClient,
    Depends(get_explanation_client),
]

GuidanceRouterDependency = Annotated[
    GuidanceRouter,
    Depends(get_guidance_router),
]


@router.post(
    "",
    response_model=HouseholdCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_household(
    repository: RepositoryDependency,
    request: HouseholdCreate | None = Body(default=None),
) -> HouseholdCreated:
    """Create the browser-owned household root used by later plan resources."""
    household_id = repository.create_household(
        display_name=request.display_name if request else None
    )

    return HouseholdCreated(
        household_id=household_id
    )


@router.put(
    "/{household_id}/plan",
    response_model=HouseholdPlan,
)
def save_plan(
    household_id: str,
    plan: HouseholdPlan,
    repository: RepositoryDependency,
    address_client: Annotated[
        AddressClient,
        Depends(get_address_client),
    ],
) -> HouseholdPlan:
    """Validate, enrich, and transactionally persist the complete plan aggregate."""
    return HouseholdPlanService(
        repository,
        address_client,
    ).save(
        household_id,
        plan,
    )


@router.get(
    "/{household_id}/plan",
    response_model=HouseholdPlan,
)
def get_plan(
    household_id: str,
    repository: RepositoryDependency,
) -> HouseholdPlan:
    """Return the latest saved aggregate; an absent plan remains a 404 resource."""
    return repository.get_plan(
        household_id
    )


def _preparedness_plan_response(
    household_id: str,
    repository: HouseholdRepository,
    preparedness_advice: str | None = None,
) -> Response:
    plan = repository.get_plan(household_id)

    try:
        location = repository.get_location(
            household_id
        )

        household_address = (
            location.canonical_address
            or location.address
            or ""
        ).strip()

    except LocationNotFound:
        household_address = ""

    content = PreparednessPdfService().generate(
        plan,
        household_address=household_address,
        preparedness_advice=preparedness_advice,
    )

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="firebreak-household-plan.pdf"'
            )
        },
    )


@router.get(
    "/{household_id}/preparedness-plan.pdf",
    response_class=Response,
)
def export_preparedness_plan(
    household_id: str,
    repository: RepositoryDependency,
) -> Response:
    """Download a printable plan without optional in-memory advice."""
    return _preparedness_plan_response(
        household_id,
        repository,
    )


@router.post(
    "/{household_id}/preparedness-plan.pdf",
    response_class=Response,
)
def export_preparedness_plan_with_advice(
    household_id: str,
    request: PreparednessPlanExportRequest,
    repository: RepositoryDependency,
) -> Response:
    """Include bounded advice that the user already requested and saw."""
    return _preparedness_plan_response(
        household_id,
        repository,
        request.preparedness_advice,
    )


@router.get(
    "/{household_id}/completion",
    response_model=PlanCompletion,
)
def get_completion(
    household_id: str,
    repository: RepositoryDependency,
) -> PlanCompletion:
    """Derive completion and immediate checks from the latest saved plan."""

    return PlanCompletionService().evaluate(
        repository.get_plan(
            household_id
        )
    )


@router.put(
    "/{household_id}/location",
    response_model=HouseholdLocation,
)
def save_location(
    household_id: str,
    request: LocationRequest,
    repository: RepositoryDependency,
    address_client: Annotated[
        AddressClient,
        Depends(get_address_client),
    ],
) -> HouseholdLocation:
    """Save entered address text and attempt non-blocking official verification."""

    return LocationService(
        repository,
        address_client,
    ).save(
        household_id,
        request.address,
        request.selected_address,
        request.provider_reference,
    )


@router.get(
    "/{household_id}/location",
    response_model=HouseholdLocation,
)
def get_location(
    household_id: str,
    repository: RepositoryDependency,
) -> HouseholdLocation:
    """Return saved address data independently of local-context availability."""

    return repository.get_location(
        household_id
    )


@router.put(
    "/{household_id}/location/device",
    response_model=HouseholdLocation,
)
def save_device_location(
    household_id: str,
    request: DeviceLocationRequest,
    repository: RepositoryDependency,
    address_client: Annotated[
        AddressClient,
        Depends(get_address_client),
    ],
) -> HouseholdLocation:
    """Save coordinates shared on demand without claiming postal verification."""

    return LocationService(
        repository,
        address_client,
    ).save_device_location(
        household_id,
        request.latitude,
        request.longitude,
    )


def _local_context_service(
    repository: HouseholdRepository,
    spatial_provider: SpatialProvider,
    fire_danger_client: FireDangerClient,
    weather_client: WeatherClient,
) -> LocalContextService:
    return LocalContextService(
        repository,
        spatial_provider,
        fire_danger_client,
        weather_client,
    )


@router.get(
    "/{household_id}/local-context",
    response_model=LocalContext,
)
def get_local_context(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[
        SpatialProvider,
        Depends(get_spatial_provider),
    ],
    fire_danger_client: Annotated[
        FireDangerClient,
        Depends(get_fire_danger_client),
    ],
    weather_client: Annotated[
        WeatherClient,
        Depends(get_weather_client),
    ],
) -> LocalContext:
    """Aggregate cached spatial context with current official BOM information."""

    return _local_context_service(
        repository,
        spatial_provider,
        fire_danger_client,
        weather_client,
    ).get(
        household_id
    )


@router.get(
    "/{household_id}/historical-fire-points",
    response_model=HistoricalFirePoints,
)
def get_historical_fire_points(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[
        SpatialProvider,
        Depends(get_spatial_provider),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=1000),
    ] = 500,
) -> HistoricalFirePoints:
    """Return a bounded, household-scoped Historical Fire map dataset."""

    return HistoricalFireMapService(
        repository,
        spatial_provider,
    ).get(
        household_id,
        limit=limit,
    )


@router.get(
    "/{household_id}/preparation-support",
    response_model=PreparationSupport,
)
def get_preparation_support(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[
        SpatialProvider,
        Depends(get_spatial_provider),
    ],
    fire_danger_client: Annotated[
        FireDangerClient,
        Depends(get_fire_danger_client),
    ],
) -> PreparationSupport:
    """Return rule-based review guidance only when official FDR is usable."""

    plan = repository.get_plan(
        household_id
    )

    completion = PlanCompletionService().evaluate(
        plan
    )

    return PreparationSupportService(
        repository,
        spatial_provider,
        fire_danger_client,
    ).get(
        household_id,
        completion,
    )


@router.get(
    "/{household_id}/safety-guidance",
    response_model=SafetyGuidance,
)
def get_safety_guidance(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[
        SpatialProvider,
        Depends(get_spatial_provider),
    ],
    entries: Annotated[
        list[GuidanceEntryDefinition],
        Depends(get_safety_guidance_entries),
    ],
) -> SafetyGuidance:
    """Return the reviewed CFA question-and-answer entries and the questions to offer."""

    return SafetyGuidanceService(
        repository,
        spatial_provider,
        entries,
    ).get(household_id)


@router.post(
    "/{household_id}/safety-guidance/ask",
    response_model=GuidanceAnswer,
)
def ask_safety_guidance(
    household_id: str,
    body: GuidanceQuestion,
    repository: RepositoryDependency,
    guidance_router: GuidanceRouterDependency,
    entries: Annotated[
        list[GuidanceEntryDefinition],
        Depends(get_safety_guidance_entries),
    ],
) -> GuidanceAnswer:
    """Say which reviewed entries answer a typed question.

    The household id only scopes the route. Nothing about the household is sent to
    the model, and the question is never logged.
    """

    if not repository.household_exists(household_id):
        raise HouseholdNotFound(f"Household '{household_id}' was not found.")

    return GuidanceAskService(guidance_router, entries).ask(body.question)


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

    return BasicScenarioService(
        repository
    ).run_for_household(
        household_id,
        request.scenario_id,
    )


@router.get(
    "/{household_id}/tests/{test_run_id}",
    response_model=ScenarioTestResult,
)
def get_preparedness_test_result(
    household_id: str,
    test_run_id: str,
    repository: RepositoryDependency,
) -> ScenarioTestResult:
    """Retrieve a stored test result scoped to its owning household."""

    return repository.get_test_result(
        household_id,
        test_run_id,
    )


@router.post(
    "/{household_id}/rendezvous-simulation",
    response_model=RendezvousResult,
)
def simulate_rendezvous(
    household_id: str,
    repository: RepositoryDependency,
    routing_client: RoutingDependency,
) -> RendezvousResult:
    """Estimate when every member reaches the primary evacuation destination."""

    return RendezvousSimulationService(
        repository,
        routing_client,
    ).simulate(
        household_id
    )


@router.post(
    "/{household_id}/rendezvous-explanation",
    response_model=RendezvousExplanation,
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

    if not repository.household_exists(
        household_id
    ):
        raise HouseholdNotFound(
            f"Household '{household_id}' was not found."
        )

    return ExplanationService(
        explanation_client
    ).explain(
        result
    )


@router.get(
    "/{household_id}/travel-disruptions",
    response_model=TravelDisruptionResult,
)
def get_travel_disruptions(
    household_id: str,
    repository: RepositoryDependency,
    road_disruption_client: RoadDisruptionDependency,
    radius_km: Annotated[
        float,
        Query(gt=0, le=50),
    ] = 10.0,
) -> TravelDisruptionResult:
    """Return current road disruptions near saved evacuation destinations."""

    return TravelDisruptionService(
        repository,
        road_disruption_client,
    ).get(
        household_id,
        radius_km=radius_km,
    )

@router.get("/{household_id}/travel-routes", response_model=TravelRouteResult)
def get_travel_routes(
    household_id: str,
    repository: RepositoryDependency,
    route_client: Annotated[RoadRouteClient, Depends(get_travel_route_client)],
) -> TravelRouteResult:
    """One road route from home to each verified saved evacuation destination."""
    return TravelRouteService(repository, route_client).get(household_id)
