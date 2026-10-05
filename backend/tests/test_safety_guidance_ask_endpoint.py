import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_guidance_router,
    get_household_repository,
    get_safety_guidance_entries,
)
from app.core.exceptions import ExternalDataUnavailable
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.safety_guidance import GuidanceEntryDefinition


def _entry(entry_id: str, reviewed_by: str | None = "Reviewer"):
    return GuidanceEntryDefinition.model_validate(
        {
            "id": entry_id,
            "question": f"Question {entry_id}?",
            "answer": "Answer.",
            "source_name": "CFA",
            "source_url": "https://www.cfa.vic.gov.au/example",
            "retrieved_on": "2026-10-05",
            "reviewed_by": reviewed_by,
        }
    )


class Router:
    def __init__(self, ids=None, error: Exception | None = None) -> None:
        self.ids = ids if ids is not None else []
        self.error = error
        self.calls: list[str] = []

    def route(self, question, catalogue):
        self.calls.append(question)
        if self.error:
            raise self.error
        return self.ids


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    router = Router(["a"])
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_guidance_router] = lambda: router
    app.dependency_overrides[get_safety_guidance_entries] = lambda: [_entry("a"), _entry("b")]
    with TestClient(app) as client:
        household_id = client.post("/api/v1/households").json()["household_id"]
        yield client, repository, router, household_id
    app.dependency_overrides.clear()


def _ask(client, household_id, question):
    return client.post(
        f"/api/v1/households/{household_id}/safety-guidance/ask",
        json={"question": question},
    )


def test_a_matched_question_returns_the_entry_ids(api) -> None:
    client, _, router, household_id = api

    response = _ask(client, household_id, "Is this ok?")

    assert response.status_code == 200
    assert response.json() == {"status": "matched", "entry_ids": ["a"]}
    assert router.calls == ["Is this ok?"]


def test_the_question_is_trimmed_before_it_is_used(api) -> None:
    client, _, router, household_id = api

    _ask(client, household_id, "   Is this ok?   ")

    assert router.calls == ["Is this ok?"]


def test_a_question_with_no_match_is_still_a_200(api) -> None:
    client, _, router, household_id = api
    router.ids = []

    response = _ask(client, household_id, "Something unrelated")

    assert response.status_code == 200
    assert response.json() == {"status": "no_match", "entry_ids": []}


def test_an_invented_id_is_dropped(api) -> None:
    client, _, router, household_id = api
    router.ids = ["invented"]

    assert _ask(client, household_id, "Is this ok?").json()["status"] == "no_match"


def test_emergency_wording_returns_emergency_and_skips_the_router(api) -> None:
    client, _, router, household_id = api

    response = _ask(client, household_id, "My house is on fire")

    assert response.status_code == 200
    assert response.json() == {"status": "emergency", "entry_ids": []}
    assert router.calls == []


def test_a_router_failure_is_unavailable_not_a_server_error(api) -> None:
    client, _, router, household_id = api
    router.error = ExternalDataUnavailable("down")

    response = _ask(client, household_id, "Is this ok?")

    assert response.status_code == 200
    assert response.json() == {"status": "unavailable", "entry_ids": []}


@pytest.mark.parametrize("question", ["", "   ", "x" * 301])
def test_an_empty_or_over_long_question_is_rejected(api, question: str) -> None:
    client, _, router, household_id = api

    response = _ask(client, household_id, question)

    assert response.status_code == 422
    assert router.calls == []


def test_a_question_of_exactly_300_characters_is_accepted(api) -> None:
    client, _, _, household_id = api

    assert _ask(client, household_id, "x" * 300).status_code == 200


def test_an_unexpected_field_is_rejected(api) -> None:
    client, _, _, household_id = api

    response = client.post(
        f"/api/v1/households/{household_id}/safety-guidance/ask",
        json={"question": "Is this ok?", "household": "hh_1"},
    )

    assert response.status_code == 422


def test_an_unknown_household_returns_404(api) -> None:
    client, _, router, _ = api

    response = _ask(client, "hh_does_not_exist", "Is this ok?")

    assert response.status_code == 404
    assert router.calls == []


def test_asking_does_not_change_the_plan(api) -> None:
    client, repository, _, household_id = api
    client.put(
        f"/api/v1/households/{household_id}/plan",
        json={"animals": [{"animal_id": "a_001", "category": "pet"}]},
    )
    before = repository.get_plan(household_id).model_dump()

    _ask(client, household_id, "Is this ok?")

    assert repository.get_plan(household_id).model_dump() == before


def test_mock_mode_answers_a_shipped_question_end_to_end() -> None:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            household_id = client.post("/api/v1/households").json()["household_id"]
            response = _ask(client, household_id, "What should a pet kit include?")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "matched", "entry_ids": ["pet-kit"]}
