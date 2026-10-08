import json

import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.mock import MockActionDecisionClient
from app.providers.openai_decisions import (
    DECISIONS_MODEL,
    DECISIONS_URL,
    DisabledActionDecisionClient,
    OpenAIDecisionsClient,
)
from app.services.voice_actions import ACTIONS, EMOTIONS


def _answer(choice, confidence, emotion=None, emotion_confidence=0.9) -> dict:
    answers = [
        {
            "type": "choice",
            "name": "action",
            "choice": choice,
            "probabilities": [],
            "confidence": confidence,
        }
    ]
    if emotion is not None:
        answers.append(
            {
                "type": "choice",
                "name": "emotion",
                "choice": emotion,
                "probabilities": [],
                "confidence": emotion_confidence,
            }
        )
    return {"answers": answers}


def _client(handler) -> OpenAIDecisionsClient:
    return OpenAIDecisionsClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_an_api_key_is_required() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIDecisionsClient(api_key=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIDecisionsClient(api_key="   ")


def test_the_request_asks_the_action_and_the_emotion_in_one_call() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_answer("read_weather", 0.9))

    _client(handler).decide("Show me the weather", "overview", "none")

    body = seen["body"]
    assert seen["url"] == DECISIONS_URL
    assert seen["auth"] == "Bearer test-key"
    assert body["model"] == DECISIONS_MODEL == "gpt-6-luna"
    assert "Show me the weather" in body["input"]
    action, emotion = body["questions"]
    assert action["type"] == "choice"
    assert action["name"] == "action"
    assert [choice["value"] for choice in action["choices"]] == list(ACTIONS)
    assert all(choice["description"] for choice in action["choices"])
    assert emotion["type"] == "choice"
    assert emotion["name"] == "emotion"
    assert [choice["value"] for choice in emotion["choices"]] == list(EMOTIONS)
    assert all(choice["description"] for choice in emotion["choices"])


def test_a_confident_known_action_is_returned() -> None:
    decision = _client(lambda r: httpx.Response(200, json=_answer("read_weather", 0.92))).decide(
        "weather", "overview", ""
    )

    assert decision.action == "read_weather"
    assert decision.confidence == 0.92


def test_low_confidence_becomes_none() -> None:
    decision = _client(lambda r: httpx.Response(200, json=_answer("read_weather", 0.3))).decide(
        "weather", "overview", ""
    )

    assert decision.action == "none"


def test_an_unknown_choice_becomes_none() -> None:
    decision = _client(lambda r: httpx.Response(200, json=_answer("delete_plan", 0.99))).decide(
        "x", "overview", ""
    )

    assert decision.action == "none"


@pytest.mark.parametrize(
    "payload",
    [
        {"answers": [{"type": "refusal", "name": "action"}]},
        {"answers": []},
        {"answers": [{"type": "predicate", "name": "action", "probability": 0.9}]},
        {"answers": [{"type": "choice", "name": "other", "choice": "read_weather", "confidence": 1}]},
    ],
)
def test_a_refusal_or_missing_answer_becomes_none(payload: dict) -> None:
    decision = _client(lambda r: httpx.Response(200, json=payload)).decide("x", "overview", "")

    assert decision.action == "none"


@pytest.mark.parametrize("payload", [{"answers": "nope"}, ["not", "an", "object"], {}])
def test_an_unreadable_response_is_unavailable(payload) -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(200, json=payload)).decide("x", "overview", "")


def test_http_errors_timeouts_and_bad_json_are_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(500)).decide("x", "overview", "")

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(timeout).decide("x", "overview", "")

    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(200, content=b"not json")).decide("x", "overview", "")


def test_the_disabled_client_is_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        DisabledActionDecisionClient().decide("x", "overview", "")


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("Show me the weather", "read_weather"),
        ("Open the fire history", "show_fire_history"),
        ("What is the fire danger today", "read_fire_danger"),
        ("How complete is my plan", "read_plan_completion"),
        ("Any road disruptions", "check_travel_disruptions"),
        ("Take me to the map", "open_fire_map"),
        ("Go to my plan", "open_plan"),
        ("What should I pack", "ask_safety_question"),
        ("Say that again", "repeat_last"),
        ("Go back", "go_back"),
    ],
)
def test_the_mock_matches_obvious_keywords(text: str, action: str) -> None:
    assert MockActionDecisionClient().decide(text, "overview", "").action == action


def test_the_mock_answers_none_for_everything_else() -> None:
    decision = MockActionDecisionClient().decide("Hello there", "overview", "")

    assert decision.action == "none"


def _decide(payload, text="x"):
    return _client(lambda r: httpx.Response(200, json=payload)).decide(text, "overview", "")


def test_the_emotion_is_returned_with_the_action() -> None:
    decision = _decide(_answer("read_weather", 0.9, "worried", 0.8))

    assert decision.action == "read_weather"
    assert decision.emotion == "worried"


def test_no_emotion_answer_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9)).emotion == "calm"


def test_a_low_confidence_emotion_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9, "urgent", 0.3)).emotion == "calm"


def test_an_emotion_outside_the_list_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9, "furious", 0.99)).emotion == "calm"


def test_a_refused_or_wrong_type_emotion_is_calm() -> None:
    refused = {
        "answers": [
            {"type": "choice", "name": "action", "choice": "read_weather", "confidence": 0.9},
            {"type": "refusal", "name": "emotion"},
        ]
    }
    wrong_type = {
        "answers": [
            {"type": "choice", "name": "action", "choice": "read_weather", "confidence": 0.9},
            {"type": "predicate", "name": "emotion", "probability": 0.9},
        ]
    }

    assert _decide(refused).emotion == "calm"
    assert _decide(wrong_type).emotion == "calm"


def test_the_emotion_survives_when_the_action_is_not_understood() -> None:
    decision = _decide(_answer("read_weather", 0.2, "frustrated", 0.9))

    assert decision.action == "none"
    assert decision.emotion == "frustrated"


@pytest.mark.parametrize(
    ("text", "emotion"),
    [
        ("I'm really scared, should we leave?", "worried"),
        ("Hurry, I need the fire danger now", "urgent"),
        ("Ugh, this is not working", "frustrated"),
        ("Haha, take me home koala", "playful"),
        ("Show me the weather", "calm"),
    ],
)
def test_the_mock_reads_obvious_feelings(text: str, emotion: str) -> None:
    assert MockActionDecisionClient().decide(text, "overview", "").emotion == emotion
