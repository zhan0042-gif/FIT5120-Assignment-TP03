# Safety Guidance Implementation Plan


**Goal:** Show each household a short list of reviewed CFA safety-guidance cards on `/overview`, chosen by deterministic rules over the saved plan and location context.

**Architecture:** A reviewed JSON content file ships inside `backend/app/content/`. A pure selection service matches each card's `applies_when` conditions against facts derived from the saved plan and the cached bushfire-prone-area flag, and a new read-only endpoint returns the matching cards. The frontend adds one API method, one Pinia store and one panel. No model is called, nothing is persisted, and there is no schema migration.

**Tech Stack:** FastAPI + Pydantic v2 (Python 3.12), pytest; Vue 3 + Pinia (plain JavaScript), Node's built-in test runner.

**Spec:** `docs/design/specs/2026-10-05-safety-guidance-design.md`

## Global Constraints

- Frontend is plain JavaScript, not TypeScript. Backend tests run from `backend/` with `pytest`; frontend tests run from `frontend/` with `npm test`.
- The endpoint is `GET /api/v1/households/{household_id}/safety-guidance`. Unknown household is `404`. It never returns an `unavailable` state, because the content is local.
- Card text is a summary in the team's own words with a link to the source page. It is never copied verbatim (the CFA pages carry "Copyright CFA (Country Fire Authority)").
- A card whose `reviewed_by` is `null` is never served.
- Allowed `applies_when` keys, and only these: `has_dependants`, `has_mobility_support`, `has_pets`, `has_livestock`, `no_private_transport`, `in_bushfire_prone_area`. A key, when present, must be `true`.
- An invalid content file makes the app fail at import. The content file is part of the build.
- Never fabricate: when location context cannot be resolved, location-conditioned cards are omitted and `location_conditions_applied` is `false`. The condition is never guessed.
- The service never writes to the plan, calls a model, calls a provider other than the existing spatial provider through the existing resolver, or persists anything.
- UI copy is English and is never worded as prediction. The panel is visually and verbally distinct from the "Generated summary" of the rendezvous explanation.
- Conventional commits with a scope (`feat(backend): …`, `feat(frontend): …`, `docs: …`).
- Work on branch `feature/safety-guidance`.

## Review Focus

- A household that exists but has no saved plan and no location must get the general cards and a `200`, not a `404` or `500`. (Task 2, Task 3)
- A spatial lookup that fails or a location that is unverified must omit location cards and set `location_conditions_applied: false`, not return `503`. (Task 2)
- A card that matches the household but has `reviewed_by: null` must not appear. (Task 2)
- `has_private_transport` left unanswered (`None`) must not trigger `no_private_transport`; only an explicit `False` does. (Task 2)
- Pets and livestock must select different cards, and a card needing two conditions must need both. (Task 2)
- A slow response for a previous household must not overwrite the guidance for the current one. (Task 4)

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/schemas/safety_guidance.py` (create) | Content-file model with strict conditions, and the response models |
| `backend/app/content/safety_guidance.json` (create) | The reviewed card content |
| `backend/app/services/safety_guidance.py` (create) | Load and validate the content file; select cards for a household |
| `backend/app/core/dependencies.py` (modify) | `get_safety_guidance_cards` dependency |
| `backend/app/api/routes/households.py` (modify) | The `safety-guidance` route |
| `backend/tests/test_safety_guidance_content.py` (create) | Content file and loader validation |
| `backend/tests/test_safety_guidance_service.py` (create) | Selection rules |
| `backend/tests/test_safety_guidance_endpoint.py` (create) | HTTP behaviour |
| `docs/iteration1-integration-contract.md` (modify) | Document the endpoint |
| `frontend/src/api/client.js` (modify) | `getSafetyGuidance` |
| `frontend/src/stores/safetyGuidance.js` (create) | Request status and cards |
| `frontend/tests/safetyGuidanceStore.test.js` (create) | Store behaviour |
| `frontend/src/components/overview/SafetyGuidancePanel.vue` (create) | Render the cards |
| `frontend/src/views/OverviewView.vue` (modify) | Mount the panel |

---

### Task 1: Schemas, content file and loader

**Files:**
- Create: `backend/app/schemas/safety_guidance.py`
- Create: `backend/app/content/safety_guidance.json`
- Create: `backend/app/services/safety_guidance.py`
- Create: `backend/tests/test_safety_guidance_content.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `GuidanceConditions` with `required() -> frozenset[str]`
  - `GuidanceCardDefinition` with fields `id, title, body, source_name, source_url, retrieved_on: date, reviewed_by: str | None, applies_when: GuidanceConditions`
  - `SafetyGuidanceCard` (`id, title, body, source_name, source_url, retrieved_on`) and `SafetyGuidance` (`cards: list[SafetyGuidanceCard]`, `location_conditions_applied: bool`)
  - `load_cards(path: Path = CONTENT_PATH) -> list[GuidanceCardDefinition]` in `app/services/safety_guidance.py`
  - `CONTENT_PATH: Path`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_safety_guidance_content.py`:

```python
import json
from pathlib import Path

