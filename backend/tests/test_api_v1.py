from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_address_client,
    get_fire_danger_client,
    get_household_repository,
    get_spatial_provider,
    get_weather_client,
)
from app.core.exceptions import (
    AddressResolutionError,
    DatabaseUnavailable,
    ExternalDataUnavailable,
    LocationNotFound,
)
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import FireDanger, HouseholdLocation


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


class UnavailableRepository:
    def create_household(self, display_name: str | None = None) -> str:
        raise DatabaseUnavailable("Application database is unavailable.")


def test_database_failure_returns_controlled_503(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_household_repository] = lambda: UnavailableRepository()

    response = client.post("/api/v1/households")

    assert response.status_code == 503
    assert response.json() == {"detail": "Application database is unavailable."}


class NoMatchingAddressClient:
    def resolve(self, address: str):
        raise AddressResolutionError("No matching Victorian household address was found.")


def test_address_resolution_error_keeps_the_saved_address_unverified(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_address_client] = lambda: NoMatchingAddressClient()
    household_id = create_household(client)

    response = client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "999 Missing Road Nowhere VIC 3999"},
    )

    assert response.status_code == 200
    assert response.json()["address"] == "999 Missing Road Nowhere VIC 3999"
    assert response.json()["verification_status"] == "unverified"
    assert response.json()["verification_message"] == (
        "No matching Victorian household address was found."
    )
    assert response.json()["latitude"] is None


def test_unverified_location_returns_controlled_context_state(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_address_client] = lambda: NoMatchingAddressClient()
    household_id = create_household(client)
    client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "999 Missing Road Nowhere VIC 3999"},
    )

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 409
    assert "address is saved" in response.json()["detail"]


def test_device_location_is_saved_and_used_without_a_fake_address(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, repository = api
    household_id = create_household(client)

    saved = client.put(
        f"/api/v1/households/{household_id}/location/device",
        json={"latitude": -37.8136, "longitude": 144.9631},
    )
    context = client.get(f"/api/v1/households/{household_id}/local-context")

    assert saved.status_code == 200
    assert saved.json()["address"] == ""
    assert saved.json()["canonical_address"] is None
    assert saved.json()["location_source"] == "device_location"
    assert saved.json()["verification_status"] == "unverified"
    assert repository.get_location(household_id).address == ""
    assert context.status_code == 200
    assert context.json()["location"]["location_source"] == "device_location"


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": -91, "longitude": 144.9631},
        {"latitude": -37.8136, "longitude": 181},
    ],
)
def test_device_location_rejects_invalid_coordinates(
    api: tuple[TestClient, InMemoryHouseholdRepository], payload: dict
) -> None:
    client, _ = api
    household_id = create_household(client)

    response = client.put(
        f"/api/v1/households/{household_id}/location/device", json=payload
    )

    assert response.status_code == 422


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
    assert fetched_plan.json()["arrangements"]["primary_destination"]["verification_status"] == "verified"
    assert fetched_plan.json()["arrangements"]["primary_destination"]["canonical_address"] == "1 Example Road"
    assert fetched_plan.json()["arrangements"]["backup_arrangements"][0]["destination"]["verification_status"] == "verified"
    assert completion_response.json()["overall_status"] == "complete"
    assert completion_response.json()["immediate_checks"] == []
    assert context_response.json()["bushfire_context"] == {
        "is_bushfire_prone_area": True,
        "fire_district": "Central",
    }
    assert context_response.json()["fire_danger"]["availability"] == "available"
    assert context_response.json()["fire_danger"]["message"] is None
    assert context_response.json()["weather"]["station_name"] == (
        "Mock Melbourne Station"
    )
    assert context_response.json()["weather"]["observed_at"]
    assert "forecast_time" not in context_response.json()["weather"]
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


