import pytest

from app.core.config import build_external_providers
from app.core.exceptions import ExternalDataUnavailable
from app.providers.jev_judgement import DisabledJudgementClient
from app.providers.mock import MockJudgementClient
from app.schemas.voice import VoiceQuestion, VoiceState


def _state(transcript: str) -> VoiceState:
    return VoiceState(page="plan-builder", transcript=transcript)


def _pick(question_id: str, *options: str) -> VoiceQuestion:
    return VoiceQuestion(id=question_id, type="pick_one", options=list(options))


def _yes_no(question_id: str) -> VoiceQuestion:
    return VoiceQuestion(id=question_id, type="yes_no")


def _judge(transcript: str, question: VoiceQuestion):
    [answer] = MockJudgementClient().judge(_state(transcript), [question])
    return answer


def test_the_mock_picks_the_option_sharing_the_most_naming_words() -> None:
    answer = _judge(
        "primary transport is a van",
        _pick(
            "command",
            "go to Overview",
            "set Primary transport",
            "set Backup transport (backup 1)",
            "none of these",
        ),
    )
    assert answer.answer == "set Primary transport"
    assert answer.probability >= 0.85


def test_the_mock_prefers_the_phrase_the_user_actually_said_on_a_tie() -> None:
    # "go back" names the same thing as the plan builder's Back button; the
    # words "go back" were said, "press" was not.
    answer = _judge(
        "go back",
        _pick("command", "go back", "press Back, or say previous step", "none of these"),
    )
    assert answer.answer == "go back"
    assert answer.probability >= 0.85


def test_a_button_alias_counts_as_its_own_phrasing() -> None:
    answer = _judge(
        "next step",
        _pick("command", "press Continue, or say next step", "scroll down", "none of these"),
    )
    assert answer.answer == "press Continue, or say next step"


def test_a_possessive_names_the_person() -> None:
    answer = _judge(
        "Minh's relationship is parent",
        _pick(
            "command",
            "set Relationship to household (Minh)",
            "set Relationship to household (Lan)",
            "none of these",
        ),
    )
    assert answer.answer == "set Relationship to household (Minh)"


def test_the_mock_answers_none_when_nothing_matches() -> None:
    answer = _judge(
        "what a lovely day", _pick("command", "go to Overview", "none of these")
    )
    assert answer.answer == "none of these"


def test_an_unbroken_tie_is_never_confident() -> None:
    answer = _judge(
        "set the name",
        _pick("command", "fill in Name (member 1)", "fill in Name (member 2)", "none of these"),
    )
    assert answer.answer == "fill in Name (member 1)"
    assert answer.probability <= 0.6


def test_the_mock_takes_the_value_after_a_cue_word() -> None:
    answer = _judge(
        "name is Minh", _pick("span", "name", "name is", "is Minh", "Minh", "(none)")
    )
    assert answer.answer == "Minh"


def test_the_mock_finds_no_value_without_a_cue_word() -> None:
    answer = _judge("fill in the name", _pick("span", "fill", "the name", "(none)"))
    assert answer.answer == "(none)"


def test_stop_confirm_and_checked_read_the_transcript() -> None:
    assert _judge("never mind", _yes_no("stop")).answer == "yes"
    assert _judge("scroll to the top", _yes_no("stop")).answer == "no"
    assert _judge("yes please", _yes_no("confirm")).answer == "yes"
    assert _judge("no", _yes_no("confirm")).answer == "no"
    unclear = _judge("hmm", _yes_no("confirm"))
    assert unclear.probability < 0.5
    assert _judge("Minh is not a dependant", _yes_no("checked")).answer == "no"
    assert _judge("Minh is a dependant", _yes_no("checked")).answer == "yes"


def test_the_mock_understands_which_suggestion_was_named() -> None:
    options = (
        "1 first: 12 Smith St, Ballarat VIC 3350",
        "2 second: 12 Smith Rd, Sale VIC 3850",
        "none",
    )
    assert _judge("the second one", _pick("suggestion", *options)).answer == options[1]
    assert _judge("number one", _pick("suggestion", *options)).answer == options[0]
    assert _judge("none of them", _pick("suggestion", *options)).answer == "none"


def test_the_mock_is_deterministic_and_its_probabilities_are_real() -> None:
    questions = [
        _pick("command", "go to Fire Map", "scroll down", "none of these"),
        _pick("span", "fire", "fire map", "(none)"),
        _yes_no("checked"),
        _yes_no("stop"),
    ]
    first = MockJudgementClient().judge(_state("go to fire map"), questions)
    second = MockJudgementClient().judge(_state("go to fire map"), questions)
    assert first == second
    assert all(0.0 <= answer.probability <= 1.0 for answer in first)
    assert [answer.id for answer in first] == ["command", "span", "checked", "stop"]


def test_the_disabled_judge_refuses() -> None:
    with pytest.raises(ExternalDataUnavailable):
        DisabledJudgementClient().judge(_state("go to fire map"), [_yes_no("stop")])


def test_mock_data_mode_always_uses_the_mock_judge(monkeypatch) -> None:
    monkeypatch.delenv("APP_VOICE_MODE", raising=False)
    assert isinstance(build_external_providers("mock").judgement, MockJudgementClient)


def test_live_data_mode_switches_voice_off_by_default(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.delenv("APP_VOICE_MODE", raising=False)
    assert isinstance(build_external_providers("live").judgement, DisabledJudgementClient)


def test_live_data_mode_can_use_the_mock_judge(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("APP_VOICE_MODE", "mock")
    assert isinstance(build_external_providers("live").judgement, MockJudgementClient)


def test_an_unknown_voice_mode_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("APP_VOICE_MODE", "jev")
    with pytest.raises(RuntimeError, match="APP_VOICE_MODE"):
        build_external_providers("live")