import pytest

from app.services.safety_guidance import CONTENT_PATH, load_cards


def _card(**overrides) -> dict:
    card = {
        "id": "example-card",
        "title": "Example",
        "body": "A short summary.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
        "reviewed_by": None,
        "applies_when": {},
    }
    card.update(overrides)
    return card


def _write(tmp_path: Path, cards: list[dict]) -> Path:
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(cards), encoding="utf-8")
    return path


def test_shipped_content_file_loads_in_display_order() -> None:
    cards = load_cards(CONTENT_PATH)

    assert [card.id for card in cards] == [
        "leave-early",
        "leave-early-extra-support",
        "last-resort-options",
        "emergency-kit",
        "pets-in-your-plan",
        "plan-with-extra-support",
        "prepare-your-property",
    ]


def test_every_shipped_card_names_a_source_page_and_date() -> None:
    for card in load_cards(CONTENT_PATH):
        assert card.source_url.startswith("https://")
        assert card.retrieved_on.isoformat() == "2026-10-05"


def test_a_valid_card_loads(tmp_path: Path) -> None:
    cards = load_cards(_write(tmp_path, [_card(applies_when={"has_pets": True})]))

    assert cards[0].applies_when.required() == frozenset({"has_pets"})


def test_an_empty_condition_object_applies_to_everyone(tmp_path: Path) -> None:
    cards = load_cards(_write(tmp_path, [_card()]))

    assert cards[0].applies_when.required() == frozenset()


def test_an_unknown_condition_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [_card(applies_when={"has_children": True})]))


def test_a_condition_set_to_false_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [_card(applies_when={"has_pets": False})]))


def test_a_missing_source_url_is_rejected(tmp_path: Path) -> None:
    card = _card()
    del card["source_url"]

    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [card]))


def test_a_source_url_that_is_not_https_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [_card(source_url="http://example.com")]))


def test_a_missing_retrieved_on_is_rejected(tmp_path: Path) -> None:
    card = _card()
    del card["retrieved_on"]

    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [card]))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        load_cards(_write(tmp_path, [_card(), _card(title="Other")]))


def test_an_id_that_is_not_a_slug_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_cards(_write(tmp_path, [_card(id="Not A Slug")]))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `pytest tests/test_safety_guidance_content.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.services.safety_guidance'`.

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/safety_guidance.py`:

```python
"""Content-file and response models for reviewed safety guidance."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GuidanceConditions(BaseModel):
    """Facts a household must have for a card to apply.

    A key that is present must be true; leaving a key out means the card does not
    depend on it. Unknown keys are rejected so a typo cannot silently widen who
    sees a card.
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


