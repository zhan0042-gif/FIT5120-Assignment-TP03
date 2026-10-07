import json

import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.mock import MockLiveSessionClient
from app.providers.openai_live import (
    LIVE_INSTRUCTIONS,
    LIVE_MODEL,
    LIVE_URL,
    DisabledLiveSessionClient,
    OpenAILiveSessionClient,
)


def _created() -> dict:
    return {"session": {"id": "live_123", "extra": "ignored"}, "transport": {"type": "webrtc", "sdp": "answer-sdp"}}


def _client(handler) -> OpenAILiveSessionClient:
    return OpenAILiveSessionClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_an_api_key_is_required() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAILiveSessionClient(api_key=None)


def test_the_session_request_uses_client_delegation_and_the_server_prompt() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=_created())

    _client(handler).create("browser-offer")

    body = seen["body"]
    assert seen["url"] == LIVE_URL
    assert seen["auth"] == "Bearer test-key"
    assert body["session"]["model"] == LIVE_MODEL == "gpt-live-1"
    assert body["session"]["instructions"] == LIVE_INSTRUCTIONS
    assert body["session"]["delegation"] == {"type": "client"}
    assert body["transport"] == {"type": "webrtc", "sdp": "browser-offer"}


def test_the_answer_is_returned_without_extra_fields() -> None:
    created = _client(lambda r: httpx.Response(201, json=_created())).create("offer")

    assert created.model_dump() == {
        "session": {"id": "live_123"},
        "transport": {"type": "webrtc", "sdp": "answer-sdp"},
    }


@pytest.mark.parametrize(
    "payload",
    [{}, {"session": {}}, {"session": {"id": "x"}}, {"session": {"id": "x"}, "transport": {"sdp": ""}}, []],
)
def test_an_unreadable_answer_is_unavailable(payload) -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(201, json=payload)).create("offer")


def test_http_errors_timeouts_and_bad_json_are_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(401)).create("offer")

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(timeout).create("offer")

    with pytest.raises(ExternalDataUnavailable):
        _client(lambda r: httpx.Response(201, content=b"nope")).create("offer")


def test_the_disabled_client_is_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        DisabledLiveSessionClient().create("offer")


def test_the_mock_returns_a_fake_answer() -> None:
    created = MockLiveSessionClient().create("offer")

    assert created.session.id == "live_mock"
    assert created.transport.sdp


def test_the_prompt_forces_delegation_and_forbids_own_figures() -> None:
    assert len(LIVE_INSTRUCTIONS) < 4000
    assert "English" in LIVE_INSTRUCTIONS
    assert "Delegate to the backend, every time" in LIVE_INSTRUCTIONS
    assert "emergency" in LIVE_INSTRUCTIONS
    assert "repeat" in LIVE_INSTRUCTIONS
    assert "never read out or invent any number" in LIVE_INSTRUCTIONS.lower()


def test_the_prompt_sends_scrolling_and_jumping_to_a_part_of_a_page_to_the_backend() -> None:
    delegation_part = LIVE_INSTRUCTIONS.split("Do not delegate")[0]

    assert "scroll" in delegation_part
    assert "top or bottom" in delegation_part
    assert "part of a page" in delegation_part
