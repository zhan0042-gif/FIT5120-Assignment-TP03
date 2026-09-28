import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_judgement_client
from app.main import app
from app.providers.jev_judgement import DisabledJudgementClient
from app.schemas.voice import VoiceAnswer

COMMAND = {
    "id": "command",
    "type": "pick_one",
    "options": ["set Primary transport", "none of these"],
}
STOP = {"id": "stop", "type": "yes_no", "options": []}


def _batch(transcript: str = "primary transport is a van", questions=None) -> dict:
    return {
        "state": {
            "page": "plan-builder",
            "step": "destinations",
            "mode": "normal",
            "transcript": transcript,
            "targets": [
                {"id": "primary-transport", "kind": "select",
                 "label": "Primary transport", "current": "Not set"},
            ],
        },
        "questions": questions if questions is not None else [COMMAND, STOP],
    }


class ScriptedClient:
    def __init__(self, answers: list[VoiceAnswer]) -> None:
        self.answers = answers

    def judge(self, state, questions):
        return self.answers


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _use(judge) -> None:
    app.dependency_overrides[get_judgement_client] = lambda: judge


def test_the_mock_judge_answers_every_question_in_order(client) -> None:
    response = client.post("/api/v1/voice/judge", json=_batch())

    assert response.status_code == 200
    answers = response.json()["answers"]
    assert [answer["id"] for answer in answers] == ["command", "stop"]
    assert answers[0]["answer"] == "set Primary transport"
    assert answers[1]["answer"] == "no"


@pytest.mark.parametrize(
    "body",
    [
        _batch(transcript="x" * 501),
        _batch(questions=[{"id": f"q{i}", "type": "yes_no", "options": []} for i in range(101)]),
        _batch(questions=[{"id": "command", "type": "pick_one",
                           "options": [f"option {i}" for i in range(101)]}]),
        _batch(questions=[STOP, STOP]),
        _batch(questions=[{"id": "stop", "type": "yes_no", "options": ["yes"]}]),
        _batch(questions=[{"id": "command", "type": "pick_one", "options": []}]),
        _batch(questions=[]),
    ],
    ids=[
        "long transcript", "too many questions", "too many options",
        "duplicate ids", "yes_no with options", "pick_one without options",
        "no questions",
    ],
)
def test_an_invalid_batch_is_refused(client, body) -> None:
    assert client.post("/api/v1/voice/judge", json=body).status_code == 422


def test_a_switched_off_judge_is_unavailable(client) -> None:
    _use(DisabledJudgementClient())
    response = client.post("/api/v1/voice/judge", json=_batch())
    assert response.status_code == 503


@pytest.mark.parametrize(
    "answers",
    [
        [VoiceAnswer(id="command", answer="delete everything", probability=0.99),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=1.5),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="stop", answer="maybe", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="stop", answer="no", probability=0.9),
         VoiceAnswer(id="extra", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="command", answer="none of these", probability=0.9),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
    ],
    ids=[
        "option not offered", "question unanswered", "impossible probability",
        "yes_no not yes or no", "question not asked", "question answered twice",
    ],
)
def test_an_answer_the_judge_had_no_basis_for_is_unavailable(client, answers) -> None:
    _use(ScriptedClient(answers))
    response = client.post("/api/v1/voice/judge", json=_batch())

    assert response.status_code == 503
    # The failure message must never echo what the user said.
    assert "van" not in response.text


def test_answers_come_back_in_question_order(client) -> None:
    _use(ScriptedClient([
        VoiceAnswer(id="stop", answer="no", probability=0.9),
        VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
    ]))
    answers = client.post("/api/v1/voice/judge", json=_batch()).json()["answers"]
    assert [answer["id"] for answer in answers] == ["command", "stop"]