class GuidanceCardDefinition(BaseModel):
    """One card as written in the content file."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)
    source_name: str = Field(min_length=1, max_length=60)
    source_url: str = Field(pattern=r"^https://\S+$")
    retrieved_on: date
    reviewed_by: str | None = Field(default=None, min_length=1)
    applies_when: GuidanceConditions = Field(default_factory=GuidanceConditions)


class SafetyGuidanceCard(BaseModel):
    """One card as shown to a household."""

    id: str
    title: str
    body: str
    source_name: str
    source_url: str
    retrieved_on: date


class SafetyGuidance(BaseModel):
    cards: list[SafetyGuidanceCard]
    # False when the bushfire-prone-area fact could not be resolved, so cards that
    # depend on it were left out rather than guessed.
    location_conditions_applied: bool
```

- [ ] **Step 4: Write the content file**

Create `backend/app/content/safety_guidance.json`. Every card is a summary in the team's words of the page named in `source_url`. All cards start with `reviewed_by: null`, so none is served until a second team member checks it against the live page and records their name.

```json
[
  {
    "id": "leave-early",
    "title": "Leave early on Extreme and Catastrophic days",
    "body": "CFA says many people who die in bushfires wait too long to leave and are trapped by radiant heat, smoke and embers. On Extreme or Catastrophic fire danger days CFA advises leaving before any fire starts, by 10 am or the night before, rather than waiting for smoke or flames. Leaving early gives you more time, control and choices about when to go, where to go, what to bring, how to travel and who to tell. Check the Fire Danger Rating each day during bushfire season.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "leave-early-extra-support",
    "title": "Plan to leave early if someone needs extra help",
    "body": "CFA advises that people with mobility challenges, disabilities or caring responsibilities plan to leave early, and may need to go the night before an Extreme or Catastrophic day.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_mobility_support": true }
  },
  {
    "id": "last-resort-options",
    "title": "If it is too late to leave",
    "body": "Leaving early is the plan; the options below are last resorts, not a plan. CFA lists a well-prepared house or building, a personal bushfire shelter, a Community Fire Refuge, a Neighbourhood Safer Place, a parked car in a clear area, or open ground such as a ploughed paddock, reserve or water body. Leaving late risks being caught on roads with thick smoke and possible closures or crashes. CFA does not recommend staying to defend a property and describes it as extremely dangerous. Read CFA's full guidance before relying on any of these.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/when-to-leave",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "emergency-kit",
    "title": "Pack an emergency kit before fire season",
    "body": "CFA suggests packing a kit in autumn or winter so you can leave quickly and cope with being away for a while. It includes a change of clothes and toiletries for each person, medicines and prescriptions, a first aid kit, identity and insurance documents, printed contact numbers, a battery-powered radio, a torch with spare batteries, phone chargers or a power bank, drinking water, easy-to-pack food, and pure wool blankets, which CFA notes help protect from radiant heat. If you have children, add comfort items such as a blanket or a special toy. Keep the kit somewhere easy to reach and practise packing the car on a low-risk day so everything and everyone fits.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/what-to-take-with-you",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": {}
  },
  {
    "id": "pets-in-your-plan",
    "title": "Include your pets in your plan",
    "body": "CFA says never to stay home or risk your life for a pet, and to leave early with pets on high-risk days; never return once a fire has started. Arrange in advance where your pet will go, such as friends, family, a kennel or a cattery, and confirm it with them. Pack a pet kit: food and water for several days, a carrier or crate, a backup collar and lead, medications, medical and vaccination records and your vet's details. Keep microchip and ID tag details up to date and practise loading pets into the car. CFA warns that Neighbourhood Safer Places and emergency relief centres are not designed to house pets and might not let them in.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/pets-and-bushfires",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_pets": true }
  },
  {
    "id": "plan-with-extra-support",
    "title": "Plan with people who need extra support",
    "body": "CFA says people who need extra support, including older adults, people with disabilities and people with health conditions, should have a clear, workable bushfire plan and should not assume they will be evacuated. Plans should be practical, realistic and made with the person involved. CFA provides a planning template with room for backup plans and for the contents of an emergency bag, such as mobility aids, communication devices, medical equipment and medications, and lists free programs and in-home visits for people at higher risk and their carers.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/planning-with-people-who-need-extra-support",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "has_mobility_support": true }
  },
  {
    "id": "prepare-your-property",
    "title": "Get your property ready before the season",
    "body": "In early spring CFA suggests clearing gutters, sealing gaps and vents, storing fuels and chemicals away from the house and securing LPG tanks, moving woodpiles away, pruning shrubs and overhanging branches, marking water sources, and mowing a clearing of about 10 metres of well-mown grass. During the season keep grass trimmed and gutters clear. Before Extreme or Catastrophic days CFA suggests removing leaf piles and combustible items, and moving doormats, outdoor furniture and potted plants away from the house.",
    "source_name": "CFA",
    "source_url": "https://www.cfa.vic.gov.au/fire-safety/your-fire-plan/preparing-for-bushfire-season",
    "retrieved_on": "2026-10-05",
    "reviewed_by": null,
    "applies_when": { "in_bushfire_prone_area": true }
  }
]
```

- [ ] **Step 5: Write the loader**

Create `backend/app/services/safety_guidance.py`:

```python
"""Select reviewed CFA guidance cards for a household. Nothing here is generated."""

from pathlib import Path

from pydantic import TypeAdapter

from app.schemas.safety_guidance import GuidanceCardDefinition

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "safety_guidance.json"

_CARDS = TypeAdapter(list[GuidanceCardDefinition])


def load_cards(path: Path = CONTENT_PATH) -> list[GuidanceCardDefinition]:
    """Read and validate the content file, keeping its order as display order."""

    cards = _CARDS.validate_json(path.read_text(encoding="utf-8"))
    ids = [card.id for card in cards]
    duplicates = sorted({card_id for card_id in ids if ids.count(card_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate safety guidance ids: {', '.join(duplicates)}")
    return cards
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_safety_guidance_content.py -v`
Expected: 11 passed.

- [ ] **Step 7: Correct the spec's file location and commit**

The spec was already updated to `backend/app/content/safety_guidance.json`. Commit everything together.

```bash
git add backend/app/schemas/safety_guidance.py backend/app/content/safety_guidance.json backend/app/services/safety_guidance.py backend/tests/test_safety_guidance_content.py docs/design/specs/2026-10-05-safety-guidance-design.md docs/design/plans/2026-10-05-safety-guidance.md
git commit -m "feat(backend): add safety guidance content schema and loader"
```

---

### Task 2: Card selection service

**Files:**
- Modify: `backend/app/services/safety_guidance.py`
- Create: `backend/tests/test_safety_guidance_service.py`

**Interfaces:**
- Consumes: `GuidanceCardDefinition`, `SafetyGuidance`, `SafetyGuidanceCard`, `load_cards`, `CONTENT_PATH` from Task 1; `HouseholdStaticContextResolver(repository, spatial_provider).get_full(household_id) -> (HouseholdLocation, HouseholdLocationContext)` from `app/services/context.py`; `HouseholdRepository.household_exists`, `get_plan`.
- Produces:
  - `DEFAULT_CARDS: list[GuidanceCardDefinition]` (loaded at import)
  - `plan_facts(plan: HouseholdPlan) -> set[str]`
  - `SafetyGuidanceService(repository, spatial_provider, cards=None)` with `get(household_id: str) -> SafetyGuidance`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_safety_guidance_service.py`:

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
from app.schemas.safety_guidance import GuidanceCardDefinition
from app.services.safety_guidance import SafetyGuidanceService, plan_facts


def card(card_id: str, reviewed_by: str | None = "Reviewer", **conditions):
    return GuidanceCardDefinition.model_validate(
        {
            "id": card_id,
            "title": card_id,
            "body": "Summary.",
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


def ids(result) -> list[str]:
    return [shown.id for shown in result.cards]


def test_a_household_without_a_plan_gets_only_the_general_cards() -> None:
    repository, household_id = household()
    service = SafetyGuidanceService(
        repository,
        MockSpatialProvider(),
        [card("general"), card("pets", has_pets=True)],
    )

    result = service.get(household_id)

    assert ids(result) == ["general"]
    assert result.location_conditions_applied is False


def test_cards_keep_the_order_of_the_content_file() -> None:
    repository, household_id = household()
    service = SafetyGuidanceService(
        repository,
        MockSpatialProvider(),
        [card("second"), card("first")],
    )

    assert ids(service.get(household_id)) == ["second", "first"]


def test_a_card_that_is_not_reviewed_is_never_returned() -> None:
    repository, household_id = household()
    service = SafetyGuidanceService(
        repository,
        MockSpatialProvider(),
        [card("unreviewed", reviewed_by=None), card("reviewed")],
    )

    assert ids(service.get(household_id)) == ["reviewed"]


def test_mobility_support_selects_its_card() -> None:
    plan = HouseholdPlan(members=[member(mobility=True)])
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("support", has_mobility_support=True)]
    )

    assert ids(service.get(household_id)) == ["support"]


def test_no_mobility_support_leaves_its_card_out() -> None:
    plan = HouseholdPlan(members=[member()])
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("support", has_mobility_support=True)]
    )

    assert ids(service.get(household_id)) == []


def test_pets_and_livestock_select_different_cards() -> None:
    plan = HouseholdPlan(animals=[Animal(animal_id="a_001", category="pet")])
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository,
        MockSpatialProvider(),
        [card("pets", has_pets=True), card("livestock", has_livestock=True)],
    )

    assert ids(service.get(household_id)) == ["pets"]


def test_a_card_with_two_conditions_needs_both() -> None:
    plan = HouseholdPlan(
        members=[member(mobility=True)],
        animals=[Animal(animal_id="a_001", category="pet")],
    )
    repository, household_id = household(plan)
    both = card("both", has_pets=True, has_mobility_support=True)
    only_pets = HouseholdPlan(animals=[Animal(animal_id="a_001", category="pet")])

    assert ids(SafetyGuidanceService(repository, MockSpatialProvider(), [both]).get(household_id)) == ["both"]

    other_repository, other_id = household(only_pets)
    assert ids(SafetyGuidanceService(other_repository, MockSpatialProvider(), [both]).get(other_id)) == []


def test_dependants_select_their_card() -> None:
    plan = HouseholdPlan(members=[member(dependant=True)])
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("dependants", has_dependants=True)]
    )

    assert ids(service.get(household_id)) == ["dependants"]


def test_an_unanswered_transport_question_does_not_select_the_no_transport_card() -> None:
    plan = HouseholdPlan(has_private_transport=None)
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("walk", no_private_transport=True)]
    )

    assert ids(service.get(household_id)) == []


def test_saying_there_is_no_private_transport_selects_its_card() -> None:
    plan = HouseholdPlan(has_private_transport=False)
    repository, household_id = household(plan)
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("walk", no_private_transport=True)]
    )

    assert ids(service.get(household_id)) == ["walk"]


def test_a_bushfire_prone_location_selects_its_card() -> None:
    repository, household_id = household(location=verified_location())
    service = SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("property", in_bushfire_prone_area=True)]
    )

    result = service.get(household_id)

    assert ids(result) == ["property"]
    assert result.location_conditions_applied is True


def test_a_verified_location_outside_a_prone_area_leaves_its_card_out() -> None:
    repository, household_id = household(location=verified_location())
    service = SafetyGuidanceService(
        repository, NotProneSpatial(), [card("property", in_bushfire_prone_area=True)]
    )

    result = service.get(household_id)

    assert ids(result) == []
    assert result.location_conditions_applied is True


def test_an_unverified_location_leaves_location_cards_out_and_says_so() -> None:
    unverified = HouseholdLocation(address="somewhere", verification_status="unverified")
    repository, household_id = household(location=unverified)
    service = SafetyGuidanceService(
        repository,
        MockSpatialProvider(),
        [card("property", in_bushfire_prone_area=True), card("general")],
    )

    result = service.get(household_id)

    assert ids(result) == ["general"]
    assert result.location_conditions_applied is False


def test_a_failing_spatial_lookup_is_not_an_error() -> None:
    repository, household_id = household(location=verified_location())
    service = SafetyGuidanceService(
        repository,
        FailingSpatial(),
        [card("property", in_bushfire_prone_area=True), card("general")],
    )

    result = service.get(household_id)

    assert ids(result) == ["general"]
    assert result.location_conditions_applied is False


def test_an_unknown_household_raises_not_found() -> None:
    service = SafetyGuidanceService(
        InMemoryHouseholdRepository(), MockSpatialProvider(), [card("general")]
    )

    with pytest.raises(HouseholdNotFound):
        service.get("hh_missing")


def test_selecting_cards_does_not_change_the_saved_plan() -> None:
    plan = HouseholdPlan(
        members=[member(mobility=True)],
        animals=[Animal(animal_id="a_001", category="pet")],
    )
    repository, household_id = household(plan)
    before = repository.get_plan(household_id).model_dump()

    SafetyGuidanceService(
        repository, MockSpatialProvider(), [card("pets", has_pets=True)]
    ).get(household_id)

    assert repository.get_plan(household_id).model_dump() == before


def test_plan_facts_of_an_empty_plan_is_empty() -> None:
    assert plan_facts(HouseholdPlan()) == set()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_safety_guidance_service.py -v`
Expected: collection error, `ImportError: cannot import name 'SafetyGuidanceService'`.

- [ ] **Step 3: Implement the service**

Replace the contents of `backend/app/services/safety_guidance.py` with:

```python
"""Select reviewed CFA guidance cards for a household. Nothing here is generated."""

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
    GuidanceCardDefinition,
    SafetyGuidance,
    SafetyGuidanceCard,
)
from app.services.context import HouseholdStaticContextResolver

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "safety_guidance.json"

_CARDS = TypeAdapter(list[GuidanceCardDefinition])


def load_cards(path: Path = CONTENT_PATH) -> list[GuidanceCardDefinition]:
    """Read and validate the content file, keeping its order as display order."""

    cards = _CARDS.validate_json(path.read_text(encoding="utf-8"))
    ids = [card.id for card in cards]
    duplicates = sorted({card_id for card_id in ids if ids.count(card_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate safety guidance ids: {', '.join(duplicates)}")
    return cards


# Loaded at import so an invalid content file stops the app from starting rather
# than failing on the first request.
DEFAULT_CARDS: list[GuidanceCardDefinition] = load_cards()


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
    """Choose which reviewed cards apply to a household.

    Deterministic and read-only: it derives facts, compares them with each card's
    conditions, and returns the matches in file order. It does not write to the
    plan and does not call a model.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        cards: Sequence[GuidanceCardDefinition] | None = None,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.cards = DEFAULT_CARDS if cards is None else list(cards)

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

        shown = [
            SafetyGuidanceCard(
                id=card.id,
                title=card.title,
                body=card.body,
                source_name=card.source_name,
                source_url=card.source_url,
                retrieved_on=card.retrieved_on,
            )
            for card in self.cards
            # A summary nobody has checked against its source is never shown.
            if card.reviewed_by is not None and card.applies_when.required() <= facts
        ]
        return SafetyGuidance(
            cards=shown,
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

- [ ] **Step 4: Run all safety guidance tests to verify they pass**

Run: `pytest tests/test_safety_guidance_service.py tests/test_safety_guidance_content.py -v`
Expected: 28 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/safety_guidance.py backend/tests/test_safety_guidance_service.py
git commit -m "feat(backend): select reviewed safety guidance cards for a household"
```

---

### Task 3: Endpoint, dependency and contract

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/api/routes/households.py`
- Modify: `docs/iteration1-integration-contract.md`
- Create: `backend/tests/test_safety_guidance_endpoint.py`

**Interfaces:**
- Consumes: `SafetyGuidanceService`, `DEFAULT_CARDS`, `GuidanceCardDefinition`, `SafetyGuidance` from Tasks 1 and 2.
- Produces: `get_safety_guidance_cards() -> list[GuidanceCardDefinition]` dependency; `GET /api/v1/households/{household_id}/safety-guidance` returning `SafetyGuidance`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_safety_guidance_endpoint.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository, get_safety_guidance_cards
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.safety_guidance import GuidanceCardDefinition


def _card(card_id: str, reviewed_by: str | None = "Reviewer", **conditions):
    return GuidanceCardDefinition.model_validate(
        {
            "id": card_id,
            "title": card_id.title(),
            "body": "Summary.",
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
    cards = [
        _card("general"),
        _card("pets", has_pets=True),
        _card("unreviewed", reviewed_by=None),
    ]
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_safety_guidance_cards] = lambda: cards
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def test_a_household_without_a_plan_gets_the_general_cards(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]

    response = client.get(f"/api/v1/households/{household_id}/safety-guidance")

    assert response.status_code == 200
    body = response.json()
    assert [card["id"] for card in body["cards"]] == ["general"]
    assert body["location_conditions_applied"] is False


def test_a_card_has_its_source_and_reading_date(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]

    card = client.get(f"/api/v1/households/{household_id}/safety-guidance").json()["cards"][0]

    assert card == {
        "id": "general",
        "title": "General",
        "body": "Summary.",
        "source_name": "CFA",
        "source_url": "https://www.cfa.vic.gov.au/example",
        "retrieved_on": "2026-10-05",
    }


def test_a_saved_plan_with_a_pet_adds_the_pet_card(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]
    client.put(
        f"/api/v1/households/{household_id}/plan",
        json={"animals": [{"animal_id": "a_001", "category": "pet"}]},
    )

    body = client.get(f"/api/v1/households/{household_id}/safety-guidance").json()

    assert [card["id"] for card in body["cards"]] == ["general", "pets"]


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
    assert set(response.json()) == {"cards", "location_conditions_applied"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_safety_guidance_endpoint.py -v`
Expected: collection error, `ImportError: cannot import name 'get_safety_guidance_cards'`.

- [ ] **Step 3: Add the dependency**

In `backend/app/core/dependencies.py`, add the imports after the existing `app.repositories.mysql` import and the function after `get_travel_route_client`.

Imports to add:

```python
from app.schemas.safety_guidance import GuidanceCardDefinition
from app.services.safety_guidance import DEFAULT_CARDS
```

Function to add at the end of the file:

```python
def get_safety_guidance_cards() -> list[GuidanceCardDefinition]:
    return DEFAULT_CARDS
```

- [ ] **Step 4: Add the route**

In `backend/app/api/routes/households.py`:

Add `get_safety_guidance_cards` to the `from app.core.dependencies import (...)` list.

Add these imports with the other `app.schemas` and `app.services` imports:

```python
from app.schemas.safety_guidance import GuidanceCardDefinition, SafetyGuidance
from app.services.safety_guidance import SafetyGuidanceService
```

Add this route directly after the `get_preparation_support` function (before `run_preparedness_test`):

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
    cards: Annotated[
        list[GuidanceCardDefinition],
        Depends(get_safety_guidance_cards),
    ],
) -> SafetyGuidance:
    """Return reviewed CFA guidance cards that apply to the saved plan."""

    return SafetyGuidanceService(
        repository,
        spatial_provider,
        cards,
    ).get(household_id)
```

- [ ] **Step 5: Run the endpoint tests and the full suite**

Run: `pytest tests/test_safety_guidance_endpoint.py -v`
Expected: 6 passed.

Run: `pytest`
Expected: the whole suite passes, with `tests/test_mysql_repository.py` skipped.

Run: `APP_DATA_MODE=mock python -c "from app.main import app"`
Expected: no output and exit code 0.

- [ ] **Step 6: Confirm the content file is not excluded from the container build**

Run (from the repository root): `git check-ignore backend/app/content/safety_guidance.json; ls .dockerignore backend/.dockerignore 2>/dev/null`
Expected: no output from `git check-ignore`. If a `.dockerignore` is listed, open it and confirm it does not match `*.json` or `backend/app/content`. The Dockerfile's `COPY backend/app ./app` then ships the file with no further change.

- [ ] **Step 7: Document the endpoint**

In `docs/iteration1-integration-contract.md`, add this row to the endpoint table directly after the `GET /households/{household_id}/preparation-support` row:

```markdown
| `GET /households/{household_id}/safety-guidance` | Return reviewed CFA guidance cards that apply to the saved plan. Read-only, no model call. Always `200` for a known household. |
```

Add this section directly after the "Preparation support and scenarios" section:

```markdown
## Safety guidance

Safety guidance is a set of cards written and reviewed by the team, each a summary of one CFA page with a link to it. The service selects cards; it does not generate advice, call a model, or write to the plan.

- A card applies when every condition in its `applies_when` is true. Conditions come from the saved plan (`has_dependants`, `has_mobility_support`, `has_pets`, `has_livestock`, `no_private_transport`) and the cached bushfire-prone-area flag (`in_bushfire_prone_area`). `no_private_transport` requires an explicit `has_private_transport: false`.
- A card with no `reviewed_by` is never returned.
- A household with no saved plan receives the cards that have no conditions.
- If the location is missing or unverified, or the spatial lookup fails, cards that depend on `in_bushfire_prone_area` are omitted and `location_conditions_applied` is `false`. The condition is not guessed.
- Cards are returned in the order of `backend/app/content/safety_guidance.json`.
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/dependencies.py backend/app/api/routes/households.py backend/tests/test_safety_guidance_endpoint.py docs/iteration1-integration-contract.md
git commit -m "feat(backend): add safety guidance endpoint"
```

---

### Task 4: Frontend API method and store

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/stores/safetyGuidance.js`
- Create: `frontend/tests/safetyGuidanceStore.test.js`

**Interfaces:**
- Consumes: `GET /households/{id}/safety-guidance` from Task 3.
- Produces:
  - `api.getSafetyGuidance(householdId)` returning `{ cards, location_conditions_applied }`
  - `useSafetyGuidanceStore()` with refs `cards`, `locationConditionsApplied`, `status` (`'idle' | 'loading' | 'success' | 'error'`), `error`, and functions `load(householdId)` and `reset()`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/safetyGuidanceStore.test.js`:

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../src/api/client.js'
import { useSafetyGuidanceStore } from '../src/stores/safetyGuidance.js'

const card = (id) => ({
  id,
  title: id,
  body: 'Summary.',
  source_name: 'CFA',
  source_url: 'https://www.cfa.vic.gov.au/example',
  retrieved_on: '2026-10-05',
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
    return { cards: [card('leave-early')], location_conditions_applied: true }
  })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.cards.map((item) => item.id), ['leave-early'])
  assert.equal(store.locationConditionsApplied, true)
})

