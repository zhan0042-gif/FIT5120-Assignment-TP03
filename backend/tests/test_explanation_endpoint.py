from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_explanation_client, get_household_repository
from app.core.exceptions import ExternalDataUnavailable
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.rendezvous import RendezvousResult

READY_BODY = {
    "status": "ready",
    "destination_name": "Grandma's house",
    "member_etas": [
        {
            "member_id": "m1", "display_name": "Minh", "origin_kind": "home",
            "travel_seconds": 1620, "distance_meters": 21000, "waiting_seconds": 1680,
        },
        {
            "member_id": "m2", "display_name": "Lan", "origin_kind": "work",
            "travel_seconds": 3300, "distance_meters": 65000, "waiting_seconds": 0,
        },
    ],
    "everyone_together_seconds": 3300,
    "slowest_member_id": "m2",
    "warnings": [],
    "simulated_at": datetime.now(timezone.utc).isoformat(),
}

CLEAN = (
    "Lan takes 55 minutes and arrives last, so the household is not together "
    "until then. Consider arranging a lift so Lan can set off sooner."
)


class FixedClient:
    def __init__(self, text: str) -> None:
        self.text = text

    def explain(self, result: RendezvousResult) -> str:
        return self.text


class DeadClient:
    def explain(self, result: RendezvousResult) -> str:
        raise ExternalDataUnavailable("unavailable")


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def _household(client: TestClient) -> str:
    return client.post("/api/v1/households").json()["household_id"]


def test_a_clean_passage_is_returned(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient(CLEAN)
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] == CLEAN


def test_a_rejected_passage_returns_200_with_no_explanation(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient(
        "Lan may be delayed by smoke on the way."
    )
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] is None
    assert response.json()["reason"] == "speculation"


def test_a_dead_provider_returns_200_with_no_explanation(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: DeadClient()
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] is None
    assert response.json()["reason"] == "unavailable"


def test_an_unknown_household_is_404(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient("Fine.")

    response = client.post(
        "/api/v1/households/hh_missing/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 404
