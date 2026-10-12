import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_action_decision_client,
    get_household_repository,
    get_live_session_client,
    get_live_session_rate_limit,
    get_voice_decision_rate_limit,
)
from app.core.exceptions import ExternalDataUnavailable
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.live import ActionDecision, LiveSessionRef, LiveSessionResponse, LiveTransport
from app.services.rate_limit import AskRateLimit


class Sessions:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def create(self, sdp: str) -> LiveSessionResponse:
        self.calls.append(sdp)
        if self.error:
            raise self.error
        return LiveSessionResponse(
            session=LiveSessionRef(id="live_1"), transport=LiveTransport(sdp="answer-sdp")
        )


class Decider:
    def __init__(self, action: str = "read_weather", confidence: float = 0.9, error: Exception | None = None, emotion: str = "calm") -> None:
        self.action = action
        self.confidence = confidence
        self.error = error
        self.emotion = emotion
        self.calls: list[tuple[str, str, str]] = []

    def decide(self, utterance: str, page: str, last_readout: str) -> ActionDecision:
        self.calls.append((utterance, page, last_readout))
        if self.error:
            raise self.error
        return ActionDecision(action=self.action, confidence=self.confidence, emotion=self.emotion)


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    sessions = Sessions()
    decider = Decider()
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_live_session_client] = lambda: sessions
    app.dependency_overrides[get_action_decision_client] = lambda: decider
    # Tests share one process, so give each its own generous limits.
    app.dependency_overrides[get_live_session_rate_limit] = lambda: AskRateLimit(per_household=1000, overall=1000)
    app.dependency_overrides[get_voice_decision_rate_limit] = lambda: AskRateLimit(per_household=1000, overall=1000)
    with TestClient(app) as client:
        household_id = client.post("/api/v1/households").json()["household_id"]
        yield client, sessions, decider, household_id
    app.dependency_overrides.clear()


def _sessions_url(household_id: str) -> str:
    return f"/api/v1/households/{household_id}/live/sessions"


def _decide_url(household_id: str) -> str:
    return f"/api/v1/households/{household_id}/live/decide"


def test_a_session_is_created_and_the_answer_is_returned(api) -> None:
    client, sessions, _, household_id = api

    response = client.post(_sessions_url(household_id), json={"sdp": "browser-offer"})

    assert response.status_code == 201
    assert response.json() == {
        "session": {"id": "live_1"},
        "transport": {"type": "webrtc", "sdp": "answer-sdp"},
    }
    assert sessions.calls == ["browser-offer"]


def test_the_offer_reaches_the_provider_exactly_as_sent_including_its_final_line_break(api) -> None:
    client, sessions, _, household_id = api
    # Every SDP line, the last one included, must end with CRLF or OpenAI rejects the
    # offer with invalid_offer. A real browser offer always ends this way.
    offer = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n"

    response = client.post(_sessions_url(household_id), json={"sdp": offer})

    assert response.status_code == 201
    assert sessions.calls == [offer]


def test_a_session_for_an_unknown_household_is_404_and_calls_nothing(api) -> None:
    client, sessions, _, _ = api

    response = client.post(_sessions_url("hh_missing"), json={"sdp": "offer"})

    assert response.status_code == 404
    assert sessions.calls == []


@pytest.mark.parametrize("body", [{}, {"sdp": ""}, {"sdp": "   "}, {"sdp": "x" * 65537}, {"sdp": "o", "extra": 1}])
def test_a_bad_session_body_is_422(api, body) -> None:
    client, sessions, _, household_id = api

    assert client.post(_sessions_url(household_id), json=body).status_code == 422
    assert sessions.calls == []


def test_a_provider_outage_on_session_creation_is_503(api) -> None:
    client, sessions, _, household_id = api
    sessions.error = ExternalDataUnavailable("down")

    assert client.post(_sessions_url(household_id), json={"sdp": "offer"}).status_code == 503


def test_session_creation_is_rate_limited_per_household(api) -> None:
    client, sessions, _, household_id = api
    limit = AskRateLimit(per_household=1, overall=1000)  # one shared instance, so it counts
    app.dependency_overrides[get_live_session_rate_limit] = lambda: limit

    assert client.post(_sessions_url(household_id), json={"sdp": "offer"}).status_code == 201
    second = client.post(_sessions_url(household_id), json={"sdp": "offer"})

    assert second.status_code == 429
    assert len(sessions.calls) == 1