test('an empty list is a success, not an error', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => ({ cards: [], location_conditions_applied: false }))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.cards, [])
  assert.equal(store.locationConditionsApplied, false)
})

test('a failed request leaves an error and no cards', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => { throw new Error('boom') })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'error')
  assert.deepEqual(store.cards, [])
  assert.match(store.error, /could not be loaded/i)
})

test('loading without a household does not call the API', async (context) => {
  setActivePinia(createPinia())
  let called = false
  mockApi(context, 'getSafetyGuidance', async () => { called = true; return { cards: [] } })
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
      return { cards: [card('old')], location_conditions_applied: false }
    }
    return { cards: [card('new')], location_conditions_applied: true }
  })
  const store = useSafetyGuidanceStore()

  const oldLoad = store.load('hh_old')
  await store.load('hh_new')
  releaseFirst()
  await oldLoad

  assert.deepEqual(store.cards.map((item) => item.id), ['new'])
  assert.equal(store.locationConditionsApplied, true)
})

test('reset returns the store to its starting state', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => ({ cards: [card('a')], location_conditions_applied: true }))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  store.reset()

  assert.equal(store.status, 'idle')
  assert.deepEqual(store.cards, [])
  assert.equal(store.error, null)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `frontend/`): `node --test tests/safetyGuidanceStore.test.js`
