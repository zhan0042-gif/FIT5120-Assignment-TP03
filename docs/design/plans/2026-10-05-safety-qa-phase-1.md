# Safety Q&A, Phase 1 Implementation Plan

**Goal:** Replace the safety guidance card list with a chat-style panel: suggested question buttons that show short reviewed answers with sources, and the full list collapsed below. No model is called in this phase.

**Architecture:** The reviewed content file is reshaped from long cards into short question-and-answer entries. The existing selection service returns every reviewed entry plus an ordered list of suggested ids (up to four tailored to the household, then general ones, six in total). The browser answers a tapped question from the entries it already holds, so no further request is made. The chat history lives only in a Pinia store for the visit.

**Tech Stack:** FastAPI + Pydantic v2 (Python 3.12), pytest; Vue 3 + Pinia (plain JavaScript), Node's built-in test runner.

**Spec:** `docs/design/specs/2026-10-05-safety-qa-design.md` (Phase 1 sections). It builds on `docs/design/specs/2026-10-05-safety-guidance-design.md` and reshapes the code from `docs/design/plans/2026-10-05-safety-guidance.md`.

## Global Constraints

- Frontend is plain JavaScript, not TypeScript. Backend tests run from `backend/` with `pytest`; frontend tests run from `frontend/` with `npm test`.
- Endpoint stays `GET /api/v1/households/{household_id}/safety-guidance`. Its response becomes `{ entries, suggested_ids, location_conditions_applied }`; the earlier `cards` field is removed. Unknown household is `404`. It calls no model and writes nothing.
- `entries` is every reviewed entry in file order, regardless of the household. An entry with `reviewed_by: null` is never served.
- `suggested_ids` is at most six ids: first up to four tailored entries (non-empty `applies_when` that holds), then general entries (empty `applies_when`), each in file order.
- Allowed `applies_when` keys, and only these: `has_dependants`, `has_mobility_support`, `has_pets`, `has_livestock`, `no_private_transport`, `in_bushfire_prone_area`. A key, when present, must be `true`. Unknown keys fail validation.
- An entry's `answer` is at most 600 characters, plain prose, written in the team's own words (never copied from CFA). `source_url` is `https://` and required. `retrieved_on` is required and is the date a person checked the page.
- An invalid content file makes the app fail at import.
- The date is never refreshed automatically. Cards older than six months get a note (existing `guidanceFreshness.js`).
- The fixed notice ("not for emergencies; if you are in danger call 000") is a frontend constant, always visible, and never depends on the content file.
- Never fabricate: when the location cannot be resolved, location-conditioned entries are left out of `suggested_ids` and `location_conditions_applied` is `false`. The condition is never guessed.
- UI copy is English and never worded as prediction.
- Chat messages are never sent to or stored on the server.
- Conventional commits with a scope.
- Work on branch `feature/safety-guidance`.
- `asked_as` is not part of Phase 1 entries (Phase 2 introduces it).

## Review Focus

- A household with several matching tailored entries must still be offered general questions such as when to leave: at most four tailored, six in total. (Task 1)
- A household with no reviewed entries at all: `entries` and `suggested_ids` are empty, the panel does not crash, and the emergency notice still shows. (Task 1, Task 3)
- A question for something the household does not have (a pet entry for a household with no pets) is still in `entries`, so it stays reachable under "Read all guidance". (Task 1)
- An answer longer than 600 characters, a whitespace-only `reviewed_by`, and an unknown condition key are rejected when the file loads. (Task 1)
- Tapping a suggested question whose id is no longer in `entries` must do nothing rather than throw. (Task 2)
- The emergency notice must be visible while the guidance is loading, after it fails, and when it is empty. (Task 3)

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/schemas/safety_guidance.py` (rewrite) | Entry definition with strict conditions; response models |
| `backend/app/content/safety_guidance.json` (rewrite) | The reviewed Q&A entries |
| `backend/app/services/safety_guidance.py` (rewrite) | Load/validate the file; derive entries and suggested ids |
| `backend/app/core/dependencies.py` (modify) | `get_safety_guidance_entries` |
| `backend/app/api/routes/households.py` (modify) | Route uses entries |
| `backend/tests/test_safety_guidance_content.py` (rewrite) | File and loader validation |
| `backend/tests/test_safety_guidance_service.py` (rewrite) | Selection rules |
| `backend/tests/test_safety_guidance_endpoint.py` (rewrite) | HTTP behaviour |
| `docs/iteration1-integration-contract.md` (modify) | New response shape |
| `frontend/src/stores/safetyGuidance.js` (rewrite) | Entries, suggestions, chat messages |
| `frontend/tests/safetyGuidanceStore.test.js` (rewrite) | Store behaviour |
| `frontend/src/utils/safetyGuidanceCopy.js` (create) | Fixed notice and empty-state text |
| `frontend/tests/safetyGuidanceCopy.test.js` (create) | Pins the notice |
| `frontend/src/components/overview/SafetyChatPanel.vue` (create) | The chat panel |
| `frontend/src/components/overview/SafetyGuidancePanel.vue` (delete) | Replaced |
| `frontend/src/views/OverviewView.vue` (modify) | Mount the chat panel |

---

### Task 1: Backend entries, selection and endpoint

The schema, loader, service, dependency and route share names, so they change together; the app would not import between the steps otherwise. Work the steps in order and commit once.

**Files:**
- Rewrite: `backend/app/schemas/safety_guidance.py`
- Rewrite: `backend/app/content/safety_guidance.json`
- Rewrite: `backend/app/services/safety_guidance.py`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/api/routes/households.py`
- Rewrite: `backend/tests/test_safety_guidance_content.py`, `backend/tests/test_safety_guidance_service.py`, `backend/tests/test_safety_guidance_endpoint.py`
- Modify: `docs/iteration1-integration-contract.md`

**Interfaces:**
- Consumes: `HouseholdStaticContextResolver(repository, spatial_provider).get_full(household_id)` from `app/services/context.py`; `HouseholdRepository.household_exists`, `get_plan`.
- Produces:
  - `GuidanceConditions.required() -> frozenset[str]` (unchanged)
  - `GuidanceEntryDefinition` (`id, question, answer, source_name, source_url, retrieved_on: date, reviewed_by: str | None, applies_when`)
  - `GuidanceEntry` (`id, question, answer, source_name, source_url, retrieved_on`)
  - `SafetyGuidance` (`entries: list[GuidanceEntry]`, `suggested_ids: list[str]`, `location_conditions_applied: bool`)
  - `load_entries(path: Path = CONTENT_PATH) -> list[GuidanceEntryDefinition]`, `CONTENT_PATH`, `DEFAULT_ENTRIES`
  - `plan_facts(plan) -> set[str]` (unchanged), `MAX_SUGGESTED = 6`, `MAX_TAILORED = 4`
  - `SafetyGuidanceService(repository, spatial_provider, entries=None).get(household_id) -> SafetyGuidance`
  - `get_safety_guidance_entries() -> list[GuidanceEntryDefinition]` dependency

- [ ] **Step 1: Write the failing content tests**

Replace `backend/tests/test_safety_guidance_content.py` with:

