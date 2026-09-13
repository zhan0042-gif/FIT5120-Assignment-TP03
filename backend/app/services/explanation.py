"""Request a passage about a simulation result, and discard it unless it is safe."""

import logging

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import ExplanationClient
from app.schemas.explanation import RendezvousExplanation
from app.schemas.rendezvous import RendezvousResult
from app.services.explanation_gates import rejection_reason

logger = logging.getLogger(__name__)


class ExplanationService:
    """Turn a computed result into prose, or into nothing.

    Nothing here calculates. The figures arrive already correct and the passage
    is only allowed to talk about them.
    """

    def __init__(self, explanation_client: ExplanationClient) -> None:
        self.explanation_client = explanation_client

    def explain(self, result: RendezvousResult) -> RendezvousExplanation:
        if result.status != "ready" or not result.member_etas:
            return RendezvousExplanation(reason="not_ready")

        try:
            text = self.explanation_client.explain(result)
        except ExternalDataUnavailable:
            return RendezvousExplanation(reason="unavailable")

        reason = rejection_reason(text, result)
        if reason is not None:
            # The passage itself is never logged: it may quote the household's
            # own addresses and member names.
            logger.info("explanation rejected by gate: %s", reason)
            return RendezvousExplanation(reason=reason)

        return RendezvousExplanation(explanation=text)
