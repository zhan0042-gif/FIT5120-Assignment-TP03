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