```python
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.services.safety_guidance import CONTENT_PATH, load_entries


def _entry(**overrides) -> dict:
    entry = {
        "id": "example-entry",
        "question": "An example question?",
        "answer": "A short answer.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
        "reviewed_by": None,
        "applies_when": {},
    }
    entry.update(overrides)
    return entry


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "entries.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_shipped_content_file_loads_in_display_order() -> None:
    entries = load_entries(CONTENT_PATH)

    assert [entry.id for entry in entries] == [
        "when-to-leave",
        "leaving-late-danger",
        "too-late-to-leave",
        "stay-and-defend",
        "emergency-kit",
        "children-comfort",
        "pets-plan",
        "pet-kit",
        "pets-relief-centres",
        "extra-help-leave-early",
        "extra-support-plan",
        "property-prep",
        "extreme-day-home",
    ]


def test_every_shipped_entry_names_a_cfa_page_and_a_real_date() -> None:
    for entry in load_entries(CONTENT_PATH):
        assert urlparse(entry.source_url).hostname == "www.cfa.vic.gov.au"
        # The reviewer re-records this from the live page, so pin only that it is real.
        assert entry.retrieved_on <= date.today()


def test_a_valid_entry_loads(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(applies_when={"has_pets": True})]))

    assert entries[0].applies_when.required() == frozenset({"has_pets"})


def test_an_empty_condition_object_applies_to_everyone(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry()]))

    assert entries[0].applies_when.required() == frozenset()


def test_an_unknown_condition_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(applies_when={"has_children": True})]))


def test_a_condition_set_to_false_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(applies_when={"has_pets": False})]))


def test_a_missing_question_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["question"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_a_missing_source_url_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["source_url"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_a_source_url_that_is_not_https_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(source_url="http://example.com")]))


def test_a_missing_retrieved_on_is_rejected(tmp_path: Path) -> None:
    entry = _entry()
    del entry["retrieved_on"]

    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [entry]))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        load_entries(_write(tmp_path, [_entry(), _entry(question="Another?")]))


def test_an_id_that_is_not_a_slug_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(id="Not A Slug")]))


def test_an_answer_of_exactly_600_characters_is_accepted(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(answer="a" * 600)]))

    assert len(entries[0].answer) == 600


def test_an_answer_longer_than_600_characters_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(answer="a" * 601)]))


def test_a_reviewer_name_of_only_spaces_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_entries(_write(tmp_path, [_entry(reviewed_by="   ")]))


def test_a_reviewer_name_is_trimmed(tmp_path: Path) -> None:
    entries = load_entries(_write(tmp_path, [_entry(reviewed_by="  Ada  ")]))

    assert entries[0].reviewed_by == "Ada"
```

- [ ] **Step 2: Write the failing service tests**

Replace `backend/tests/test_safety_guidance_service.py` with:

```python
from types import SimpleNamespace

import pytest

from app.core.exceptions import ExternalDataUnavailable, HouseholdNotFound
from app.providers.mock import MockSpatialProvider
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import (
    Animal,
    HouseholdLocation,
    HouseholdMember,
    HouseholdPlan,
)
from app.schemas.safety_guidance import GuidanceEntryDefinition
from app.services.safety_guidance import SafetyGuidanceService, plan_facts


def entry(entry_id: str, reviewed_by: str | None = "Reviewer", **conditions):
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


class NotProneSpatial:
    def get_context(self, latitude, longitude):
        return SimpleNamespace(
            latitude=latitude,
            longitude=longitude,
            is_bushfire_prone_area=False,
            fire_district="Central",
        )


class FailingSpatial:
    def get_context(self, latitude, longitude):
        raise ExternalDataUnavailable("spatial data is down")


def member(member_id="m_001", *, dependant=False, mobility=False):
    return HouseholdMember(
        member_id=member_id,
        is_dependant=dependant,
        mobility_support_required=mobility,
    )


def pet(animal_id="a_001"):
    return Animal(animal_id=animal_id, category="pet")


def verified_location():
    return HouseholdLocation(
        address="1 Example Road",
        latitude=-37.8,
        longitude=145.0,
        verification_status="verified",
    )


def household(plan: HouseholdPlan | None = None, location=None):
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    if plan is not None:
        repository.save_plan(household_id, plan)
    if location is not None:
        repository.save_location(household_id, location)
    return repository, household_id


def service(repository, entries, spatial=None):
    return SafetyGuidanceService(repository, spatial or MockSpatialProvider(), entries)


def entry_ids(result) -> list[str]:
    return [shown.id for shown in result.entries]


def test_every_reviewed_entry_is_returned_whatever_the_household_has() -> None:
    repository, household_id = household()
    result = service(
        repository, [entry("general"), entry("pets", has_pets=True)]
    ).get(household_id)

    assert entry_ids(result) == ["general", "pets"]
    assert result.suggested_ids == ["general"]


def test_an_unreviewed_entry_is_in_neither_list() -> None:
    repository, household_id = household()
    result = service(
        repository, [entry("unreviewed", reviewed_by=None), entry("reviewed")]
    ).get(household_id)

    assert entry_ids(result) == ["reviewed"]
    assert result.suggested_ids == ["reviewed"]


def test_no_reviewed_entries_gives_empty_lists() -> None:
    repository, household_id = household()
    result = service(repository, [entry("draft", reviewed_by=None)]).get(household_id)

    assert result.entries == []
    assert result.suggested_ids == []


def test_an_entry_has_the_fields_shown_to_the_user() -> None:
    repository, household_id = household()
    shown = service(repository, [entry("general")]).get(household_id).entries[0]

    assert shown.model_dump(mode="json") == {
        "id": "general",
        "question": "Question general?",
        "answer": "Answer.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
    }


def test_questions_keep_the_order_of_the_content_file() -> None:
    repository, household_id = household()
    result = service(repository, [entry("second"), entry("first")]).get(household_id)

    assert entry_ids(result) == ["second", "first"]
    assert result.suggested_ids == ["second", "first"]


def test_tailored_questions_come_first_and_the_list_is_capped_at_six() -> None:
    repository, household_id = household(HouseholdPlan(animals=[pet()]))
    entries = [entry(f"general-{n}") for n in range(1, 6)] + [
        entry("pets-1", has_pets=True),
        entry("pets-2", has_pets=True),
    ]

    result = service(repository, entries).get(household_id)

    assert result.suggested_ids == [
        "pets-1",
        "pets-2",
        "general-1",
        "general-2",
        "general-3",
        "general-4",
    ]


def test_at_most_four_tailored_questions_leave_room_for_general_ones() -> None:
    repository, household_id = household(HouseholdPlan(animals=[pet()]))
    entries = [entry(f"pets-{n}", has_pets=True) for n in range(1, 6)] + [
        entry(f"general-{n}") for n in range(1, 4)
    ]

    result = service(repository, entries).get(household_id)

    assert result.suggested_ids == [
        "pets-1",
        "pets-2",
        "pets-3",
        "pets-4",
        "general-1",
        "general-2",
    ]


def test_a_household_with_no_plan_is_offered_only_general_questions() -> None:
    repository, household_id = household()
    result = service(
        repository, [entry("general"), entry("pets", has_pets=True)]
    ).get(household_id)

    assert result.suggested_ids == ["general"]
    assert result.location_conditions_applied is False


def test_mobility_support_suggests_its_question() -> None:
    repository, household_id = household(HouseholdPlan(members=[member(mobility=True)]))
    result = service(repository, [entry("support", has_mobility_support=True)]).get(household_id)

    assert result.suggested_ids == ["support"]


def test_no_mobility_support_does_not_suggest_its_question() -> None:
    repository, household_id = household(HouseholdPlan(members=[member()]))
    result = service(repository, [entry("support", has_mobility_support=True)]).get(household_id)

    assert result.suggested_ids == []


def test_pets_and_livestock_suggest_different_questions() -> None:
    repository, household_id = household(HouseholdPlan(animals=[pet()]))
    result = service(
        repository,
        [entry("pets", has_pets=True), entry("livestock", has_livestock=True)],
    ).get(household_id)

    assert result.suggested_ids == ["pets"]


def test_a_question_with_two_conditions_needs_both() -> None:
    both = entry("both", has_pets=True, has_mobility_support=True)
    repository, household_id = household(
        HouseholdPlan(members=[member(mobility=True)], animals=[pet()])
    )
    other_repository, other_id = household(HouseholdPlan(animals=[pet()]))

    assert service(repository, [both]).get(household_id).suggested_ids == ["both"]
    assert service(other_repository, [both]).get(other_id).suggested_ids == []


def test_dependants_suggest_their_question() -> None:
    repository, household_id = household(HouseholdPlan(members=[member(dependant=True)]))
    result = service(repository, [entry("dependants", has_dependants=True)]).get(household_id)

    assert result.suggested_ids == ["dependants"]


def test_an_unanswered_transport_question_does_not_suggest_the_no_transport_question() -> None:
    repository, household_id = household(HouseholdPlan(has_private_transport=None))
    result = service(repository, [entry("walk", no_private_transport=True)]).get(household_id)

    assert result.suggested_ids == []


def test_saying_there_is_no_private_transport_suggests_its_question() -> None:
    repository, household_id = household(HouseholdPlan(has_private_transport=False))
    result = service(repository, [entry("walk", no_private_transport=True)]).get(household_id)

    assert result.suggested_ids == ["walk"]


def test_a_bushfire_prone_location_suggests_its_question() -> None:
    repository, household_id = household(location=verified_location())
    result = service(
        repository, [entry("property", in_bushfire_prone_area=True)]
    ).get(household_id)

    assert result.suggested_ids == ["property"]
    assert result.location_conditions_applied is True


def test_a_verified_location_outside_a_prone_area_does_not_suggest_its_question() -> None:
    repository, household_id = household(location=verified_location())
    result = service(
        repository, [entry("property", in_bushfire_prone_area=True)], NotProneSpatial()
    ).get(household_id)

    assert result.suggested_ids == []
    assert entry_ids(result) == ["property"]
    assert result.location_conditions_applied is True


def test_an_unverified_location_leaves_location_questions_unsuggested_and_says_so() -> None:
    unverified = HouseholdLocation(address="somewhere", verification_status="unverified")
    repository, household_id = household(location=unverified)
    result = service(
        repository,
        [entry("property", in_bushfire_prone_area=True), entry("general")],
    ).get(household_id)

    assert result.suggested_ids == ["general"]
    assert entry_ids(result) == ["property", "general"]
    assert result.location_conditions_applied is False


def test_a_failing_spatial_lookup_is_not_an_error() -> None:
    repository, household_id = household(location=verified_location())
    result = service(
        repository,
        [entry("property", in_bushfire_prone_area=True), entry("general")],
        FailingSpatial(),
    ).get(household_id)

    assert result.suggested_ids == ["general"]
    assert result.location_conditions_applied is False


def test_an_unknown_household_raises_not_found() -> None:
    with pytest.raises(HouseholdNotFound):
        service(InMemoryHouseholdRepository(), [entry("general")]).get("hh_missing")


def test_selecting_questions_does_not_change_the_saved_plan() -> None:
    repository, household_id = household(
        HouseholdPlan(members=[member(mobility=True)], animals=[pet()])
    )
    before = repository.get_plan(household_id).model_dump()

    service(repository, [entry("pets", has_pets=True)]).get(household_id)

    assert repository.get_plan(household_id).model_dump() == before


def test_plan_facts_of_an_empty_plan_is_empty() -> None:
    assert plan_facts(HouseholdPlan()) == set()
```

