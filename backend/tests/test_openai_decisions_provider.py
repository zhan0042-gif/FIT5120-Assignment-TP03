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
from app.services.voice_actions import ACTIONS


def _answer(choice, confidence) -> dict:
    return {
        "answers": [
            {
                "type": "choice",
                "name": "action",
                "choice": choice,
                "probabilities": [],
                "confidence": confidence,
            }
        ]
    }


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


def test_the_request_asks_one_choice_question_over_the_closed_list() -> None:
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
    (question,) = body["questions"]
    assert question["type"] == "choice"
    assert question["name"] == "action"
    assert [choice["value"] for choice in question["choices"]] == list(ACTIONS)
    assert all(choice["description"] for choice in question["choices"])


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
