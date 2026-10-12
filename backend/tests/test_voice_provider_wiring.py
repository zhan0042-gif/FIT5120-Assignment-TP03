import pytest

from app.core.config import build_external_providers
from app.core.dependencies import (
    get_action_decision_client,
    get_live_session_client,
    get_live_session_rate_limit,
    get_voice_decision_rate_limit,
)
from app.providers.mock import MockActionDecisionClient, MockLiveSessionClient
from app.providers.openai_decisions import DisabledActionDecisionClient, OpenAIDecisionsClient
from app.providers.openai_live import DisabledLiveSessionClient, OpenAILiveSessionClient


def test_mock_mode_uses_the_mock_voice_clients() -> None:
    providers = build_external_providers("mock")

    assert isinstance(providers.action_decision, MockActionDecisionClient)
    assert isinstance(providers.live_session, MockLiveSessionClient)


def test_live_mode_without_a_key_disables_voice_instead_of_stopping_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    providers = build_external_providers("live")

    assert isinstance(providers.action_decision, DisabledActionDecisionClient)
    assert isinstance(providers.live_session, DisabledLiveSessionClient)


def test_live_mode_with_a_blank_key_is_also_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    providers = build_external_providers("live")

    assert isinstance(providers.live_session, DisabledLiveSessionClient)


def test_live_mode_with_a_key_uses_the_hosted_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    providers = build_external_providers("live")

    assert isinstance(providers.action_decision, OpenAIDecisionsClient)
    assert isinstance(providers.live_session, OpenAILiveSessionClient)


def test_the_dependency_getters_return_the_wired_clients_and_limiters() -> None:
    # conftest selects APP_DATA_MODE=mock before the app is imported.
    assert isinstance(get_action_decision_client(), MockActionDecisionClient)
    assert isinstance(get_live_session_client(), MockLiveSessionClient)

    session_limit = get_live_session_rate_limit()
    decide_limit = get_voice_decision_rate_limit()
    assert (session_limit.per_household, session_limit.overall) == (3, 20)
    assert (decide_limit.per_household, decide_limit.overall) == (20, 120)
    assert session_limit is not decide_limit
    assert session_limit.window_seconds == 60.0
    assert decide_limit.window_seconds == 60.0