- [ ] **Step 3: Write the failing endpoint tests**

Replace `backend/tests/test_safety_guidance_endpoint.py` with:

```python
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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run (from `backend/`): `pytest tests/test_safety_guidance_content.py tests/test_safety_guidance_service.py tests/test_safety_guidance_endpoint.py -q`
Expected: collection errors, `ImportError: cannot import name 'load_entries'` (and `GuidanceEntryDefinition`, `get_safety_guidance_entries`).

- [ ] **Step 5: Rewrite the schema**

Replace `backend/app/schemas/safety_guidance.py` with:

```python
"""Content-file and response models for reviewed safety Q&A."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class GuidanceConditions(BaseModel):
    """Facts a household must have for a question to be suggested to it.

    A key that is present must be true; leaving a key out means the entry does not
    depend on it. Unknown keys are rejected so a typo cannot silently change who is
    offered a question.
    """

    model_config = ConfigDict(extra="forbid")

    has_dependants: Literal[True] | None = None
    has_mobility_support: Literal[True] | None = None
    has_pets: Literal[True] | None = None
    has_livestock: Literal[True] | None = None
    no_private_transport: Literal[True] | None = None
    in_bushfire_prone_area: Literal[True] | None = None

    def required(self) -> frozenset[str]:
        return frozenset(
            name
            for name in type(self).model_fields
            if getattr(self, name) is True
        )


# A name made of spaces would pass a bare min_length check and ship an unreviewed entry.
ReviewerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GuidanceEntryDefinition(BaseModel):
    """One question and its reviewed answer, as written in the content file."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=600)
    source_name: str = Field(min_length=1, max_length=60)
    source_url: str = Field(pattern=r"^https://\S+$")
    retrieved_on: date
    reviewed_by: ReviewerName | None = None
    applies_when: GuidanceConditions = Field(default_factory=GuidanceConditions)


class GuidanceEntry(BaseModel):
    """One entry as shown to a household."""

    id: str
    question: str
    answer: str
    source_name: str
    source_url: str
    retrieved_on: date


class SafetyGuidance(BaseModel):
    entries: list[GuidanceEntry]
    # Ids of the questions offered as buttons, tailored ones first.
    suggested_ids: list[str]
    # False when the bushfire-prone-area fact could not be resolved, so questions
    # that depend on it were not suggested rather than guessed.
    location_conditions_applied: bool
