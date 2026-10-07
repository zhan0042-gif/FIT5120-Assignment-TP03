"""Voice assistant endpoints: start a session and choose an action."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_action_decision_client,
    get_household_repository,
    get_live_session_client,
    get_live_session_rate_limit,
    get_voice_decision_rate_limit,
)
from app.core.exceptions import HouseholdNotFound
from app.providers.interfaces import ActionDecisionClient, LiveSessionClient
from app.repositories.households import HouseholdRepository
from app.schemas.live import ActionDecision, DecideRequest, LiveSessionRequest, LiveSessionResponse
from app.services.live import LiveSessionService, VoiceDecisionService
from app.services.rate_limit import AskRateLimit

router = APIRouter(prefix="/households/{household_id}/live", tags=["live"])

RepositoryDependency = Annotated[HouseholdRepository, Depends(get_household_repository)]


@router.post(
    "/sessions",
    response_model=LiveSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_live_session(
    household_id: str,
    body: LiveSessionRequest,
    repository: RepositoryDependency,
    client: Annotated[LiveSessionClient, Depends(get_live_session_client)],
    rate_limit: Annotated[AskRateLimit, Depends(get_live_session_rate_limit)],
) -> LiveSessionResponse:
    """Exchange the browser's WebRTC offer for a GPT-Live session answer.

    The household id only scopes the route and the limit. The offer is never logged.
    """

    if not repository.household_exists(household_id):
        raise HouseholdNotFound(f"Household '{household_id}' was not found.")

    return LiveSessionService(client, rate_limit).create(household_id, body.sdp)


@router.post("/decide", response_model=ActionDecision)
def decide_voice_action(
    household_id: str,
    body: DecideRequest,
    repository: RepositoryDependency,
    client: Annotated[ActionDecisionClient, Depends(get_action_decision_client)],
    rate_limit: Annotated[AskRateLimit, Depends(get_voice_decision_rate_limit)],
) -> ActionDecision:
    """Say which action from the closed list matches what the person said.

    Nothing about the household is sent to the model, and the utterance is never logged.
    """

    if not repository.household_exists(household_id):
        raise HouseholdNotFound(f"Household '{household_id}' was not found.")

    return VoiceDecisionService(client, rate_limit).decide(household_id, body)