def test_no_private_transport_round_trip_needs_no_fake_transport(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    household_id = create_household(client)

    save_response = client.put(
        f"/api/v1/households/{household_id}/plan",
        json={"has_private_transport": False},
    )
    completion_response = client.get(
        f"/api/v1/households/{household_id}/completion"
    )
    scenarios_response = client.get(
        f"/api/v1/scenarios/basic?household_id={household_id}"
    )

    assert save_response.status_code == 200
    assert save_response.json()["has_private_transport"] is False
    assert save_response.json()["transports"] == []
    statuses = {
        section["section"]: section["status"]
        for section in completion_response.json()["sections"]
    }
    assert statuses["transport"] == "complete"
    assert statuses["backup_transport"] == "complete"
    assert scenarios_response.status_code == 200
    vehicle = next(
        item
        for item in scenarios_response.json()
        if item["scenario_id"] == "vehicle_unavailable"
    )
    assert vehicle["enabled"] is False


def test_fake_no_transport_sentinel_is_rejected_by_api(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    household_id = create_household(client)

    response = client.put(
        f"/api/v1/households/{household_id}/plan",
        json={
            "transports": [
                {
                    "transport_id": "t_fake",
                    "transport_type": "none",
                    "display_name": "No private transport available",
                }
            ]
        },
    )

    assert response.status_code == 422


def test_shared_transport_api_save_succeeds_and_returns_immediate_check(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    plan = deepcopy(complete_plan_data)
    plan["arrangements"]["backup_arrangements"][0]["transport_id"] = "t_001"

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
                "message": "All backup arrangements use the primary transport.",
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


def test_existing_responsibility_accepts_valid_update_and_rejects_conflict(
    api: tuple[TestClient, InMemoryHouseholdRepository], complete_plan_data: dict
) -> None:
    client, _ = api
    household_id = create_household(client)
    assert client.put(
        f"/api/v1/households/{household_id}/plan", json=complete_plan_data
    ).status_code == 200

    updated = deepcopy(complete_plan_data)
    updated["responsibilities"][0]["task_name"] = "Collect the emergency kit"
    valid_response = client.put(
        f"/api/v1/households/{household_id}/plan", json=updated
    )

    invalid = deepcopy(updated)
    invalid["responsibilities"][0]["backup_member_id"] = "m_001"
    invalid_response = client.put(
        f"/api/v1/households/{household_id}/plan", json=invalid
    )
    saved = client.get(f"/api/v1/households/{household_id}/plan").json()

    assert valid_response.status_code == 200
    assert invalid_response.status_code == 422
    assert saved["responsibilities"][0] == updated["responsibilities"][0]


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
        "location_source": "address",
        "canonical_address": "Warrandyte VIC 3113",
        "unit_number": None,
        "street_number": None,
        "street_name": None,
        "suburb_or_locality": None,
        "state": "VIC",
        "postcode": None,
        "country": "Australia",
        "latitude": -37.74,
        "longitude": 145.21,
        "verification_status": "verified",
        "verification_message": None,
        "verified_at": first.json()["verified_at"],
    }
    assert second.status_code == 200
    assert repository.get_location(household_id) == HouseholdLocation.model_validate(
        second.json()
    )


def test_address_suggestion_endpoint_returns_provider_candidates(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api

    response = client.get("/api/v1/locations/suggestions", params={"q": "warr"})

    assert response.status_code == 200
    assert response.json()[0]["address"] == "Warrandyte Vic 3113"
    assert response.json()[0]["state"] == "VIC"
    assert response.json()[0]["country"] == "Australia"


def test_address_suggestion_endpoint_ignores_incomplete_query(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api

    response = client.get("/api/v1/locations/suggestions", params={"q": "84"})

    assert response.status_code == 200
    assert response.json() == []


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
    plan_without_backup["arrangements"]["backup_arrangements"] = []
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


class UnavailableWeatherClient:
    def get_weather(self, latitude: float, longitude: float):
        raise ExternalDataUnavailable("Official BOM weather is unavailable")


class FailingFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise ExternalDataUnavailable("Official BOM FDR is unavailable")


class MalformedFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise ExternalDataUnavailable("The BOM FDR product is malformed")


class UnexpectedFireDangerClient:
    def get_fire_danger(self, fire_district: str):
        raise RuntimeError("unexpected implementation defect")


class StaleFireDangerClient:
    def get_fire_danger(self, fire_district: str) -> FireDanger:
        return FireDanger(
            today="High",
            tomorrow="High",
            day_3="Extreme",
            day_4="Extreme",
            source_updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )


def _save_mock_location(client: TestClient, household_id: str) -> None:
    response = client.put(
        f"/api/v1/households/{household_id}/location",
        json={"address": "Warrandyte VIC 3113"},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "client_factory",
    [lambda: FailingFireDangerClient(), lambda: MalformedFireDangerClient()],
)
def test_unavailable_or_malformed_fdr_returns_partial_local_context(
    api: tuple[TestClient, InMemoryHouseholdRepository], client_factory
) -> None:
    client, _ = api
    app.dependency_overrides[get_fire_danger_client] = client_factory
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["location"]["address"] == "Warrandyte VIC 3113"
    assert payload["bushfire_context"]["fire_district"] == "Central"
    assert payload["weather"]["station_name"] == "Mock Melbourne Station"
    assert payload["environmental_context"] == {
        "fire_history_summary": None,
        "vegetation_context": None,
        "terrain_context": None,
    }
    assert payload["fire_danger"] == {
        "availability": "unavailable",
        "today": None,
        "tomorrow": None,
        "day_3": None,
        "day_4": None,
        "source_updated_at": None,
        "source_url": None,
        "message": (
            "Current fire danger information is not available from the official source."
        ),
    }


def test_stale_fdr_returns_partial_local_context(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_fire_danger_client] = StaleFireDangerClient
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 200
    assert response.json()["fire_danger"]["availability"] == "unavailable"
    assert response.json()["fire_danger"]["today"] is None


def test_unexpected_fdr_error_remains_full_local_context_failure(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_fire_danger_client] = UnexpectedFireDangerClient
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 503


def test_weather_failure_remains_full_local_context_failure(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_weather_client] = FailingWeatherClient
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 503


def test_controlled_weather_unavailability_returns_partial_local_context(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_weather_client] = UnavailableWeatherClient
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 200
    assert response.json()["bushfire_context"]["fire_district"] == "Central"
    assert response.json()["fire_danger"]["availability"] == "available"
    assert response.json()["weather"] is None


def test_reverse_lookup_returns_candidates_without_persisting_or_verifying_them(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, repository = api
    household_id = create_household(client)

    response = client.post(
        "/api/v1/locations/nearby-addresses",
        json={"latitude": -37.8136, "longitude": 144.9631},
    )

    assert response.status_code == 200
    assert response.json()[0]["address"] == "Melbourne Vic 3000"
    assert response.json()[0]["verification_status"] == "unverified"
    with pytest.raises(LocationNotFound):
        repository.get_location(household_id)


def test_spatial_failure_remains_full_local_context_failure(
    api: tuple[TestClient, InMemoryHouseholdRepository],
) -> None:
    client, _ = api
    app.dependency_overrides[get_spatial_provider] = FailingSpatialProvider
    household_id = create_household(client)
    _save_mock_location(client, household_id)

    response = client.get(f"/api/v1/households/{household_id}/local-context")

    assert response.status_code == 503


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
