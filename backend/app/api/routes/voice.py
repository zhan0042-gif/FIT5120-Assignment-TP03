"""Voice control: judge a spoken command against the page's own options."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_judgement_client
from app.providers.interfaces import JudgementClient
from app.schemas.voice import VoiceJudgeRequest, VoiceJudgeResponse
from app.services.voice import VoiceJudgementService

router = APIRouter(prefix="/voice", tags=["voice"])
JudgementDependency = Annotated[JudgementClient, Depends(get_judgement_client)]


@router.post("/judge", response_model=VoiceJudgeResponse)
def judge_voice_command(
    request: VoiceJudgeRequest, client: JudgementDependency
) -> VoiceJudgeResponse:
    """Answer the page's question batch about one finished utterance.

    Stateless: nothing is stored, and the plan is never read or changed here.
    """
    return VoiceJudgementService(client).judge(request)