```

- [ ] **Step 6: Rewrite the content file**

Replace `backend/app/content/safety_guidance.json` with the following. Every entry is a summary in the team's words of the page named in `source_url`. All start with `reviewed_by: null`, so none is served until a second team member checks it against the live page and records their name.

```json
[
  {
    "id": "when-to-leave",
    "question": "When should I leave on a high-risk day?",
    "answer": "CFA advises leaving before any fire starts, by 10 am or the night before, on Extreme and Catastrophic fire danger days. Do not wait for smoke or flames. Check the Fire Danger Rating each day during bushfire season so you know what kind of day it is.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "leaving-late-danger",
    "question": "Why is leaving late so dangerous?",
    "answer": "CFA says many people who die in bushfires wait too long to leave and are trapped by radiant heat, smoke and embers. Leaving late can also put you on roads with thick smoke, closures or crashes. Leaving early gives you more time, more control and more choices about where to go and how to travel.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "too-late-to-leave",
    "question": "What if it is too late to leave?",
    "answer": "Leaving early is the plan; these are last resorts, not a plan. CFA lists a well-prepared house or building, a personal bushfire shelter, a Community Fire Refuge, a Neighbourhood Safer Place, a parked car in a clear area, or open ground such as a ploughed paddock, reserve or water body. Read CFA's full guidance before relying on any of them.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "stay-and-defend",
    "question": "Should I stay and defend my home?",
    "answer": "CFA does not recommend staying to defend a property and describes it as extremely dangerous. It advises planning to leave early instead.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "emergency-kit",
    "question": "What should I put in an emergency kit?",
    "answer": "CFA suggests a change of clothes and toiletries for each person, medicines and prescriptions, a first aid kit, identity and insurance documents, printed contact numbers, a battery-powered radio, a torch, phone chargers or a power bank, drinking water and easy-to-pack food. It also suggests pure wool blankets, which help protect from radiant heat. Keep the kit somewhere easy to reach and practise packing the car on a low-risk day.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/what-to-take-with-you",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "children-comfort",
    "question": "What should I pack for children?",
    "answer": "Alongside the practical items in the emergency kit, CFA suggests comfort items for children, such as a blanket, a special toy or card games.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/what-to-take-with-you",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_dependants": true }
  },
  {
    "id": "pets-plan",
    "question": "What about my pets?",
    "answer": "CFA says never to stay home or risk your life for a pet, and to leave early with pets on high-risk days. Arrange where your pet will go, such as friends, family, a kennel or a cattery, and confirm it in advance. Never return once a fire has started.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/pets-and-bushfires",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_pets": true }
  },
  {
    "id": "pet-kit",
    "question": "What should a pet kit include?",
    "answer": "CFA suggests food and water for several days, bowls and a tin opener, a carrier or crate, a backup collar and lead, a pet first-aid kit, about a week of any medication, medical and vaccination records, your vet's details and familiar bedding. Keep microchip and ID tag details up to date and practise loading pets into the car.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/pets-and-bushfires",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_pets": true }
  },
  {
    "id": "pets-relief-centres",
    "question": "Can I take my pet to a relief centre?",
    "answer": "CFA warns that Neighbourhood Safer Places and emergency relief centres are not designed to house pets and might not let them in, so arrange a place for your pet in advance.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/pets-and-bushfires",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_pets": true }
  },
  {
    "id": "extra-help-leave-early",
    "question": "Someone in my household needs extra help to move. When should we leave?",
    "answer": "CFA says people with mobility challenges, disabilities or caring responsibilities should plan to leave early and give themselves extra time to get ready.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_mobility_support": true }
  },
  {
    "id": "extra-support-plan",
    "question": "How do we plan for someone who needs extra support?",
    "answer": "CFA says people who need extra support should have a clear, workable bushfire plan and should not assume they will be evacuated. The plan should be practical, realistic and made with the person involved. CFA provides a template with room for backup plans and an emergency bag, such as mobility aids, communication devices, medical equipment and medications.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/planning-with-people-who-need-extra-support",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_mobility_support": true }
  },
  {
    "id": "property-prep",
    "question": "How do I get my property ready before the season?",
    "answer": "In early spring CFA suggests clearing gutters, sealing gaps and vents, storing fuels and chemicals away from the house and securing LPG tanks, moving woodpiles away, pruning shrubs and overhanging branches, marking water sources, and mowing about 10 metres of well-kept grass around the home. During the season keep grass trimmed and gutters clear.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/preparing-for-bushfire-season",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "in_bushfire_prone_area": true }
  },
  {
    "id": "extreme-day-home",
    "question": "What should I do around my home on Extreme or Catastrophic days?",
    "answer": "CFA suggests mowing the lawn, removing leaf piles and other combustible material, clearing gutters, moving doormats, outdoor furniture and potted plants away from the house, and checking that gas bottles are anchored with their valves facing away from the house.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/preparing-for-bushfire-season",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "in_bushfire_prone_area": true }
  }
]
```

- [ ] **Step 7: Rewrite the service**

Replace `backend/app/services/safety_guidance.py` with:

```python
"""Choose reviewed CFA question-and-answer entries for a household. Nothing here is generated."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter

from app.core.exceptions import (
    ExternalDataUnavailable,
    HouseholdNotFound,
    LocationNotFound,
    LocationNotVerified,
    PlanNotFound,
)
from app.providers.interfaces import SpatialProvider
from app.repositories.households import HouseholdRepository
from app.schemas.households import HouseholdPlan
from app.schemas.safety_guidance import (
    GuidanceEntry,
    GuidanceEntryDefinition,
    SafetyGuidance,
)
from app.services.context import HouseholdStaticContextResolver

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "safety_guidance.json"

# Up to four questions tailored to the household come first, then general ones, six
# in all. Tailored questions lead but cannot crowd out the general ones, such as
# when to leave.
MAX_SUGGESTED = 6
MAX_TAILORED = 4

_ENTRIES = TypeAdapter(list[GuidanceEntryDefinition])


def load_entries(path: Path = CONTENT_PATH) -> list[GuidanceEntryDefinition]:
    """Read and validate the content file, keeping its order as display order."""

    entries = _ENTRIES.validate_json(path.read_text(encoding="utf-8"))
    ids = [entry.id for entry in entries]
    duplicates = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate safety guidance ids: {', '.join(duplicates)}")
    return entries


# Loaded at import so an invalid content file stops the app from starting rather
# than failing on the first request.
DEFAULT_ENTRIES: list[GuidanceEntryDefinition] = load_entries()


def plan_facts(plan: HouseholdPlan) -> set[str]:
    """Condition names that are true of a saved plan."""

    facts: set[str] = set()
    if any(member.is_dependant for member in plan.members):
        facts.add("has_dependants")
    if any(member.mobility_support_required for member in plan.members):
        facts.add("has_mobility_support")
    if any(animal.category == "pet" for animal in plan.animals):
        facts.add("has_pets")
    if any(animal.category == "livestock" for animal in plan.animals):
        facts.add("has_livestock")
    # Only an explicit "no": an unanswered question is not an answer.
    if plan.has_private_transport is False:
        facts.add("no_private_transport")
    return facts


class SafetyGuidanceService:
    """Return every reviewed entry and the questions to offer this household.

    Deterministic and read-only: it derives facts, compares them with each entry's
    conditions, and returns the result. It does not write to the plan and does not
    call a model. Conditions only choose which questions are *suggested*; every
    reviewed entry stays available, so a household with no pets can still read the
    pet answers.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        entries: Sequence[GuidanceEntryDefinition] | None = None,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.entries = DEFAULT_ENTRIES if entries is None else list(entries)

    def get(self, household_id: str) -> SafetyGuidance:
        if not self.repository.household_exists(household_id):
            raise HouseholdNotFound(f"Household '{household_id}' was not found.")

        facts: set[str] = set()
        try:
            facts |= plan_facts(self.repository.get_plan(household_id))
        except PlanNotFound:
            pass

        in_prone_area = self._in_bushfire_prone_area(household_id)
        if in_prone_area:
            facts.add("in_bushfire_prone_area")

        # A summary nobody has checked against its source is never shown.
        reviewed = [entry for entry in self.entries if entry.reviewed_by is not None]
        tailored = [
            entry.id
            for entry in reviewed
            if entry.applies_when.required() and entry.applies_when.required() <= facts
        ]
        general = [entry.id for entry in reviewed if not entry.applies_when.required()]
        suggested = (tailored[:MAX_TAILORED] + general)[:MAX_SUGGESTED]

        return SafetyGuidance(
            entries=[
                GuidanceEntry(
                    id=entry.id,
                    question=entry.question,
                    answer=entry.answer,
                    source_name=entry.source_name,
                    source_url=entry.source_url,
                    retrieved_on=entry.retrieved_on,
                )
                for entry in reviewed
            ],
            suggested_ids=suggested,
            location_conditions_applied=in_prone_area is not None,
        )

    def _in_bushfire_prone_area(self, household_id: str) -> bool | None:
        """True or False when the location is resolved, None when it is not."""

        try:
            _, context = HouseholdStaticContextResolver(
                self.repository, self.spatial_provider
            ).get_full(household_id)
        except (LocationNotFound, LocationNotVerified, ExternalDataUnavailable):
            return None
        return context.is_bushfire_prone_area
