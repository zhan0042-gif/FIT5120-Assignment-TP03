"""Match a typed question to reviewed entries. The model only ever returns ids.

Order of checks: emergency wording first (no model call), then the router, then
gates on whatever the router returned. Nothing here logs the question, because it
can contain a name or an address.
"""

from collections.abc import Sequence

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import GuidanceRouter
from app.schemas.safety_guidance import (
    GuidanceAnswer,
    GuidanceCatalogueItem,
    GuidanceEntryDefinition,
)
from app.services.guidance_emergency import is_emergency
from app.services.rate_limit import AskRateLimit
from app.services.safety_guidance import DEFAULT_ENTRIES

MAX_MATCHES = 2


class GuidanceAskService:
    def __init__(
        self,
        router: GuidanceRouter,
        entries: Sequence[GuidanceEntryDefinition] | None = None,
        rate_limit: AskRateLimit | None = None,
    ) -> None:
        self.router = router
        self.entries = DEFAULT_ENTRIES if entries is None else list(entries)
        self.rate_limit = rate_limit

    def ask(self, question: str, household_id: str = "") -> GuidanceAnswer:
        # An emergency is answered first and never counts against the limit.
        if is_emergency(question):
            return GuidanceAnswer(status="emergency")

        # Over the limit looks the same as the model being down: the buttons still work.
        if self.rate_limit is not None and not self.rate_limit.allow(household_id):
            return GuidanceAnswer(status="unavailable")

        # Only reviewed entries are offered, so the router cannot name a draft.
        catalogue = [
            GuidanceCatalogueItem(id=entry.id, question=entry.question, asked_as=entry.asked_as)
            for entry in self.entries
            if entry.reviewed_by is not None
        ]
        if not catalogue:
            return GuidanceAnswer(status="no_match")

        try:
            returned = self.router.route(question, catalogue)
        except ExternalDataUnavailable:
            return GuidanceAnswer(status="unavailable")

        known = {item.id for item in catalogue}
        chosen: list[str] = []
        for entry_id in returned:
            # Anything that is not a known, new id is dropped, whatever the model said.
            if isinstance(entry_id, str) and entry_id in known and entry_id not in chosen:
                chosen.append(entry_id)
        chosen = chosen[:MAX_MATCHES]

        if not chosen:
            return GuidanceAnswer(status="no_match")
        return GuidanceAnswer(status="matched", entry_ids=chosen)
