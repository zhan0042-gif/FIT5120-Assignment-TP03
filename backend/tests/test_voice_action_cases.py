import json
from pathlib import Path

from app.services.voice_actions import ACTIONS

FIXTURE = Path(__file__).parent / "fixtures" / "voice_action_cases.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text())["cases"]


def test_every_case_expects_an_action_in_the_closed_list() -> None:
    assert all(case["expected"] in ACTIONS for case in _cases())


def test_case_ids_are_unique_and_every_case_is_complete() -> None:
    cases = _cases()

    assert len({case["id"] for case in cases}) == len(cases) == 61
    assert all({"id", "cat", "page", "last", "text", "expected"} <= set(case) for case in cases)


def test_the_must_refuse_cases_all_expect_none() -> None:
    refuse = [case for case in _cases() if case["cat"] == "must_refuse"]

    assert len(refuse) == 12
    assert all(case["expected"] == "none" for case in refuse)
