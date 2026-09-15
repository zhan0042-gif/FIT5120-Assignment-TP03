import json
from datetime import datetime, timezone

import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.core.config import build_external_providers
from app.providers.nvidia_explanation import (
    DisabledExplanationClient,
    NvidiaExplanationClient,
)
from app.schemas.rendezvous import MemberEta, RendezvousResult


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65000, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m2",
        warnings=["Lan cannot drive any transport in your plan."],
        simulated_at=datetime.now(timezone.utc),
    )


def _reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _client(handler) -> NvidiaExplanationClient:
    return NvidiaExplanationClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_requires_an_api_key() -> None:
    with pytest.raises(RuntimeError, match="AI_API_KEY"):
        NvidiaExplanationClient(api_key=None)


def test_disables_model_reasoning_in_the_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_reply("Some prose."))

    _client(handler).explain(_result())

    assert seen["body"]["chat_template_kwargs"] == {"thinking": False}
    assert seen["body"]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert seen["auth"] == "Bearer test-key"


def test_prompt_carries_the_figures_and_the_warnings() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_reply("Some prose."))

    _client(handler).explain(_result())

    prompt = " ".join(m["content"] for m in seen["body"]["messages"])
    assert "Minh" in prompt and "Lan" in prompt
    assert "27" in prompt and "55" in prompt
    assert "cannot drive" in prompt


def test_returns_the_models_text_stripped() -> None:
    text = _client(
        lambda request: httpx.Response(200, json=_reply("  Prose here.  "))
    ).explain(_result())

    assert text == "Prose here."


def test_http_error_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(503, json={"e": 1})).explain(_result())


def test_timeout_becomes_external_data_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(handler).explain(_result())


def test_empty_content_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(200, json=_reply("   "))).explain(_result())


def test_malformed_payload_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(200, json={"nope": 1})).explain(_result())


def test_a_missing_key_disables_explanation_without_stopping_the_app(monkeypatch) -> None:
    """Address lookup and routing are essential; explanation is not."""
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("VIC_ROAD_DISRUPTIONS_API_KEY", "test-road-key")
    monkeypatch.delenv("AI_API_KEY", raising=False)

    providers = build_external_providers("live")

    assert isinstance(providers.explanation, DisabledExplanationClient)
    assert not isinstance(providers.address, DisabledExplanationClient)


def test_a_present_key_selects_the_real_client(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("VIC_ROAD_DISRUPTIONS_API_KEY", "test-road-key")
    monkeypatch.setenv("AI_API_KEY", "ai-key")

    assert isinstance(
        build_external_providers("live").explanation, NvidiaExplanationClient
    )


def test_the_disabled_client_refuses_rather_than_returning_text() -> None:
    with pytest.raises(ExternalDataUnavailable):
        DisabledExplanationClient().explain(_result())
