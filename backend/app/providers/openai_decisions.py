"""OpenAI Decisions adapter that picks one voice action from the closed list.

The model only returns an action id and a confidence. Nothing it says is spoken or
shown: the browser runs the handler for the id. Plain httpx, no SDK, like the other
hosted-model adapters.
"""

from typing import Any

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.live import ActionDecision
from app.services.voice_actions import (
    ACTIONS,
    DECISION_INSTRUCTIONS,
    EMOTION_INSTRUCTIONS,
    EMOTIONS,
    NONE_ACTION,
    decision_input,
    normalise,
    normalise_emotion,
)

DECISIONS_URL = "https://api.openai.com/v1/decisions"
DECISIONS_MODEL = "gpt-6-luna"
ACTION_QUESTION = "action"
EMOTION_QUESTION = "emotion"


def _answer_named(answers: list, name: str) -> dict | None:
    return next(
        (item for item in answers if isinstance(item, dict) and item.get("name") == name),
        None,
    )


def _parse(data: Any) -> ActionDecision:
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        raise ExternalDataUnavailable("The voice action response could not be read.")

    action = _answer_named(answers, ACTION_QUESTION)
    if action is None or action.get("type") != "choice":
        # A refusal or a missing answer means the request was not understood.
        decision = normalise(NONE_ACTION, 0.0)
    else:
        decision = normalise(action.get("choice"), action.get("confidence"))

    # The feeling is independent of the action: it only moves the character's face.
    emotion = "calm"
    feeling = _answer_named(answers, EMOTION_QUESTION)
    if feeling is not None and feeling.get("type") == "choice":
        emotion = normalise_emotion(feeling.get("choice"), feeling.get("confidence"))
    return decision.model_copy(update={"emotion": emotion})


class OpenAIDecisionsClient:
    """Ask the Decisions API which single action best matches a request."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required when voice is enabled.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=True
        )

    def decide(self, utterance: str, page: str, last_readout: str) -> ActionDecision:
        body = {
            "model": DECISIONS_MODEL,
            "input": decision_input(utterance, page, last_readout),
            "questions": [
                {
                    "type": "choice",
                    "name": ACTION_QUESTION,
                    "instructions": DECISION_INSTRUCTIONS,
                    "choices": [
                        {"value": action, "description": description}
                        for action, description in ACTIONS.items()
                    ],
                },
                {
                    "type": "choice",
                    "name": EMOTION_QUESTION,
                    "instructions": EMOTION_INSTRUCTIONS,
                    "choices": [
                        {"value": emotion, "description": description}
                        for emotion, description in EMOTIONS.items()
                    ],
                },
            ],
        }
        try:
            response = self.http_client.post(
                DECISIONS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The voice action service is temporarily unavailable."
            ) from exc
        return _parse(data)


class DisabledActionDecisionClient:
    """Stands in when no OpenAI key is configured.

    Voice is an optional extra; the buttons and typed questions do not need it. A
    missing key must not stop the application from starting.
    """

    def decide(self, utterance: str, page: str, last_readout: str) -> ActionDecision:
        raise ExternalDataUnavailable("No voice action service is configured.")