Expected: FAIL, `Cannot find module '../src/stores/safetyGuidance.js'`.

- [ ] **Step 3: Add the API method**

In `frontend/src/api/client.js`, add this entry to the `api` object directly after `getTravelRoutes`:

```javascript
  getSafetyGuidance: (householdId) =>
    request(`/households/${encodeURIComponent(householdId)}/safety-guidance`),

```

- [ ] **Step 4: Write the store**

Create `frontend/src/stores/safetyGuidance.js`:

```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'

export const useSafetyGuidanceStore = defineStore('safetyGuidance', () => {
  const cards = ref([])
  const locationConditionsApplied = ref(false)
  const status = ref('idle')
  const error = ref(null)
  let revision = 0

  async function load(householdId) {
    const requestRevision = ++revision
    cards.value = []
    locationConditionsApplied.value = false
    error.value = null
    if (!householdId) {
      status.value = 'idle'
      return
    }
    status.value = 'loading'
    try {
      const response = await api.getSafetyGuidance(householdId)
      if (requestRevision !== revision) return
      cards.value = response.cards ?? []
      locationConditionsApplied.value = Boolean(response.location_conditions_applied)
      status.value = 'success'
    } catch {
      if (requestRevision !== revision) return
      status.value = 'error'
      error.value = 'Safety guidance could not be loaded. The rest of your overview is unaffected.'
    }
  }

  function reset() {
    revision += 1
    cards.value = []
    locationConditionsApplied.value = false
    status.value = 'idle'
    error.value = null
  }

  return { cards, locationConditionsApplied, status, error, load, reset }
})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `node --test tests/safetyGuidanceStore.test.js`
Expected: 6 passing.

Run: `npm test`
Expected: every existing test still passes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/stores/safetyGuidance.js frontend/tests/safetyGuidanceStore.test.js
git commit -m "feat(frontend): load safety guidance through a store"
```