```

- [ ] **Step 8: Update the dependency and the route**

In `backend/app/core/dependencies.py`:

Replace the two imports
```python
from app.schemas.safety_guidance import GuidanceCardDefinition
from app.services.safety_guidance import DEFAULT_CARDS
```
with
```python
from app.schemas.safety_guidance import GuidanceEntryDefinition
from app.services.safety_guidance import DEFAULT_ENTRIES
```
and replace the function
```python
def get_safety_guidance_cards() -> list[GuidanceCardDefinition]:
    return DEFAULT_CARDS
```
with
```python
def get_safety_guidance_entries() -> list[GuidanceEntryDefinition]:
    return DEFAULT_ENTRIES
```

In `backend/app/api/routes/households.py`:

Change `get_safety_guidance_cards,` in the `from app.core.dependencies import (...)` list to `get_safety_guidance_entries,`.

Change `from app.schemas.safety_guidance import GuidanceCardDefinition, SafetyGuidance` to `from app.schemas.safety_guidance import GuidanceEntryDefinition, SafetyGuidance`.

Replace the whole `get_safety_guidance` handler with:

```python
@router.get(
    "/{household_id}/safety-guidance",
    response_model=SafetyGuidance,
)
def get_safety_guidance(
    household_id: str,
    repository: RepositoryDependency,
    spatial_provider: Annotated[
        SpatialProvider,
        Depends(get_spatial_provider),
    ],
    entries: Annotated[
        list[GuidanceEntryDefinition],
        Depends(get_safety_guidance_entries),
    ],
) -> SafetyGuidance:
    """Return the reviewed CFA question-and-answer entries and the questions to offer."""

    return SafetyGuidanceService(
        repository,
        spatial_provider,
        entries,
    ).get(household_id)
```

- [ ] **Step 9: Run the new tests, the full suite and the import check**

Run (from `backend/`): `pytest tests/test_safety_guidance_content.py tests/test_safety_guidance_service.py tests/test_safety_guidance_endpoint.py -q`
Expected: 16 + 22 + 6 = 44 passed. (If the count differs because a test was added or removed while transcribing, every test must still pass; do not edit a test to make the number match.)

Run: `pytest -q`
Expected: the whole suite passes, with `tests/test_mysql_repository.py` skipped.

Run: `APP_DATA_MODE=mock python -c "from app.main import app"`
Expected: no output and exit code 0.

- [ ] **Step 10: Update the contract**

In `docs/iteration1-integration-contract.md`:

Replace the endpoint table row beginning ``| `GET /households/{household_id}/safety-guidance` |`` with:

```markdown
| `GET /households/{household_id}/safety-guidance` | Return the reviewed CFA question-and-answer entries and the questions to offer this household. Read-only, no model call. Always `200` for a known household. |
```

Replace the whole `## Safety guidance` section (everything between that heading and `## Frontend contract`) with:

