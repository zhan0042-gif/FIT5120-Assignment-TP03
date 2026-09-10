import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository, get_routing_client
from app.main import app
from app.providers.mock import MockRoutingClient
from app.repositories.households import InMemoryHouseholdRepository


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_routing_client] = lambda: MockRoutingClient()
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def test_simulation_returns_not_applicable_for_a_fresh_household(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]
    client.put(f"/api/v1/households/{household_id}/plan", json={})

    response = client.post(f"/api/v1/households/{household_id}/rendezvous-simulation")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_applicable"
    assert body["member_etas"] == []
    assert "member_locations" in body["missing_sections"]


def test_simulation_returns_404_for_an_unknown_household(api) -> None:
    client, _ = api

    response = client.post("/api/v1/households/hh_does_not_exist/rendezvous-simulation")

    assert response.status_code == 404