---

### Task 5: Overview panel

**Files:**
- Create: `frontend/src/components/overview/SafetyGuidancePanel.vue`
- Modify: `frontend/src/views/OverviewView.vue`

**Interfaces:**
- Consumes: `useSafetyGuidanceStore` from Task 4; `useHouseholdStore().householdId`.
- Produces: `<SafetyGuidancePanel />`, mounted in the overview.

- [ ] **Step 1: Write the panel**

Create `frontend/src/components/overview/SafetyGuidancePanel.vue`:

```vue
<script setup>
import { onMounted } from 'vue'
import { useHouseholdStore } from '../../stores/household'
import { useSafetyGuidanceStore } from '../../stores/safetyGuidance'
import ErrorState from '../common/ErrorState.vue'
import LoadingState from '../common/LoadingState.vue'

const householdStore = useHouseholdStore()
const store = useSafetyGuidanceStore()

function readOn(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function load() {
  return store.load(householdStore.householdId)
}

onMounted(load)
</script>

<template>
  <section class="card safety-guidance" aria-labelledby="safety-guidance-title">
    <h2 id="safety-guidance-title" class="card-title">Safety guidance</h2>
    <p class="intro">
      Guidance from the Country Fire Authority, summarised by the FIREBREAK team and chosen from your saved plan.
      It is advice to read, not a forecast. Always check the linked CFA page.
    </p>

    <LoadingState v-if="store.status === 'loading'" message="Loading safety guidance..." />
    <ErrorState v-else-if="store.status === 'error'" :message="store.error" @retry="load" />

    <template v-else-if="store.status === 'success'">
      <p v-if="!store.cards.length" class="empty">
        No guidance is available to show right now.
      </p>
      <article v-for="card in store.cards" :key="card.id" class="guidance-card">
        <h3>{{ card.title }}</h3>
        <p class="body">{{ card.body }}</p>
        <p class="source">
          Source:
          <a :href="card.source_url" target="_blank" rel="noopener noreferrer">{{ card.source_name }}</a>
          · read on {{ readOn(card.retrieved_on) }}
        </p>
      </article>
      <p v-if="!store.locationConditionsApplied" class="note">
        Add and verify your household location to see guidance for bushfire-prone areas.
      </p>
    </template>
  </section>
</template>

<style scoped>
.safety-guidance { margin-top: 1.25rem; }
.intro, .empty, .note { color: var(--color-text-muted); margin-top: 0.5rem; }
.guidance-card { border-top: 1px solid var(--color-summary-border); margin-top: 1rem; padding-top: 1rem; }
.guidance-card h3 { font-size: 1.05rem; margin-bottom: 0.4rem; }
.body { overflow-wrap: anywhere; }
.source { color: var(--color-text-muted); font-size: 0.85rem; margin-top: 0.5rem; }
.note { font-size: 0.9rem; margin-top: 1rem; }
</style>
```

