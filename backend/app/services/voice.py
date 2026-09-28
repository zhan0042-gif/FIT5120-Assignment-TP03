"""Voice judgement: ask the judge, then refuse any answer it had no basis to give."""

import math

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import JudgementClient
from app.schemas.voice import (
    VoiceAnswer,
    VoiceJudgeRequest,
    VoiceJudgeResponse,
    VoiceQuestion,
)

YES_NO_ANSWERS = ("yes", "no")


class VoiceJudgementService:
    def __init__(self, client: JudgementClient) -> None:
        self._client = client

    def judge(self, request: VoiceJudgeRequest) -> VoiceJudgeResponse:
        answers = self._client.judge(request.state, request.questions)
        return VoiceJudgeResponse(answers=_checked(answers, request.questions))


def _checked(
    answers: list[VoiceAnswer], questions: list[VoiceQuestion]
) -> list[VoiceAnswer]:
    """Every question answered exactly once, from its own options, with a real probability.

    The browser acts on these answers. An answer the judge was never offered is
    treated as a failed call, never passed on. Messages here never include what
    was said: they reach the client and may reach logs.
    """
    by_id: dict[str, VoiceAnswer] = {}
    for answer in answers:
        if answer.id in by_id:
            raise ExternalDataUnavailable("The voice judge answered a question twice.")
        by_id[answer.id] = answer

    ordered = []
    for question in questions:
        answer = by_id.pop(question.id, None)
        if answer is None:
            raise ExternalDataUnavailable("The voice judge left a question unanswered.")
        allowed = question.options if question.type == "pick_one" else YES_NO_ANSWERS
        if answer.answer not in allowed:
            raise ExternalDataUnavailable("The voice judge gave an answer it was not offered.")
        if not math.isfinite(answer.probability) or not 0.0 <= answer.probability <= 1.0:
            raise ExternalDataUnavailable("The voice judge gave an impossible probability.")
        ordered.append(answer)

    if by_id:
        raise ExternalDataUnavailable("The voice judge answered a question it was not asked.")
    return ordered