def test_decide_returns_the_chosen_action_and_passes_the_labels(api) -> None:
    client, _, decider, household_id = api

    response = client.post(
        _decide_url(household_id),
        json={"utterance": "Show me the weather", "page": "overview", "last_readout": "fire history"},
    )

    assert response.status_code == 200
    assert response.json() == {"action": "read_weather", "confidence": 0.9, "emotion": "calm"}
    assert decider.calls == [("Show me the weather", "overview", "fire history")]


def test_decide_defaults_the_labels(api) -> None:
    client, _, decider, household_id = api

    client.post(_decide_url(household_id), json={"utterance": "hello"})

    assert decider.calls == [("hello", "", "")]


def test_decide_turns_an_unknown_action_into_none(api) -> None:
    client, _, decider, household_id = api
    decider.action = "delete_plan"
    decider.confidence = 0.99

    response = client.post(_decide_url(household_id), json={"utterance": "delete my plan"})

    assert response.json()["action"] == "none"


def test_decide_turns_low_confidence_into_none(api) -> None:
    client, _, decider, household_id = api
    decider.confidence = 0.3

    response = client.post(_decide_url(household_id), json={"utterance": "weather"})

    assert response.json()["action"] == "none"


def test_decide_answers_an_emergency_without_calling_the_provider(api) -> None:
    client, _, decider, household_id = api
    decider.error = ExternalDataUnavailable("down")
    limit = AskRateLimit(per_household=1, overall=1)  # one shared instance, so it counts
    app.dependency_overrides[get_voice_decision_rate_limit] = lambda: limit
    # Use up the limit first (this call reaches the failing provider and is a 503), so
    # the emergency call is shown to need neither the limit nor the provider.
    assert client.post(_decide_url(household_id), json={"utterance": "hello"}).status_code == 503

    response = client.post(
        _decide_url(household_id), json={"utterance": "The fire is coming, help me!"}
    )

    assert response.status_code == 200
    assert response.json() == {"action": "ask_safety_question", "confidence": 1.0, "emotion": "urgent"}
    assert [call[0] for call in decider.calls] == ["hello"]


@pytest.mark.parametrize(
    "body",
    [{}, {"utterance": ""}, {"utterance": "   "}, {"utterance": "x" * 301}, {"utterance": "a", "extra": 1}, {"utterance": "a", "page": "p" * 41}],
)
def test_a_bad_decide_body_is_422(api, body) -> None:
    client, _, decider, household_id = api

    assert client.post(_decide_url(household_id), json=body).status_code == 422
    assert decider.calls == []


def test_decide_for_an_unknown_household_is_404(api) -> None:
    client, _, decider, _ = api

    assert client.post(_decide_url("hh_missing"), json={"utterance": "weather"}).status_code == 404
    assert decider.calls == []


def test_a_provider_outage_on_decide_is_503(api) -> None:
    client, _, decider, household_id = api
    decider.error = ExternalDataUnavailable("down")

    assert client.post(_decide_url(household_id), json={"utterance": "weather"}).status_code == 503


def test_decide_is_rate_limited_per_household(api) -> None:
    client, _, decider, household_id = api
    limit = AskRateLimit(per_household=1, overall=1000)  # one shared instance, so it counts
    app.dependency_overrides[get_voice_decision_rate_limit] = lambda: limit

    assert client.post(_decide_url(household_id), json={"utterance": "weather"}).status_code == 200
    assert client.post(_decide_url(household_id), json={"utterance": "weather"}).status_code == 429
    assert len(decider.calls) == 1


def test_decide_passes_the_speakers_emotion_through(api) -> None:
    client, _, decider, household_id = api
    decider.emotion = "worried"

    response = client.post(_decide_url(household_id), json={"utterance": "When should we leave?"})

    assert response.json()["emotion"] == "worried"


def test_an_unknown_action_keeps_the_emotion(api) -> None:
    client, _, decider, household_id = api
    decider.action = "delete_plan"
    decider.emotion = "frustrated"

    response = client.post(_decide_url(household_id), json={"utterance": "delete my plan"})

    assert response.json() == {"action": "none", "confidence": 0.9, "emotion": "frustrated"}