- [ ] **Step 2: Mount it in the overview**

In `frontend/src/views/OverviewView.vue`:

Add this import with the other component imports (after the `PreparationSupportBanner` import):

```javascript
import SafetyGuidancePanel from '../components/overview/SafetyGuidancePanel.vue'
```

Add the panel directly after the closing `</div>` of `<div class="top-grid">` and before the `<LoadingState v-if="householdStore.planStatus === 'loading'" …>` line:

```vue
    <SafetyGuidancePanel />
```

- [ ] **Step 3: Run the frontend tests and build**

Run (from `frontend/`): `npm test`
Expected: every test passes.

Run: `npm run build`
Expected: the build completes with no errors.

- [ ] **Step 4: Check it in the running app**

Run the backend and frontend (`DATABASE_HOST=127.0.0.1 .venv/bin/uvicorn app.main:app --reload --port 8000` from `backend/`, `npm run dev` from `frontend/`), open `http://localhost:5173/overview`, and confirm:

- With every card still `reviewed_by: null`, the panel shows the heading, the introduction and "No guidance is available to show right now." and the rest of the overview is unaffected.
- Temporarily set `reviewed_by` to a name on `leave-early` and `prepare-your-property`, restart the backend, and reload. `leave-early` appears with a working CFA link and a "read on 5 October 2026" date. `prepare-your-property` appears only when the household has a verified location in a bushfire-prone area, and otherwise the note about adding a verified location is shown. Revert the temporary change before committing.
- Stopping the backend and reloading shows the error state with a retry that works once the backend is back.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/overview/SafetyGuidancePanel.vue frontend/src/views/OverviewView.vue
git commit -m "feat(frontend): show safety guidance on the overview"
```

---

## Before this ships to users

The code does not make the feature useful on its own. Until a team member other than the author compares each card with its live CFA page and sets `reviewed_by` in `backend/app/content/safety_guidance.json`, the panel is empty. For the review:

- Check the timing in `leave-early` ("by 10 am or the night before") and the list in `last-resort-options` against `when-to-leave`. The drafts were written from summaries of the pages, not from a verbatim copy.
- Confirm `retrieved_on` against the live page.
- Livestock and households without private transport have no card yet; `has_livestock` and `no_private_transport` conditions are accepted so cards can be added without code changes once source pages are chosen.
