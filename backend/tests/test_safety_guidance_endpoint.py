import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository, get_safety_guidance_entries
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.safety_guidance import GuidanceEntryDefinition


def _entry(entry_id: str, reviewed_by: str | None = "Reviewer", **conditions):
    return GuidanceEntryDefinition.model_validate(
        {
            "id": entry_id,
            "question": f"Question {entry_id}?",
            "answer": "Answer.",
            "source_name": "CFA",
            "source_url": "https://www.cfa.vic.gov.au/example",
            "retrieved_on": "2026-10-05",
            "reviewed_by": reviewed_by,
            "applies_when": conditions,
        }
    )


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    entries = [
        _entry("general"),
        _entry("pets", has_pets=True),
        _entry("unreviewed", reviewed_by=None),
    ]
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_safety_guidance_entries] = lambda: entries
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def test_a_household_without_a_plan_gets_every_entry_and_general_suggestions(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]

    response = client.get(f"/api/v1/households/{household_id}/safety-guidance")

    assert response.status_code == 200
    body = response.json()
    assert [entry["id"] for entry in body["entries"]] == ["general", "pets"]
    assert body["suggested_ids"] == ["general"]
    assert body["location_conditions_applied"] is False


def test_an_entry_has_its_question_answer_and_source(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]

    entry = client.get(f"/api/v1/households/{household_id}/safety-guidance").json()["entries"][0]

    assert entry == {
        "id": "general",
        "question": "Question general?",
        "answer": "Answer.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
    }


def test_a_saved_plan_with_a_pet_suggests_the_pet_question_first(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]
    client.put(
        f"/api/v1/households/{household_id}/plan",
        json={"animals": [{"animal_id": "a_001", "category": "pet"}]},
    )

    body = client.get(f"/api/v1/households/{household_id}/safety-guidance").json()

    assert body["suggested_ids"] == ["pets", "general"]


def test_reading_guidance_does_not_change_the_plan(api) -> None:
    client, repository = api
    household_id = client.post("/api/v1/households").json()["household_id"]
    client.put(
        f"/api/v1/households/{household_id}/plan",
        json={"animals": [{"animal_id": "a_001", "category": "pet"}]},
    )
    before = repository.get_plan(household_id).model_dump()

    client.get(f"/api/v1/households/{household_id}/safety-guidance")

    assert repository.get_plan(household_id).model_dump() == before


def test_an_unknown_household_returns_404(api) -> None:
    client, _ = api

    response = client.get("/api/v1/households/hh_does_not_exist/safety-guidance")

    assert response.status_code == 404


def test_the_shipped_content_is_served_by_default() -> None:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            household_id = client.post("/api/v1/households").json()["household_id"]
            response = client.get(f"/api/v1/households/{household_id}/safety-guidance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()) == {"entries", "suggested_ids", "location_conditions_applied"}
