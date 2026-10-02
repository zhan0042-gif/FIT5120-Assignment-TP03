import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_household_repository, get_travel_route_client, get_road_disruption_client
from app.core.config import build_external_providers
from app.core.exceptions import ExternalDataUnavailable
from app.providers.mock import MockRoadDisruptionClient
from app.providers.tomtom_routing import TomTomRoutingClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import Arrangements, BackupArrangement, Destination, HouseholdLocation, HouseholdPlan
from app.schemas.travel_routes import RoadRoute, RoutePoint
from app.services.travel_routes import TravelRouteService


HOME = (-37.8, 145.0)
TARGET = (-37.9, 145.1)
POINTS = [dict(latitude=-37.8, longitude=145.0), dict(latitude=-37.82, longitude=145.07), dict(latitude=-37.9, longitude=145.1)]
ROUTE = dict(legs=[dict(points=POINTS)], summary=dict(lengthInMeters=15000, travelTimeInSeconds=900))


def destination(index, *, verified=True):
    return Destination(destination_id=f"d{index}", display_name=f"Destination {index}", address=f"Address {index}",
        latitude=-37.9-index * .01, longitude=145.1, verification_status="verified" if verified else "unverified")


def repository(*, home=True, primary=True, backups=2):
    repo = InMemoryHouseholdRepository()
    household_id = repo.create_household()
    if home:
        repo.save_location(household_id, HouseholdLocation(address="Home", latitude=HOME[0], longitude=HOME[1], verification_status="verified"))
    repo.save_plan(household_id, HouseholdPlan(arrangements=Arrangements(
        primary_destination=destination(0) if primary else None,
        backup_arrangements=[BackupArrangement(destination=destination(i+1)) for i in range(backups)])))
    return repo, household_id


class Routes:
    def __init__(self, fail=()):
        self.fail = fail
        self.calls = []

    def road_route(self, origin, target):
        self.calls.append((origin, target))
        if target[0] in self.fail:
            raise ExternalDataUnavailable("secret-bearing provider URL must not escape")
        return RoadRoute(geometry=[RoutePoint(latitude=origin[0], longitude=origin[1]),
            RoutePoint(latitude=origin[0], longitude=target[1]), RoutePoint(latitude=target[0], longitude=target[1])],
            distance_m=15000, travel_time_seconds=900)


def test_primary_and_every_verified_backup_return_ordered_road_geometry():
    repo, household_id = repository(backups=3)
    client = Routes()
    result = TravelRouteService(repo, client).get(household_id)
    assert result.status == "available"
    assert [route.destination_type for route in result.routes] == ["primary", "backup", "backup", "backup"]
    assert [route.destination_id for route in result.routes] == ["d0", "d1", "d2", "d3"]
    assert len(client.calls) == 4
    for route in result.routes:
        assert route.origin.latitude == HOME[0]
        assert len(route.geometry) == 3
        assert route.destination_name and route.destination_address
        assert route.distance_m == 15000 and route.travel_time_seconds == 900


def test_backup_only_plan_is_supported():
    repo, household_id = repository(primary=False, backups=2)
    result = TravelRouteService(repo, Routes()).get(household_id)
    assert [route.destination_type for route in result.routes] == ["backup", "backup"]


def test_unverified_primary_or_backup_only_skips_that_destination():
    repo, household_id = repository()
    plan = repo.get_plan(household_id)
    plan.arrangements.primary_destination.verification_status = "unverified"
    plan.arrangements.backup_arrangements[0].destination.verification_status = "unverified"
    repo.save_plan(household_id, plan)
    result = TravelRouteService(repo, Routes()).get(household_id)
    assert [route.destination_id for route in result.routes] == ["d2"]


@pytest.mark.parametrize("home", [False, True])
def test_missing_home_coordinates_do_not_call_provider(home):
    repo, household_id = repository(home=home)
    if home:
        repo.save_location(household_id, HouseholdLocation(address="Unverified home"))
    client = Routes()
    result = TravelRouteService(repo, client).get(household_id)
    assert result.status == "unavailable" and result.routes == []
    assert "home location is unavailable" in result.unavailable_reason
    assert client.calls == []


def test_no_verified_destinations_or_missing_plan_is_not_applicable():
    repo, household_id = repository(primary=False, backups=0)
    assert TravelRouteService(repo, Routes()).get(household_id).status == "not_applicable"
    empty_id = repo.create_household()
    repo.save_location(empty_id, HouseholdLocation(address="Home", latitude=HOME[0], longitude=HOME[1]))
    assert TravelRouteService(repo, Routes()).get(empty_id).status == "not_applicable"


