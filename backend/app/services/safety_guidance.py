"""Choose reviewed CFA question-and-answer entries for a household. Nothing here is generated."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter

from app.core.exceptions import (
    ExternalDataUnavailable,
    HouseholdNotFound,
    LocationNotFound,
    LocationNotVerified,
    PlanNotFound,
)
from app.providers.interfaces import SpatialProvider
from app.repositories.households import HouseholdRepository
from app.schemas.households import HouseholdPlan
from app.schemas.safety_guidance import (
    GuidanceEntry,
    GuidanceEntryDefinition,
    SafetyGuidance,
)
from app.services.context import HouseholdStaticContextResolver

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "safety_guidance.json"

# Up to four questions tailored to the household come first, then general ones, six
# in all. Tailored questions lead but cannot crowd out the general ones, such as
# when to leave.
MAX_SUGGESTED = 6
MAX_TAILORED = 4

_ENTRIES = TypeAdapter(list[GuidanceEntryDefinition])


def load_entries(path: Path = CONTENT_PATH) -> list[GuidanceEntryDefinition]:
    """Read and validate the content file, keeping its order as display order."""

    entries = _ENTRIES.validate_json(path.read_text(encoding="utf-8"))
    ids = [entry.id for entry in entries]
    duplicates = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate safety guidance ids: {', '.join(duplicates)}")
    return entries


# Loaded at import so an invalid content file stops the app from starting rather
# than failing on the first request.
DEFAULT_ENTRIES: list[GuidanceEntryDefinition] = load_entries()


def plan_facts(plan: HouseholdPlan) -> set[str]:
    """Condition names that are true of a saved plan."""

    facts: set[str] = set()
    if any(member.is_dependant for member in plan.members):
        facts.add("has_dependants")
    if any(member.mobility_support_required for member in plan.members):
        facts.add("has_mobility_support")
    if any(animal.category == "pet" for animal in plan.animals):
        facts.add("has_pets")
    if any(animal.category == "livestock" for animal in plan.animals):
        facts.add("has_livestock")
    # Only an explicit "no": an unanswered question is not an answer.
    if plan.has_private_transport is False:
        facts.add("no_private_transport")
    return facts


class SafetyGuidanceService:
    """Return every reviewed entry and the questions to offer this household.

    Deterministic and read-only: it derives facts, compares them with each entry's
    conditions, and returns the result. It does not write to the plan and does not
    call a model. Conditions only choose which questions are *suggested*; every
    reviewed entry stays available, so a household with no pets can still read the
    pet answers.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        entries: Sequence[GuidanceEntryDefinition] | None = None,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.entries = DEFAULT_ENTRIES if entries is None else list(entries)

    def get(self, household_id: str) -> SafetyGuidance:
        if not self.repository.household_exists(household_id):
            raise HouseholdNotFound(f"Household '{household_id}' was not found.")

        facts: set[str] = set()
        try:
            facts |= plan_facts(self.repository.get_plan(household_id))
        except PlanNotFound:
            pass

        in_prone_area = self._in_bushfire_prone_area(household_id)
        if in_prone_area:
            facts.add("in_bushfire_prone_area")

        # A summary nobody has checked against its source is never shown.
        reviewed = [entry for entry in self.entries if entry.reviewed_by is not None]
        tailored = [
            entry.id
            for entry in reviewed
            if entry.applies_when.required() and entry.applies_when.required() <= facts
        ]
        general = [entry.id for entry in reviewed if not entry.applies_when.required()]
        suggested = (tailored[:MAX_TAILORED] + general)[:MAX_SUGGESTED]

        return SafetyGuidance(
            entries=[
                GuidanceEntry(
                    id=entry.id,
                    question=entry.question,
                    answer=entry.answer,
                    source_name=entry.source_name,
                    source_url=entry.source_url,
                    retrieved_on=entry.retrieved_on,
                )
                for entry in reviewed
            ],
            suggested_ids=suggested,
            location_conditions_applied=in_prone_area is not None,
        )

    def _in_bushfire_prone_area(self, household_id: str) -> bool | None:
        """True or False when the location is resolved, None when it is not."""

        try:
            _, context = HouseholdStaticContextResolver(
                self.repository, self.spatial_provider
            ).get_full(household_id)
        except (LocationNotFound, LocationNotVerified, ExternalDataUnavailable):
            return None
        return context.is_bushfire_prone_area
