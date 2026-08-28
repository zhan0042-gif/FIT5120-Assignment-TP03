from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_fire_danger_client,
    get_household_repository,
    get_spatial_provider,
    get_weather_client,
)
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import FireDanger


@pytest.fixture
def api() -> tuple[TestClient, InMemoryHouseholdRepository]:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def create_household(client: TestClient) -> str:
    response = client.post("/api/v1/households")
    assert response.status_code == 201
    return response.json()["household_id"]


def test_complete_household_api_flow(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, repository = api
    household_id = create_household(client)

    plan_response = client.put(
        f"/api/v1/households/{household_id}/plan", json=complete_plan_data
    )
    location_response = client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Warrandyte VIC 3113"},
    )
    fetched_plan = client.get(f"/api/v1/households/{household_id}/plan")
    completion_response = client.get(
        f"/api/v1/households/{household_id}/completion"
    )
    context_response = client.get(
        f"/api/v1/households/{household_id}/local-context"
    )
    preparation_response = client.get(
        f"/api/v1/households/{household_id}/preparation-support"
    )
    test_response = client.post(
        f"/api/v1/households/{household_id}/tests",
        json={"scenario_id": "vehicle_unavailable"},
    )

    assert plan_response.status_code == 200
    assert location_response.status_code == 200
    assert fetched_plan.json() == complete_plan_data
    assert completion_response.json()["overall_status"] == "complete"
    assert completion_response.json()["immediate_checks"] == []
    assert context_response.json()["bushfire_context"] == {
        "is_bushfire_prone_area": True,
        "fire_district": "Central",
    }
    assert preparation_response.json()["status"] == "review_recommended"
    assert test_response.status_code == 201
    assert test_response.json()["overall_status"] == "pass"
    assert len(repository.get_test_results(household_id)) == 1


