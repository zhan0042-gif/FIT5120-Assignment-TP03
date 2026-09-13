from copy import deepcopy
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdPlan
from app.services.preparedness_pdf import PreparednessPdfService


def test_pdf_generation_returns_valid_non_empty_content(complete_plan) -> None:
    content = PreparednessPdfService().generate(
        complete_plan,
        generated_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
    )

    assert content.startswith(b"%PDF-")
    assert len(content) > 1_000


def test_missing_optional_plan_values_do_not_crash_pdf_generation() -> None:
    content = PreparednessPdfService().generate(HouseholdPlan())

    assert content.startswith(b"%PDF-")
    assert len(content) > 1_000


def test_household_tables_use_saved_daytime_location_and_clear_pet_columns(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "1 Treasury Place, East Melbourne VIC 3002",
    }
    data["animals"][0].update(
        {"animal_type": "cat", "display_name": "Gift", "quantity": 1}
    )
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan)[0] == [
        "Maya",
        "Self",
        "Not recorded",
        "Work",
        "1 Treasury Place, East Melbourne VIC 3002",
    ]
    assert service._animal_rows(plan)[0] == ["Cat", "Gift", "1"]


def test_home_daytime_location_uses_saved_household_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan, "84 Wattle Track, Warburton VIC 3799")[0][
        4
    ] == "84 Wattle Track, Warburton VIC 3799"
    assert service._member_rows(plan)[0][4] == "Not recorded"


def test_pdf_endpoint_passes_saved_canonical_household_address(
    complete_plan_data: dict, monkeypatch
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="84 wattle track",
            canonical_address="84 Wattle Track, Warburton VIC 3799",
        ),
    )
    received = {}

    def generate(_self, _plan, *, household_address="", generated_at=None):
        received["household_address"] = household_address
        return b"%PDF-test"

    monkeypatch.setattr(PreparednessPdfService, "generate", generate)
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert received["household_address"] == "84 Wattle Track, Warburton VIC 3799"


def test_pdf_export_has_download_headers_and_does_not_modify_saved_plan(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    plan = HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    repository.save_plan(household_id, plan)
    before = repository.get_plan(household_id).model_dump()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="firebreak-household-plan.pdf"'
    )
    assert response.content.startswith(b"%PDF-")
    assert repository.get_plan(household_id).model_dump() == before


def test_pdf_export_for_missing_household_uses_existing_404_behaviour() -> None:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/households/hh_missing/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Household 'hh_missing' was not found."
    }


def test_pdf_export_for_household_without_plan_uses_existing_404_behaviour() -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    app.dependency_overrides[get_household_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Household '{household_id}' does not have a plan."
    }
