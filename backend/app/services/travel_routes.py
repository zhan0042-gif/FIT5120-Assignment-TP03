"""Independent home-to-destination road-route visualisation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable, LocationNotFound, PlanNotFound
from app.providers.interfaces import RoadRouteClient
from app.repositories.households import HouseholdRepository
from app.schemas.households import Destination
from app.schemas.travel_routes import DestinationRoute, RoutePoint, TravelRouteResult


class TravelRouteService:
    def __init__(self, repository: HouseholdRepository, client: RoadRouteClient):
        self.repository = repository
        self.client = client

    def get(self, household_id: str) -> TravelRouteResult:
        checked_at = datetime.now(timezone.utc)
        try:
            home = self.repository.get_location(household_id)
        except LocationNotFound:
            home = None
        if home is None or home.latitude is None or home.longitude is None:
            return TravelRouteResult(status="unavailable", checked_at=checked_at,
                unavailable_reason="Routes cannot be shown because your home location is unavailable.")
        try:
            plan = self.repository.get_plan(household_id)
        except PlanNotFound:
            return TravelRouteResult(status="not_applicable", checked_at=checked_at,
                unavailable_reason="Add and verify a saved evacuation destination to show routes.")
        candidates = [("primary", plan.arrangements.primary_destination)] + [
            ("backup", arrangement.destination) for arrangement in plan.arrangements.backup_arrangements
        ]
        destinations = [(kind, destination) for kind, destination in candidates
            if destination is not None and destination.verification_status == "verified"
            and destination.latitude is not None and destination.longitude is not None]
        if not destinations:
            return TravelRouteResult(status="not_applicable", checked_at=checked_at,
                unavailable_reason="No verified evacuation destinations are available for routes.")
        origin = RoutePoint(latitude=home.latitude, longitude=home.longitude)
        # Bounded parallel requests; map preserves saved primary/backup order.
        with ThreadPoolExecutor(max_workers=min(4, len(destinations))) as executor:
            routes = list(executor.map(lambda item: self._route(origin, *item), destinations))
        available = sum(route.status == "available" for route in routes)
        status = "available" if available == len(routes) else "partial" if available else "unavailable"
        return TravelRouteResult(status=status, checked_at=checked_at, routes=routes,
            unavailable_reason=None if status == "available" else
                "Some routes are unavailable." if status == "partial" else "Road routes are currently unavailable.")

    def _route(self, origin: RoutePoint, kind: str, destination: Destination) -> DestinationRoute:
        target = RoutePoint(latitude=destination.latitude, longitude=destination.longitude)
        metadata = dict(destination_type=kind, destination_id=destination.destination_id,
            destination_name=destination.display_name or destination.canonical_address or destination.address or "Saved destination",
            destination_address=destination.canonical_address or destination.address,
            origin=origin, destination=target)
        try:
            route = self.client.road_route((origin.latitude, origin.longitude), (target.latitude, target.longitude))
        except ExternalDataUnavailable:
            # Provider errors can contain credential-bearing URLs; do not expose them.
            return DestinationRoute(status="unavailable", **metadata,
                unavailable_reason="The road route to this destination is unavailable.")
        return DestinationRoute(status="available", **metadata, **route.model_dump())