def test_business_validation_returns_clean_422(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    invalid = deepcopy(complete_plan_data)
    invalid["transports"][0]["driver_member_ids"] = ["not_a_member"]

    response = client.put(
        f"/api/v1/households/{household_id}/plan", json=invalid
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "The household plan is invalid."
    assert "unknown driver" in response.json()["detail"]["errors"][0]


def test_partial_plan_round_trip_and_completion(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    household_id = create_household(client)

    save_response = client.put(
        f"/api/v1/households/{household_id}/plan", json={}
    )
    completion_response = client.get(
        f"/api/v1/households/{household_id}/completion"
    )

    assert save_response.status_code == 200
    assert save_response.json()["members"] == []
    assert save_response.json()["animals"] == []
    assert completion_response.status_code == 200
    assert completion_response.json()["overall_status"] == "needs_information"
    assert all(
        section["status"] == "needs_information"
        for section in completion_response.json()["sections"]
    )
    assert completion_response.json()["immediate_checks"] == []


def test_shared_transport_api_save_succeeds_and_returns_immediate_check(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    plan = deepcopy(complete_plan_data)
    plan["arrangements"]["backup_transport_id"] = "t_001"

    save_response = client.put(
        f"/api/v1/households/{household_id}/plan", json=plan
    )
    completion_response = client.get(
        f"/api/v1/households/{household_id}/completion"
    )

    assert save_response.status_code == 200
    assert completion_response.status_code == 200
    assert completion_response.json()["immediate_checks"] == [
        {
            "check": "shared_transport_resource",
            "section": "backup_transport",
            "status": "warning",
            "message": "Primary and backup transport use the same resource.",
        }
    ]


def test_same_responsible_person_api_remains_invalid(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    plan = deepcopy(complete_plan_data)
    plan["responsibilities"][0]["backup_member_id"] = "m_001"

    response = client.put(
        f"/api/v1/households/{household_id}/plan", json=plan
    )

    assert response.status_code == 422
    assert "different backup member" in response.json()["detail"]["errors"][0]


def test_whitespace_only_location_is_rejected(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    household_id = create_household(client)

    response = client.put(
        f"/api/v1/households/{household_id}/location", json={"address": "   "}
    )

    assert response.status_code == 422


def test_location_is_resolved_saved_and_replaced(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, repository = api
    household_id = create_household(client)

    first = client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "  Warrandyte   VIC 3113  "},
    )
    second = client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Melbourne VIC 3000"},
    )

    assert first.status_code == 200
    assert first.json() == {
        "address": "Warrandyte VIC 3113",
        "latitude": -37.74,
        "longitude": 145.21,
    }
    assert second.status_code == 200
    assert repository.get_location(household_id).model_dump() == second.json()


def test_location_save_for_missing_household_returns_404(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api

    response = client.put(
        "/api/v1/households/missing/location",
        json={"address": "Warrandyte VIC 3113"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/households/missing/plan",
        "/api/v1/households/missing/completion",
        "/api/v1/households/missing/local-context",
    ],
)
def test_missing_household_returns_404(
    api: tuple[TestClient, InMemoryHouseholdRepository], path: str
) -> None:
    client, _ = api
    assert client.get(path).status_code == 404


def test_plan_and_location_not_found(
    api: tuple[TestClient, InMemoryHouseholdRepository]
) -> None:
    client, _ = api
    household_id = create_household(client)

    assert client.get(f"/api/v1/households/{household_id}/plan").status_code == 404
    assert (
        client.get(f"/api/v1/households/{household_id}/local-context").status_code
        == 404
    )


def test_basic_scenarios_contract(api, complete_plan_data: dict) -> None:
    client, _ = api
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json=complete_plan_data)
    response = client.get(
        "/api/v1/scenarios/basic", params={"household_id": household_id}
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "scenario_id": "vehicle_unavailable",
            "title": "Main Vehicle Unavailable",
            "description": "Check whether another transport option is available.",
            "enabled": True,
            "disabled_reason": None,
        },
        {
            "scenario_id": "person_unavailable",
            "title": "Primary Responsible Person Unavailable",
            "description": "Check whether important responsibilities have backup people.",
            "enabled": True,
            "disabled_reason": None,
        },
        {
            "scenario_id": "destination_unavailable",
            "title": "Primary Destination Unavailable",
            "description": "Check whether another destination is available.",
            "enabled": True,
            "disabled_reason": None,
        },
    ]


def test_scenario_listing_requires_existing_household_and_plan(api) -> None:
    client, _ = api
    household_id = create_household(client)

    assert client.get(
        "/api/v1/scenarios/basic", params={"household_id": "missing"}
    ).status_code == 404
    assert client.get(
        "/api/v1/scenarios/basic", params={"household_id": household_id}
    ).status_code == 404


def test_disabled_scenario_execution_returns_422(api) -> None:
    client, repository = api
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json={})

    response = client.post(
        f"/api/v1/households/{household_id}/tests",
        json={"scenario_id": "vehicle_unavailable"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "No primary transport is currently recorded."
    assert repository.get_test_results(household_id) == []


def test_test_execution_uses_latest_saved_plan_and_persists_both_results(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, repository = api
    household_id = create_household(client)
    plan_without_backup = deepcopy(complete_plan_data)
    plan_without_backup["arrangements"]["backup_transport_id"] = None
    client.put(
        f"/api/v1/households/{household_id}/plan", json=plan_without_backup
    )

    first = client.post(
        f"/api/v1/households/{household_id}/tests",
        json={"scenario_id": "vehicle_unavailable"},
    )
    client.put(
        f"/api/v1/households/{household_id}/plan", json=complete_plan_data
    )
    second = client.post(
        f"/api/v1/households/{household_id}/tests",
        json={"scenario_id": "vehicle_unavailable"},
    )

    assert first.status_code == 201
    assert first.json()["overall_status"] == "needs_attention"
    assert first.json()["first_problem"]["section"] == "transport"
    assert first.json()["result_reason"]
    assert second.status_code == 201
    assert second.json()["overall_status"] == "pass"
    assert second.json()["first_problem"] is None
    assert second.json()["result_reason"]
    assert first.json()["test_run_id"] != second.json()["test_run_id"]
    assert len(repository.get_test_results(household_id)) == 2

    retrieved = client.get(
        f"/api/v1/households/{household_id}/tests/{first.json()['test_run_id']}"
    )
    other_household = create_household(client)
    wrong_household = client.get(
        f"/api/v1/households/{other_household}/tests/{first.json()['test_run_id']}"
    )
    assert retrieved.status_code == 200
    assert retrieved.json() == first.json()
    assert wrong_household.status_code == 404


def test_unsupported_scenario_returns_404(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json=complete_plan_data)

    response = client.post(
        f"/api/v1/households/{household_id}/tests",
        json={"scenario_id": "unknown"},
    )

    assert response.status_code == 404


class FailingSpatialProvider:
    def get_context(self, latitude: float, longitude: float):
        raise RuntimeError("offline")


class FailingWeatherClient:
    def get_weather(self, latitude: float, longitude: float):
        raise RuntimeError("BOM offline")


class FailingFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise RuntimeError("CFA offline")


class StaleFireDangerClient:
    def get_fire_danger(self, fire_district: str) -> FireDanger:
        return FireDanger(
            today="High",
            tomorrow="High",
            day_3="Extreme",
            day_4="Extreme",
            source_updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )


def test_provider_failure_returns_503(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    app.dependency_overrides[get_spatial_provider] = lambda: FailingSpatialProvider()
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json=complete_plan_data)
    client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Warrandyte VIC 3113"},
    )

    response = client.get(
        f"/api/v1/households/{household_id}/preparation-support"
    )

    assert response.status_code == 503


def test_preparation_support_does_not_require_weather(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    app.dependency_overrides[get_weather_client] = lambda: FailingWeatherClient()
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json=complete_plan_data)
    client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Warrandyte VIC 3113"},
    )

    response = client.get(
        f"/api/v1/households/{household_id}/preparation-support"
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "client_factory",
    [lambda: FailingFireDangerClient(), lambda: StaleFireDangerClient()],
)
def test_unavailable_or_stale_fdr_returns_503_for_preparation_support(
    api: tuple[TestClient, InMemoryHouseholdRepository],
    complete_plan_data: dict,
    client_factory,
) -> None:
    client, _ = api
    app.dependency_overrides[get_fire_danger_client] = client_factory
    household_id = create_household(client)
    client.put(f"/api/v1/households/{household_id}/plan", json=complete_plan_data)
    client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Warrandyte VIC 3113"},
    )

    response = client.get(
        f"/api/v1/households/{household_id}/preparation-support"
    )

    assert response.status_code == 503
