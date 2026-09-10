"""Rendezvous simulation API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.households import CompletionSectionName


class MemberEta(BaseModel):
    """One member's estimated journey to the shared destination."""

    member_id: str
    display_name: str
    origin_kind: Literal["home", "work", "school", "other"]
    travel_seconds: int
    distance_meters: int
    waiting_seconds: int


class RendezvousResult(BaseModel):
    """Estimated moment the household is together, or why it cannot be estimated.

    Not persisted: the figures depend on traffic at the time of the call, and a
    stored figure presented later as current would be worse than none.
    """

    status: Literal["ready", "unavailable", "not_applicable"]
    unavailable_reason: str | None = None
    missing_sections: list[CompletionSectionName] = []
    destination_name: str = ""
    member_etas: list[MemberEta] = []
    everyone_together_seconds: int | None = None
    slowest_member_id: str | None = None
    warnings: list[str] = []
    simulated_at: datetime
