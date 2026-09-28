"""Voice control: judge a spoken command against the page's own options."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_judgement_client, get_voice_turn_logger
from app.providers.interfaces import JudgementClient
from app.schemas.voice import (
    VoiceJudgeRequest,
    VoiceJudgeResponse,
    VoiceLogAccepted,
    VoiceTurnLog,
)
from app.services.voice import VoiceJudgementService
from app.services.voice_log import VoiceTurnLogger

router = APIRouter(prefix="/voice", tags=["voice"])
JudgementDependency = Annotated[JudgementClient, Depends(get_judgement_client)]
TurnLoggerDependency = Annotated[VoiceTurnLogger, Depends(get_voice_turn_logger)]


@router.post("/judge", response_model=VoiceJudgeResponse)
def judge_voice_command(
    request: VoiceJudgeRequest, client: JudgementDependency
) -> VoiceJudgeResponse:
    """Answer the page's question batch about one finished utterance.

    Stateless: nothing is stored, and the plan is never read or changed here.
    """
    return VoiceJudgementService(client).judge(request)


@router.post(
    "/log", response_model=VoiceLogAccepted, status_code=status.HTTP_202_ACCEPTED
)
def log_voice_turn(turn: VoiceTurnLog, turn_logger: TurnLoggerDependency) -> VoiceLogAccepted:
    """Record one finished turn. Always accepted: a missed line is never the user's problem.

    Answers 202 with a body rather than 204, because the frontend's HTTP
    boundary parses every successful response as JSON.
    """
    turn_logger.record(turn)
    return VoiceLogAccepted()