def test_one_route_failure_preserves_successful_primary_and_backups():
    repo, household_id = repository()
    result = TravelRouteService(repo, Routes(fail=(-37.91,))).get(household_id)
    assert result.status == "partial"
    assert [route.status for route in result.routes] == ["available", "unavailable", "available"]
    assert result.routes[1].geometry == []
    assert "secret" not in result.model_dump_json()


def test_all_route_failures_preserve_destination_metadata():
    repo, household_id = repository()
    result = TravelRouteService(repo, Routes(fail=(-37.9, -37.91, -37.92))).get(household_id)
    assert result.status == "unavailable"
    assert len(result.routes) == 3
    assert all(not route.geometry for route in result.routes)


def tomtom(handler):
    return TomTomRoutingClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_tomtom_requests_one_fastest_car_polyline_and_selects_first_route():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"routes": [ROUTE, dict(legs=[dict(points=[])])]})
    route = tomtom(handler).road_route(HOME, TARGET)
    assert [point.model_dump() for point in route.geometry] == POINTS
    assert route.distance_m == 15000 and route.travel_time_seconds == 900
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/routing/1/calculateRoute/-37.8,145.0:-37.9,145.1/json"
    assert request.url.params["maxAlternatives"] == "0"
    assert request.url.params["routeType"] == "fastest"
    assert request.url.params["travelMode"] == "car"
    assert request.url.params["routeRepresentation"] == "polyline"
    assert request.extensions["timeout"]["read"] == 8.0


@pytest.mark.parametrize("payload", [None, {}, {"routes": []}, {"routes": [{"legs": []}]},
    {"routes": [{"legs": [{"points": POINTS[:1]}]}]},
    {"routes": [{"legs": [{"points": [POINTS[0], {"latitude": 999, "longitude": 145}]}]}]},
    {"routes": [{"legs": [{"points": POINTS}], "summary": None}]},
    {"routes": [{"legs": [{"points": POINTS}], "summary": {"lengthInMeters": -1}}]}])
def test_malformed_tomtom_geometry_is_unavailable_without_fake_line(payload):
    with pytest.raises(ExternalDataUnavailable):
        tomtom(lambda request: httpx.Response(200, json=payload)).road_route(HOME, TARGET)


def test_transport_failures_do_not_expose_provider_url():
    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)
    for handler in [timeout, lambda request: httpx.Response(503, json={})]:
        with pytest.raises(ExternalDataUnavailable, match="temporarily unavailable"):
            tomtom(handler).road_route(HOME, TARGET)


def test_endpoint_uses_saved_coordinates_and_preserves_independent_disruptions():
    repo, household_id = repository()
    app.dependency_overrides[get_household_repository] = lambda: repo
    app.dependency_overrides[get_travel_route_client] = lambda: Routes(fail=(-37.91,))
    app.dependency_overrides[get_road_disruption_client] = lambda: MockRoadDisruptionClient()
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/households/{household_id}/travel-routes")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "partial"
        assert len(body["routes"]) == 3
        assert body["routes"][0]["destination_type"] == "primary"
        assert len(body["routes"][0]["geometry"]) == 3
        assert "test-key" not in response.text
        assert client.get(f"/api/v1/households/{household_id}/travel-disruptions").json()["status"] == "available"
        assert client.get("/api/v1/households/unknown/travel-routes").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_missing_key_does_not_stop_live_backend_or_disruption_provider(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    monkeypatch.setenv("VIC_ROAD_DISRUPTIONS_API_KEY", "test-road-key")
    providers = build_external_providers("live")
    repo, household_id = repository()
    assert TravelRouteService(repo, providers.travel_routes).get(household_id).status == "unavailable"
    environment = os.environ.copy()
    environment.update(APP_DATA_MODE="live", APP_REPOSITORY_MODE="memory", APP_SPATIAL_MODE="mock")
    environment.pop("TOMTOM_API_KEY", None)
    result = subprocess.run([sys.executable, "-c",
        "from fastapi.testclient import TestClient; from app.main import app; assert TestClient(app).get('/api/health').status_code == 200"],
        cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_mock_mode_never_fabricates_road_geometry():
    with pytest.raises(ExternalDataUnavailable):
        build_external_providers("mock").travel_routes.road_route(HOME, TARGET)