```markdown
## Safety guidance

Safety guidance is a set of short question-and-answer entries written and reviewed by the team, each a summary of one CFA page with a link to it. The service chooses which questions to offer; it does not generate advice, call a model, or write to the plan.

- `entries` is every reviewed entry, in the order of `backend/app/content/safety_guidance.json`, whatever the household. An entry with no `reviewed_by` is never returned. The browser answers a tapped question from this list.
- `suggested_ids` is at most six ids of the questions to offer as buttons: first up to four entries tailored to the household, then general entries, each in file order. An entry is tailored when it has conditions and all of them hold. Conditions come from the saved plan (`has_dependants`, `has_mobility_support`, `has_pets`, `has_livestock`, `no_private_transport`) and the cached bushfire-prone-area flag (`in_bushfire_prone_area`). `no_private_transport` requires an explicit `has_private_transport: false`. Conditions never stop an entry being returned in `entries`.
- A household with no saved plan is offered the general entries.
- If the location is missing or unverified, or the spatial lookup fails, entries that depend on `in_bushfire_prone_area` are not suggested and `location_conditions_applied` is `false`. The condition is not guessed. The flag is `false` for any of those three causes; the frontend tells them apart using the household's own location state.
- Response: `{ "entries": [{ "id", "question", "answer", "source_name", "source_url", "retrieved_on" }], "suggested_ids": ["..."], "location_conditions_applied": boolean }`. `retrieved_on` is an ISO date (`YYYY-MM-DD`) recording when a person checked the entry against its source page; it is never refreshed automatically.
```

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas/safety_guidance.py backend/app/content/safety_guidance.json backend/app/services/safety_guidance.py backend/app/core/dependencies.py backend/app/api/routes/households.py backend/tests/test_safety_guidance_content.py backend/tests/test_safety_guidance_service.py backend/tests/test_safety_guidance_endpoint.py docs/iteration1-integration-contract.md
git commit -m "feat(backend): turn safety guidance into short reviewed Q&A entries"
```

---

### Task 2: Frontend store and fixed copy

**Files:**
- Rewrite: `frontend/src/stores/safetyGuidance.js`
- Rewrite: `frontend/tests/safetyGuidanceStore.test.js`
- Create: `frontend/src/utils/safetyGuidanceCopy.js`
- Create: `frontend/tests/safetyGuidanceCopy.test.js`

**Interfaces:**
- Consumes: `api.getSafetyGuidance(householdId)` returning `{ entries, suggested_ids, location_conditions_applied }` from Task 1. `api.getSafetyGuidance` itself is unchanged.
- Produces:
  - `useSafetyGuidanceStore()` with refs `entries`, `suggestedIds`, `locationConditionsApplied`, `messages`, `status` (`'idle' | 'loading' | 'success' | 'error'`), `error`; computeds `entriesById` (object keyed by id) and `suggested` (array of entries, in `suggestedIds` order, skipping unknown ids); functions `load(householdId)`, `loadFor(resolveHouseholdId)`, `ask(entryId) -> boolean`, `reset()`
  - A message is `{ id: number, role: 'user', text: string }` or `{ id: number, role: 'assistant', entryId: string }`
  - `SAFETY_NOTICE`, `EMPTY_MESSAGE` string constants

- [ ] **Step 1: Write the failing tests**

Replace `frontend/tests/safetyGuidanceStore.test.js` with:

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../src/api/client.js'
import { useSafetyGuidanceStore } from '../src/stores/safetyGuidance.js'

const entry = (id) => ({
  id,
  question: `Question ${id}?`,
  answer: 'Answer.',
  source_name: 'CFA',
  source_url: 'https://www.cfa.vic.gov.au/example',
  retrieved_on: '2026-10-05',
})

const response = (ids, suggested = ids, applied = true) => ({
  entries: ids.map(entry),
  suggested_ids: suggested,
  location_conditions_applied: applied,
})

function mockApi(context, method, replacement) {
  const original = api[method]
  api[method] = replacement
  context.after(() => { api[method] = original })
}

test('guidance loads through the backend API', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async (id) => {
    assert.equal(id, 'hh_1')
    return response(['a', 'b', 'c'], ['b', 'a'])
  })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries.map((item) => item.id), ['a', 'b', 'c'])
  assert.deepEqual(store.suggested.map((item) => item.id), ['b', 'a'])
  assert.equal(store.locationConditionsApplied, true)
})

test('a suggested id that is not among the entries is skipped', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a'], ['missing', 'a']))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.deepEqual(store.suggested.map((item) => item.id), ['a'])
})

test('an empty response is a success, not an error', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response([], [], false))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries, [])
  assert.deepEqual(store.suggested, [])
  assert.equal(store.locationConditionsApplied, false)
})

test('a failed request leaves an error and nothing to show', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => { throw new Error('boom') })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'error')
  assert.deepEqual(store.entries, [])
  assert.match(store.error, /could not be loaded/i)
})

test('loading without a household does not call the API', async (context) => {
  setActivePinia(createPinia())
  let called = false
  mockApi(context, 'getSafetyGuidance', async () => { called = true; return response([]) })
  const store = useSafetyGuidanceStore()

  await store.load(null)

  assert.equal(called, false)
  assert.equal(store.status, 'idle')
})

test('a slow response for an earlier household does not overwrite a later one', async (context) => {
  setActivePinia(createPinia())
  let releaseFirst
  const first = new Promise((resolve) => { releaseFirst = resolve })
  mockApi(context, 'getSafetyGuidance', async (id) => {
    if (id === 'hh_old') {
      await first
      return response(['old'], ['old'], false)
    }
    return response(['new'], ['new'], true)
  })
  const store = useSafetyGuidanceStore()

  const oldLoad = store.load('hh_old')
  await store.load('hh_new')
  releaseFirst()
  await oldLoad

  assert.deepEqual(store.entries.map((item) => item.id), ['new'])
  assert.equal(store.locationConditionsApplied, true)
})

test('loadFor resolves the household first, so a first-time visitor still gets guidance', async (context) => {
  setActivePinia(createPinia())
  let requested = null
  mockApi(context, 'getSafetyGuidance', async (id) => { requested = id; return response(['a']) })
  const store = useSafetyGuidanceStore()

  await store.loadFor(async () => 'hh_created_just_now')

  assert.equal(requested, 'hh_created_just_now')
  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries.map((item) => item.id), ['a'])
})

test('loadFor reports an error when the household cannot be resolved', async (context) => {
  setActivePinia(createPinia())
  let called = false
  mockApi(context, 'getSafetyGuidance', async () => { called = true; return response([]) })
  const store = useSafetyGuidanceStore()

  await store.loadFor(async () => { throw new Error('no household') })

  assert.equal(called, false)
  assert.equal(store.status, 'error')
  assert.match(store.error, /could not be loaded/i)
})

test('asking a suggested question adds the question and then its reviewed answer', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a', 'b']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  const asked = store.ask('b')

  assert.equal(asked, true)
  assert.equal(store.messages.length, 2)
  assert.deepEqual(
    { role: store.messages[0].role, text: store.messages[0].text },
    { role: 'user', text: 'Question b?' },
  )
  assert.deepEqual(
    { role: store.messages[1].role, entryId: store.messages[1].entryId },
    { role: 'assistant', entryId: 'b' },
  )
})

test('asking an id that is not among the entries does nothing', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  const asked = store.ask('gone')

  assert.equal(asked, false)
  assert.deepEqual(store.messages, [])
})

test('asking the same question twice adds it twice, each message with its own id', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  store.ask('a')
  store.ask('a')

  assert.equal(store.messages.length, 4)
  assert.equal(new Set(store.messages.map((message) => message.id)).size, 4)
})

test('loading a household clears the earlier conversation', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')
  store.ask('a')

  await store.load('hh_2')

  assert.deepEqual(store.messages, [])
})

test('reset returns the store to its starting state', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')
  store.ask('a')

  store.reset()

  assert.equal(store.status, 'idle')
  assert.deepEqual(store.entries, [])
  assert.deepEqual(store.suggestedIds, [])
  assert.deepEqual(store.messages, [])
  assert.equal(store.error, null)
})
```

Create `frontend/tests/safetyGuidanceCopy.test.js`:

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { EMPTY_MESSAGE, SAFETY_NOTICE } from '../src/utils/safetyGuidanceCopy.js'

test('the fixed notice says this is not for emergencies and gives 000', () => {
  assert.match(SAFETY_NOTICE, /not for emergencies/i)
  assert.match(SAFETY_NOTICE, /\b000\b/)
})

