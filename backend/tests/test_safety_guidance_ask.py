import logging

import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.safety_guidance import GuidanceEntryDefinition
from app.services.safety_guidance_ask import GuidanceAskService


def entry(entry_id: str, reviewed_by: str | None = "Reviewer", asked_as=None):
    return GuidanceEntryDefinition.model_validate(
        {
            "id": entry_id,
            "question": f"Question {entry_id}?",
            "answer": "Answer.",
            "source_name": "CFA",
            "source_url": "https://www.cfa.vic.gov.au/example",
            "retrieved_on": "2026-10-05",
            "reviewed_by": reviewed_by,
            "asked_as": asked_as or [],
        }
    )


class FixedRouter:
    def __init__(self, ids) -> None:
        self.ids = ids
        self.calls: list = []

    def route(self, question, catalogue):
        self.calls.append((question, list(catalogue)))
        return self.ids


class DownRouter:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, question, catalogue):
        self.calls += 1
        raise ExternalDataUnavailable("model is down")


class Limit:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[str] = []

    def allow(self, household_id: str) -> bool:
        self.calls.append(household_id)
        return self.allowed


ENTRIES = [entry("a"), entry("b"), entry("c")]


def ask(router, question="Is this ok?", entries=ENTRIES):
    return GuidanceAskService(router, entries).ask(question)


def test_a_returned_id_is_a_match() -> None:
    result = ask(FixedRouter(["b"]))

    assert result.status == "matched"
    assert result.entry_ids == ["b"]


def test_two_ids_keep_the_routers_order() -> None:
    assert ask(FixedRouter(["c", "a"])).entry_ids == ["c", "a"]


def test_more_than_two_ids_are_cut_to_two() -> None:
    assert ask(FixedRouter(["a", "b", "c"])).entry_ids == ["a", "b"]


def test_repeated_ids_are_removed_before_the_cut() -> None:
    assert ask(FixedRouter(["a", "a", "b"])).entry_ids == ["a", "b"]


def test_ids_that_are_not_in_the_catalogue_are_dropped() -> None:
    result = ask(FixedRouter(["invented", "b"]))

    assert result.entry_ids == ["b"]


def test_only_invented_ids_is_no_match() -> None:
    result = ask(FixedRouter(["invented"]))

    assert result.status == "no_match"
    assert result.entry_ids == []


def test_items_that_are_not_strings_are_ignored() -> None:
    result = ask(FixedRouter([None, 3, {"id": "a"}, "c"]))

    assert result.entry_ids == ["c"]


def test_no_ids_is_no_match() -> None:
    result = ask(FixedRouter([]))

    assert result.status == "no_match"
    assert result.entry_ids == []


def test_a_router_failure_is_unavailable() -> None:
    result = ask(DownRouter())

    assert result.status == "unavailable"
    assert result.entry_ids == []


def test_emergency_wording_never_reaches_the_router() -> None:
    router = FixedRouter(["a"])

    result = ask(router, "My house is on fire")

    assert result.status == "emergency"
    assert result.entry_ids == []
    assert router.calls == []


def test_the_router_sees_only_reviewed_entries_with_their_phrasings() -> None:
    router = FixedRouter([])
    entries = [
        entry("shown", asked_as=["Another way to ask?"]),
        entry("draft", reviewed_by=None),
    ]

    ask(router, "Is this ok?", entries)

    question, catalogue = router.calls[0]
    assert question == "Is this ok?"
    assert [item.id for item in catalogue] == ["shown"]
    assert catalogue[0].question == "Question shown?"
    assert catalogue[0].asked_as == ["Another way to ask?"]


def test_an_unreviewed_entry_cannot_be_matched_even_if_the_router_names_it() -> None:
    entries = [entry("shown"), entry("draft", reviewed_by=None)]

    result = ask(FixedRouter(["draft"]), entries=entries)

    assert result.status == "no_match"


def test_with_no_reviewed_entries_the_router_is_not_called() -> None:
    router = FixedRouter(["a"])

    result = ask(router, entries=[entry("draft", reviewed_by=None)])

    assert result.status == "no_match"
    assert router.calls == []


def test_the_question_text_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    secret = "zebra-unique-question-text 12 Example Street"

    ask(FixedRouter(["a"]), secret)
    ask(DownRouter(), secret)
    ask(FixedRouter(["a"]), "My house is on fire " + secret)

    assert "zebra-unique-question-text" not in caplog.text
    assert "Example Street" not in caplog.text


def test_a_refused_request_is_unavailable_and_the_router_is_not_called() -> None:
    router = FixedRouter(["a"])

    result = GuidanceAskService(router, ENTRIES, Limit(False)).ask("Is this ok?", "hh_1")

    assert result.status == "unavailable"
    assert result.entry_ids == []
    assert router.calls == []


def test_an_allowed_request_goes_through_and_names_the_household() -> None:
    router = FixedRouter(["a"])
    limit = Limit(True)

    result = GuidanceAskService(router, ENTRIES, limit).ask("Is this ok?", "hh_1")

    assert result.status == "matched"
    assert limit.calls == ["hh_1"]


def test_emergency_wording_is_answered_even_when_the_limit_is_used_up() -> None:
    router = FixedRouter(["a"])
    limit = Limit(False)

    result = GuidanceAskService(router, ENTRIES, limit).ask("My house is on fire", "hh_1")

    assert result.status == "emergency"
    assert router.calls == []
    assert limit.calls == []
