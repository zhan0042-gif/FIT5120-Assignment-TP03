import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import voice_log_settings
from app.core.dependencies import get_voice_turn_logger
from app.main import app
from app.schemas.voice import VoiceTurnLog
from app.services.voice_log import VoiceTurnLogger

TURN = {
    "turn_id": "vt_1",
    "page": "plan-builder",
    "step": "destinations",
    "mode": "normal",
    "transcript": "primary transport is a van",
    "answers": [
        {"id": "command", "answer": "primary-transport", "probability": 0.94},
        {"id": "option:primary-transport", "answer": "Van", "probability": 0.97},
        {"id": "span", "answer": "a van", "probability": 0.9},
        {"id": "stop", "answer": "no", "probability": 0.95},
    ],
    "decision": "execute",
    "action": {"kind": "select", "target": "primary-transport", "value": "Van"},
    "outcome": "ok",
    "latency_ms": {"judge": 240, "turn": 310},
}
NOW = datetime(2026, 9, 28, 10, 14, 3, tzinfo=timezone.utc)


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _record(path: Path, include_content: bool) -> None:
    VoiceTurnLogger(path, include_content=include_content).record(
        VoiceTurnLog.model_validate(TURN), now=NOW
    )


def test_a_turn_is_one_json_line_with_content_when_allowed(tmp_path) -> None:
    path = tmp_path / "logs" / "voice.jsonl"
    _record(path, include_content=True)

    [entry] = _lines(path)
    assert entry["ts"] == "2026-09-28T10:14:03+00:00"
    assert entry["transcript"] == "primary transport is a van"
    assert entry["action"]["value"] == "Van"
    assert entry["latency_ms"] == {"judge": 240, "turn": 310}


def test_each_turn_appends_a_line(tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    _record(path, include_content=True)
    _record(path, include_content=True)
    assert len(_lines(path)) == 2


def test_content_is_removed_unless_allowed(tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    _record(path, include_content=False)

    [entry] = _lines(path)
    assert entry["transcript"] is None
    assert entry["action"] == {"kind": "select", "target": "primary-transport", "value": None}
    answers = {answer["id"]: answer for answer in entry["answers"]}
    assert answers["command"]["answer"] == "primary-transport"
    assert answers["stop"]["answer"] == "no"
    assert answers["option:primary-transport"] == {
        "id": "option:primary-transport", "answer": None, "probability": 0.97,
    }
    assert answers["span"]["answer"] is None
    assert "van" not in path.read_text(encoding="utf-8").lower()


def test_a_failed_write_neither_raises_nor_leaks(tmp_path, caplog) -> None:
    # A directory cannot be opened for appending.
    with caplog.at_level(logging.WARNING):
        _record(tmp_path, include_content=True)

    assert "could not be written" in caplog.text
    assert "primary transport" not in caplog.text


def test_settings_default_to_a_local_file_without_content(monkeypatch) -> None:
    monkeypatch.delenv("VOICE_LOG_PATH", raising=False)
    monkeypatch.delenv("VOICE_LOG_CONTENT", raising=False)
    assert voice_log_settings() == (Path("logs/voice-turns.jsonl"), False)


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes"])
def test_content_can_be_switched_on(monkeypatch, raw) -> None:
    monkeypatch.setenv("VOICE_LOG_CONTENT", raw)
    monkeypatch.setenv("VOICE_LOG_PATH", "/tmp/elsewhere.jsonl")
    assert voice_log_settings() == (Path("/tmp/elsewhere.jsonl"), True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_the_endpoint_accepts_and_writes_a_turn(client, tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        path, include_content=False
    )

    response = client.post("/api/v1/voice/log", json=TURN)

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert len(_lines(path)) == 1


def test_the_endpoint_accepts_even_when_the_write_fails(client, tmp_path) -> None:
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        tmp_path, include_content=False
    )
    assert client.post("/api/v1/voice/log", json=TURN).status_code == 202


def test_the_endpoint_refuses_an_unknown_decision(client, tmp_path) -> None:
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        tmp_path / "voice.jsonl", include_content=False
    )
    body = {**TURN, "decision": "improvise"}
    assert client.post("/api/v1/voice/log", json=body).status_code == 422