test('the empty message does not promise guidance', () => {
  assert.match(EMPTY_MESSAGE, /no guidance/i)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `frontend/`): `node --test tests/safetyGuidanceStore.test.js tests/safetyGuidanceCopy.test.js`
Expected: the copy test fails with `Cannot find module '../src/utils/safetyGuidanceCopy.js'`; the store tests fail with `store.entries` undefined or `store.ask is not a function`.

- [ ] **Step 3: Write the copy constants**

Create `frontend/src/utils/safetyGuidanceCopy.js`:

```javascript
// Fixed text. It lives here, not in the content file, so an unreviewed or invalid
// content file can never hide the emergency notice. Check the wording against an
// official source when this changes.
export const SAFETY_NOTICE = 'This is not for emergencies. If you are in danger, call 000.'

export const EMPTY_MESSAGE = 'No guidance is available to show right now.'
```

- [ ] **Step 4: Rewrite the store**

Replace `frontend/src/stores/safetyGuidance.js` with:

```javascript
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client.js'

const LOAD_ERROR = 'Safety guidance could not be loaded. The rest of your overview is unaffected.'

export const useSafetyGuidanceStore = defineStore('safetyGuidance', () => {
  const entries = ref([])
  const suggestedIds = ref([])
  const locationConditionsApplied = ref(false)
  // The conversation lives here for the visit only. It is never sent to the server.
  const messages = ref([])
  const status = ref('idle')
  const error = ref(null)
  let revision = 0
  let nextMessageId = 1

  const entriesById = computed(() =>
    Object.fromEntries(entries.value.map((entry) => [entry.id, entry])),
  )
  // Suggested questions, in the server's order, ignoring any id that is not an entry.
  const suggested = computed(() =>
    suggestedIds.value.map((id) => entriesById.value[id]).filter(Boolean),
  )

  function clearContent() {
    entries.value = []
    suggestedIds.value = []
    locationConditionsApplied.value = false
    messages.value = []
    error.value = null
  }

  async function load(householdId) {
    const requestRevision = ++revision
    clearContent()
    if (!householdId) {
      status.value = 'idle'
      return
    }
    status.value = 'loading'
    try {
      const response = await api.getSafetyGuidance(householdId)
      if (requestRevision !== revision) return
      entries.value = response.entries ?? []
      suggestedIds.value = response.suggested_ids ?? []
      locationConditionsApplied.value = Boolean(response.location_conditions_applied)
      status.value = 'success'
    } catch {
      if (requestRevision !== revision) return
      status.value = 'error'
      error.value = LOAD_ERROR
    }
  }

  // A first-time visitor has no household yet; the caller supplies how to get one
  // (for example the household store's ensureHousehold) so the panel never loads
  // with a null id and stays blank.
  async function loadFor(resolveHouseholdId) {
    const startRevision = revision
    let householdId
    try {
      householdId = await resolveHouseholdId()
    } catch {
      if (startRevision !== revision) return
      clearContent()
      status.value = 'error'
      error.value = LOAD_ERROR
      return
    }
    if (startRevision !== revision) return
    await load(householdId)
  }

  // Show a reviewed answer. Nothing is requested: the entry is already here.
  function ask(entryId) {
    const entry = entriesById.value[entryId]
    if (!entry) return false
    messages.value.push({ id: nextMessageId++, role: 'user', text: entry.question })
    messages.value.push({ id: nextMessageId++, role: 'assistant', entryId: entry.id })
    return true
  }

  function reset() {
    revision += 1
    clearContent()
    status.value = 'idle'
  }

  return {
    entries,
    suggestedIds,
    locationConditionsApplied,
    messages,
    status,
    error,
    entriesById,
    suggested,
    load,
    loadFor,
    ask,
    reset,
  }
})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `node --test tests/safetyGuidanceStore.test.js tests/safetyGuidanceCopy.test.js`
Expected: 13 store tests + 2 copy tests pass.

Run: `npm test`
Expected: the whole frontend suite passes. (`SafetyGuidancePanel.vue` still reads the old store fields but has no test, so it does not fail here; Task 3 replaces it.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/safetyGuidance.js frontend/tests/safetyGuidanceStore.test.js frontend/src/utils/safetyGuidanceCopy.js frontend/tests/safetyGuidanceCopy.test.js
git commit -m "feat(frontend): hold safety Q&A entries and the visit's conversation in a store"
```

---

### Task 3: Chat panel

**Files:**
- Create: `frontend/src/components/overview/SafetyChatPanel.vue`
- Delete: `frontend/src/components/overview/SafetyGuidancePanel.vue`
- Modify: `frontend/src/views/OverviewView.vue`

**Interfaces:**
- Consumes: `useSafetyGuidanceStore` from Task 2 (`entries`, `suggested`, `messages`, `entriesById`, `locationConditionsApplied`, `status`, `error`, `loadFor`, `ask`); `SAFETY_NOTICE`, `EMPTY_MESSAGE`; existing `isStale` (`utils/guidanceFreshness.js`) and `locationNote` (`utils/safetyGuidanceNote.js`); `useHouseholdStore().ensureHousehold`; `useLocalContextStore().canLoadContext` and `.location`.
- Produces: `<SafetyChatPanel />`, mounted in the overview.

- [ ] **Step 1: Write the panel**

Create `frontend/src/components/overview/SafetyChatPanel.vue`:

```vue
<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useHouseholdStore } from '../../stores/household'
import { useLocalContextStore } from '../../stores/localContext'
import { useSafetyGuidanceStore } from '../../stores/safetyGuidance'
import { isStale } from '../../utils/guidanceFreshness'
import { EMPTY_MESSAGE, SAFETY_NOTICE } from '../../utils/safetyGuidanceCopy'
import { locationNote } from '../../utils/safetyGuidanceNote'
import ErrorState from '../common/ErrorState.vue'
import LoadingState from '../common/LoadingState.vue'

const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()
const store = useSafetyGuidanceStore()
const conversation = ref(null)

const note = computed(() =>
  locationNote({
    applied: store.locationConditionsApplied,
    locationVerified: Boolean(localContextStore.canLoadContext(localContextStore.location)),
  }),
)

function readOn(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function load() {
  return store.loadFor(() => householdStore.ensureHousehold())
}

// Keep the newest answer in view without moving the rest of the page.
watch(
  () => store.messages.length,
  async () => {
    await nextTick()
    conversation.value?.lastElementChild?.scrollIntoView?.({ block: 'nearest' })
  },
)

onMounted(load)
</script>

<template>
  <section class="card safety-chat" aria-labelledby="safety-chat-title">
    <h2 id="safety-chat-title" class="card-title">Safety guidance</h2>
    <p class="notice" role="note"><strong>{{ SAFETY_NOTICE }}</strong></p>
    <p class="intro">
      Pick a question to see what the Country Fire Authority advises. Answers are summarised by the FIREBREAK team
      and checked against CFA's pages. They are advice to read, not a forecast.
    </p>

    <LoadingState v-if="store.status === 'loading'" message="Loading safety guidance..." />
    <ErrorState v-else-if="store.status === 'error'" :message="store.error" @retry="load" />

    <template v-else-if="store.status === 'success'">
      <p v-if="!store.entries.length" class="empty">{{ EMPTY_MESSAGE }}</p>

      <template v-else>
        <div
          v-if="store.messages.length"
          ref="conversation"
          class="conversation"
          role="log"
          aria-live="polite"
        >
          <template v-for="message in store.messages" :key="message.id">
            <div v-if="message.role === 'user'" class="message user">
              <p class="bubble">{{ message.text }}</p>
            </div>
            <div v-else-if="store.entriesById[message.entryId]" class="message assistant">
              <div class="bubble">
                <p>{{ store.entriesById[message.entryId].answer }}</p>
                <p class="source">
                  Source:
                  <a :href="store.entriesById[message.entryId].source_url" target="_blank" rel="noopener noreferrer">{{
                    store.entriesById[message.entryId].source_name
                  }}</a>
                  · checked against the source page on {{ readOn(store.entriesById[message.entryId].retrieved_on) }}
                </p>
                <p v-if="isStale(store.entriesById[message.entryId].retrieved_on)" class="stale" role="note">
                  This was last checked more than six months ago. Please read the linked page for the latest advice.
                </p>
              </div>
            </div>
          </template>
        </div>

        <p class="suggestions-label">Suggested questions</p>
        <div class="chips">
          <button
            v-for="entry in store.suggested"
            :key="entry.id"
            class="chip"
            type="button"
            @click="store.ask(entry.id)"
          >
            {{ entry.question }}
          </button>
        </div>

        <p v-if="note === 'verify'" class="note">
          Add and verify your household location to see guidance for bushfire-prone areas.
        </p>
        <p v-else-if="note === 'unavailable'" class="note">
          Guidance for bushfire-prone areas could not be checked right now. Try again later.
        </p>

        <details class="all-guidance">
          <summary>Read all guidance</summary>
          <article v-for="entry in store.entries" :key="entry.id" class="guidance-entry">
            <h3>{{ entry.question }}</h3>
            <p class="body">{{ entry.answer }}</p>
            <p class="source">
              Source:
              <a :href="entry.source_url" target="_blank" rel="noopener noreferrer">{{ entry.source_name }}</a>
              · checked against the source page on {{ readOn(entry.retrieved_on) }}
            </p>
            <p v-if="isStale(entry.retrieved_on)" class="stale" role="note">
              This was last checked more than six months ago. Please read the linked page for the latest advice.
            </p>
          </article>
        </details>
      </template>
    </template>
  </section>
</template>

<style scoped>
.safety-chat { margin-top: 1.25rem; }
.notice { margin-top: 0.5rem; }
.intro, .empty, .note { color: var(--color-text-muted); margin-top: 0.5rem; }
.conversation { display: grid; gap: 0.6rem; margin-top: 1rem; max-height: 22rem; overflow-y: auto; }
.message { display: flex; }
.message.user { justify-content: flex-end; }
.bubble { border: 1px solid var(--color-summary-border); border-radius: 0.9rem; max-width: 92%; overflow-wrap: anywhere; padding: 0.65rem 0.85rem; }
.message.user .bubble { background: var(--color-accent-soft); color: var(--color-accent); }
.bubble p + p { margin-top: 0.5rem; }
.suggestions-label { color: var(--color-text-muted); font-size: 0.85rem; margin-top: 1rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.chip { background: var(--color-accent-soft); border: 1px solid var(--color-accent); border-radius: 999px; color: var(--color-accent); cursor: pointer; font: inherit; font-size: 0.9rem; padding: 0.4rem 0.85rem; text-align: left; }
.chip:hover, .chip:focus-visible { background: var(--color-accent); color: #fff; }
.source { color: var(--color-text-muted); font-size: 0.85rem; }
.stale { color: var(--color-text-muted); font-size: 0.85rem; font-style: italic; }
.note { font-size: 0.9rem; margin-top: 1rem; }
.all-guidance { border-top: 1px solid var(--color-summary-border); margin-top: 1.25rem; padding-top: 0.75rem; }
.all-guidance summary { cursor: pointer; font-weight: 600; }
.guidance-entry { border-top: 1px solid var(--color-summary-border); margin-top: 0.85rem; padding-top: 0.85rem; }
.guidance-entry h3 { font-size: 1rem; margin-bottom: 0.35rem; }
.guidance-entry .body { overflow-wrap: anywhere; }
.guidance-entry .source { margin-top: 0.4rem; }
</style>
```

- [ ] **Step 2: Replace the old panel in the overview**

In `frontend/src/views/OverviewView.vue`, change the import line
```javascript
import SafetyGuidancePanel from '../components/overview/SafetyGuidancePanel.vue'
```
to
```javascript
import SafetyChatPanel from '../components/overview/SafetyChatPanel.vue'
```
and change `<SafetyGuidancePanel />` in the template to `<SafetyChatPanel />`.

- [ ] **Step 3: Delete the old panel**

Run (from the repository root): `git rm frontend/src/components/overview/SafetyGuidancePanel.vue`
Expected: the file is removed. Then run `grep -rn "SafetyGuidancePanel" frontend/src` and expect no output.

- [ ] **Step 4: Run the frontend tests and build**

Run (from `frontend/`): `npm test`
Expected: the whole suite passes.

Run: `npm run build`
Expected: the build completes with no errors.

- [ ] **Step 5: Check it in the running app**

Run the backend (`APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock .venv/bin/uvicorn app.main:app --port 8000` from `backend/`) and the frontend (`npm run dev` from `frontend/`). To see answers, temporarily set `reviewed_by` to a name on at least four entries in `backend/app/content/safety_guidance.json` (include `when-to-leave`, `emergency-kit`, `pets-plan` and one `in_bushfire_prone_area` entry), restart the backend, and open `http://localhost:5173/overview`. Confirm:

- The emergency notice is visible at all times: while loading, with the backend stopped (error state), and with every entry unreviewed (empty message, no suggested buttons).
- With reviewed entries and a new household, the suggested buttons are the general questions only.
- Tapping a question adds the user message, then the answer with a working CFA link, and the newest message scrolls into view.
- After saving a pet in **My Plan**, the pet question appears first among the buttons; a household with several matching entries still shows general questions after them.
- "Read all guidance" is collapsed on load, and opens to list every reviewed entry, including ones the household has no condition for.
- Setting one `retrieved_on` to a date more than six months ago shows the "last checked more than six months ago" note in both the chat answer and the full list.
- Narrow the window to phone width: the buttons wrap, nothing scrolls the page sideways.

Revert the temporary edits (`git checkout backend/app/content/safety_guidance.json`) before committing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/overview/SafetyChatPanel.vue frontend/src/views/OverviewView.vue
git commit -m "feat(frontend): replace the guidance card list with a Q&A chat panel"
```

(`git rm` already staged the deletion of `SafetyGuidancePanel.vue`, so it is part of this commit.)

---

## Before this ships to users

The code does not make the feature useful on its own. Until a team member other than the author compares each entry with its live CFA page and sets `reviewed_by` and `retrieved_on` in `backend/app/content/safety_guidance.json`, the panel shows the notice and an empty message. For the review:

- Check the timing in `when-to-leave` ("by 10 am or the night before") and the list in `too-late-to-leave` against the `when-to-leave` page. The drafts were written from summaries of the pages, not from a verbatim copy.
- `children-comfort` is suggested when a household has any dependant, because the plan does not record ages. A household with an older dependant would see "What should I pack for children?". Decide whether to keep that condition or leave the entry out of the suggestions until ages are recorded.
- Confirm the wording of the emergency notice in `frontend/src/utils/safetyGuidanceCopy.js` against an official source.
- Livestock and households without private transport have no entry yet; their conditions are accepted so entries can be added without code changes once source pages are chosen.
- The independent review compared the entries with the live CFA pages. Six entries were corrected and re-worded after it (`leaving-late-danger`, `too-late-to-leave`, `emergency-kit`, `pets-relief-centres`, `extra-help-leave-early`, `extreme-day-home`), but the reviewer should still check each entry against its page, in particular: the "by 10 am or the night before" timing in `when-to-leave`; "extremely dangerous" in `stay-and-defend`; the gas-bottle wording in `extreme-day-home`; and the groups of people named in `extra-help-leave-early`.
- `children-comfort` is offered to any household with a dependant; consider making it a general entry if that reads as a wrong guess.
- Phase 2 (typed questions answered by a model that returns ids only) is a separate plan.
