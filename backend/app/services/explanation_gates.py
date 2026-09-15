"""Checks a generated passage must survive before a user is shown it.

Each gate rejects the whole passage. Nothing is edited and nothing is retried:
a sentence that has to be repaired before it is safe was not safe to begin with.
"""

import re

from app.schemas.rendezvous import RendezvousResult

MAX_WORDS = 120

# Measured: 2 of 5 sampled responses speculated about smoke and road closures.
# The model has no basis for any of this.
SPECULATION = re.compile(
    r"\b(fire|fires|flame|flames|ember|embers|smoke|smoky|burn|burning|burnt|"
    r"spread|spreading|road closure|road closures)\b",
    re.IGNORECASE,
)

# The data model records no gender. A weaker model produced "he" unprompted.
GENDERED = re.compile(r"\b(he|she|him|her|his|hers)\b", re.IGNORECASE)

LIST_MARKER = re.compile(r"(^|\n)\s*([-*•]|\d+[.)])\s", re.MULTILINE)

NUMBER = re.compile(r"\d+")


def _minutes(seconds: int) -> int:
    return round(seconds / 60)


def allowed_numbers(result: RendezvousResult) -> set[str]:
    """Every figure a reader could legitimately see, as bare digit strings.

    Derived from the result rather than listed by hand, so a passage quoting a
    distance is accepted while one inventing a duration is not.
    """
    allowed: set[str] = {str(len(result.member_etas))}
    for eta in result.member_etas:
        allowed.add(str(_minutes(eta.travel_seconds)))
        allowed.add(str(_minutes(eta.waiting_seconds)))
        allowed.add(str(round(eta.distance_meters / 1000)))
    if result.everyone_together_seconds is not None:
        allowed.add(str(_minutes(result.everyone_together_seconds)))
    return allowed


def rejection_reason(text: str, result: RendezvousResult) -> str | None:
    """Return the name of the first gate that rejects this passage, or None.

    Order matters only for reporting: an invented figure is the most serious
    fault, so it is named first when a passage breaks several rules at once.
    """
    allowed = allowed_numbers(result)
    if any(found not in allowed for found in NUMBER.findall(text)):
        return "invented_number"
    if SPECULATION.search(text):
        return "speculation"
    if GENDERED.search(text):
        return "gendered"
    if len(text.split()) > MAX_WORDS or LIST_MARKER.search(text):
        return "shape"
    return None
