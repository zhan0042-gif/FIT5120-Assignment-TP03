from copy import deepcopy
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_explanation_client,
    get_household_repository,
    get_routing_client,
)
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


def test_member_rows_use_only_saved_name_daytime_location_and_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "1 Treasury Place, East Melbourne VIC 3002",
    }
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan)[0] == [
        "Maya",
        "Work",
        "1 Treasury Place, East Melbourne VIC 3002",
    ]
    assert not hasattr(service, "_animal_rows")
    assert not hasattr(service, "_transport_rows")


def test_home_daytime_location_uses_saved_household_address(
    complete_plan_data: dict,
) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    plan = HouseholdPlan.model_validate(data)
    service = PreparednessPdfService()

    assert service._member_rows(plan, "84 Wattle Track, Warburton VIC 3799")[0][
        2
    ] == "84 Wattle Track, Warburton VIC 3799"
    assert service._member_rows(plan)[0][2] == "Not recorded"


def test_support_entries_are_conditional_and_include_only_relevant_members(
    complete_plan_data: dict,
) -> None:
    service = PreparednessPdfService()
    no_support = HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    assert service._support_entries(no_support) == []

    data = deepcopy(complete_plan_data)
    data["members"][0].update(
        {
            "is_dependant": True,
            "mobility_support_required": True,
            "support_notes": "Keep medication close.",
        }
    )
    plan = HouseholdPlan.model_validate(data)

    assert service._support_entries(plan) == [
        (
            "Maya",
            [
                "Dependent household member.",
                "Mobility support required.",
                "Keep medication close.",
            ],
        )
    ]


def test_key_locations_and_responsibility_checklist_preserve_saved_values(
    complete_plan,
) -> None:
    service = PreparednessPdfService()
    members = {member.member_id: member.display_name for member in complete_plan.members}

    assert service._key_location_rows(
        complete_plan, "84 Wattle Track, Warburton VIC 3799"
    ) == [
        ["Home", "84 Wattle Track, Warburton VIC 3799"],
        ["Primary destination", "Relative's House\n1 Example Road"],
        ["Backup destination", "Community Centre\n2 Safe Street"],
        ["Meeting point", "Front gate"],
    ]
    assert service._responsibility_rows(complete_plan, members) == [
        ["", "Drive household", "Maya", "Alex"]
    ]


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

    def generate(
        _self,
        _plan,
        *,
        household_address="",
        preparedness_advice=None,
        generated_at=None,
    ):
        received["household_address"] = household_address
        received["preparedness_advice"] = preparedness_advice
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
    assert received["preparedness_advice"] is None


def test_pdf_endpoint_includes_bounded_existing_advice_without_regenerating(
    complete_plan_data: dict, monkeypatch
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    received = {}

    def generate(
        _self,
        _plan,
        *,
        household_address="",
        preparedness_advice=None,
        generated_at=None,
    ):
        received["preparedness_advice"] = preparedness_advice
        return b"%PDF-test"

    monkeypatch.setattr(PreparednessPdfService, "generate", generate)
    def unexpected_provider_call():
        raise AssertionError("PDF export must not resolve AI or routing providers")

    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_explanation_client] = unexpected_provider_call
    app.dependency_overrides[get_routing_client] = unexpected_provider_call
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf",
                json={
                    "preparedness_advice": (
                        "Maya arrives last. Review who can help with the pickup."
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert received["preparedness_advice"] == (
        "Maya arrives last. Review who can help with the pickup."
    )


def test_pdf_endpoint_rejects_unbounded_advice(complete_plan_data: dict) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/households/{household_id}/preparedness-plan.pdf",
                json={"preparedness_advice": "word " * 121},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


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
