"""Start a voice session and choose a voice action.

Nothing here logs the offer or the utterance: both can contain a name or an address.
"""

from app.core.exceptions import RateLimited
from app.providers.interfaces import ActionDecisionClient, LiveSessionClient
from app.schemas.live import ActionDecision, DecideRequest, LiveSessionResponse
from app.services.guidance_emergency import is_emergency
from app.services.rate_limit import AskRateLimit
from app.services.voice_actions import normalise


class LiveSessionService:
    def __init__(self, client: LiveSessionClient, rate_limit: AskRateLimit) -> None:
        self.client = client
        self.rate_limit = rate_limit

    def create(self, household_id: str, sdp: str) -> LiveSessionResponse:
        if not self.rate_limit.allow(household_id):
            raise RateLimited("Too many voice sessions were started. Please wait a minute.")
        return self.client.create(sdp)


class VoiceDecisionService:
    def __init__(self, client: ActionDecisionClient, rate_limit: AskRateLimit) -> None:
        self.client = client
        self.rate_limit = rate_limit

    def decide(self, household_id: str, request: DecideRequest) -> ActionDecision:
        # An emergency goes to the safety pipeline, which answers it with the fixed
        # "call 000" notice. It is decided before the limit and before the provider,
        # so an outage, a limit or a "not understood" answer can never lose it. The
        # character's face for it is set by rule, not read from a model.
        if is_emergency(request.utterance):
            return ActionDecision(action="ask_safety_question", confidence=1.0, emotion="urgent")

        if not self.rate_limit.allow(household_id):
            raise RateLimited("Too many voice requests. Please wait a minute.")

        decision = self.client.decide(request.utterance, request.page, request.last_readout)
        # Defence in depth: whatever the client returned, only a known action leaves here.
        return normalise(decision.action, decision.confidence).model_copy(
            update={"emotion": decision.emotion}
        )
