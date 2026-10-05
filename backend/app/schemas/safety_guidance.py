"""Content-file and response models for reviewed safety Q&A."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class GuidanceConditions(BaseModel):
    """Facts a household must have for a question to be suggested to it.

    A key that is present must be true; leaving a key out means the entry does not
    depend on it. Unknown keys are rejected so a typo cannot silently change who is
    offered a question.
    """

    model_config = ConfigDict(extra="forbid")

    has_dependants: Literal[True] | None = None
    has_mobility_support: Literal[True] | None = None
    has_pets: Literal[True] | None = None
    has_livestock: Literal[True] | None = None
    no_private_transport: Literal[True] | None = None
    in_bushfire_prone_area: Literal[True] | None = None

    def required(self) -> frozenset[str]:
        return frozenset(
            name
            for name in type(self).model_fields
            if getattr(self, name) is True
        )


# A name made of spaces would pass a bare min_length check and ship an unreviewed entry.
ReviewerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GuidanceEntryDefinition(BaseModel):
    """One question and its reviewed answer, as written in the content file."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=600)
    source_name: str = Field(min_length=1, max_length=60)
    source_url: str = Field(pattern=r"^https://\S+$")
    retrieved_on: date
    reviewed_by: ReviewerName | None = None
    applies_when: GuidanceConditions = Field(default_factory=GuidanceConditions)


class GuidanceEntry(BaseModel):
    """One entry as shown to a household."""

    id: str
    question: str
    answer: str
    source_name: str
    source_url: str
    retrieved_on: date


class SafetyGuidance(BaseModel):
    entries: list[GuidanceEntry]
    # Ids of the questions offered as buttons, tailored ones first.
    suggested_ids: list[str]
    # False when the bushfire-prone-area fact could not be resolved, so questions
    # that depend on it were not suggested rather than guessed.
    location_conditions_applied: bool
