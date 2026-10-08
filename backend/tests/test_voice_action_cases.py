import json
from pathlib import Path

from app.services.voice_actions import ACTIONS, EMOTIONS

FIXTURE = Path(__file__).parent / "fixtures" / "voice_action_cases.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text())["cases"]


def test_every_case_expects_an_action_in_the_closed_list() -> None:
    assert all(case["expected"] in ACTIONS for case in _cases())


def test_case_ids_are_unique_and_every_case_is_complete() -> None:
    cases = _cases()

    assert len({case["id"] for case in cases}) == len(cases) == 91
    assert all({"id", "cat", "page", "last", "text", "expected"} <= set(case) for case in cases)


def test_the_must_refuse_cases_all_expect_none() -> None:
    refuse = [case for case in _cases() if case["cat"] == "must_refuse"]

    assert len(refuse) == 15
    assert all(case["expected"] == "none" for case in refuse)


def test_alternative_answers_are_real_actions_on_the_same_page_as_the_expected_one() -> None:
    cases = _cases()
    marked = [case for case in cases if "also_ok" in case]

    assert marked, "the page-or-section overlaps should be marked"
    for case in marked:
        assert all(action in ACTIONS and action != "none" for action in case["also_ok"]), case["id"]
        # Only a navigation that lands on the same page is an acceptable alternative.
        assert case["expected"].startswith(("section_", "open_")), case["id"]
        assert all(action.startswith("open_") for action in case["also_ok"]), case["id"]


def test_emotion_labels_are_real_emotions_and_distress_is_never_playful() -> None:
    labelled = [case for case in _cases() if "emotion" in case]

    assert len(labelled) >= 10
    assert all(case["emotion"] in EMOTIONS for case in labelled)
    distressed = [case for case in _cases() if case.get("distress")]
    assert len(distressed) >= 3
    assert all(case["emotion"] in ("worried", "urgent") for case in distressed)
