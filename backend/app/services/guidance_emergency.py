"""Spot wording that suggests someone is in danger right now.

This runs before any model is called, so a person in danger is pointed to 000
without waiting on a hosted service and without their words being sent anywhere.
It can never be complete and covers English only; the always-visible notice in the
interface is the main protection, and this is a second line behind it. It errs
towards raising the alarm: a planning question that trips it costs one extra line
of advice, while a missed emergency could cost much more.
"""

import re

EMERGENCY_PATTERNS = [
    r"\bon fire\b",
    r"\bfire(?: is| has|['’]s) (?:here|coming|near|close|outside|reached|arrived|approaching|at)\b",
    r"\bfire approaching\b",
    r"\bflames? (?:(?:are|is|have|has) )?(?:at|near|outside|coming|reached)\b",
    r"\bsurrounded by (?:fire|flames|smoke)\b",
    # A possessive or "the" before the noun keeps "when is burning off allowed" out.
    r"\b(?:my|our|the) \w+ (?:is|are) burning\b",
    r"\btrapped\b",
    r"\bcan['’]?t breath(?:e)?\b",
    r"\bcannot breath(?:e)?\b",
    r"\btriple[ -]?zero\b",
    r"\b000\b",
    r"\bhelp me\b",
    r"\b(?:evacuate|leave|go|get out) now\b",
    # A fire, flames or smoke reported right now beside the home. "there is" rather than a bare
    # "a fire" keeps "is there a fire ban near my house" out.
    r"\bthere(?: is|['’]s| are) (?:an? )?(?:\w+ )?(?:fire|bushfire|grassfire|flames?|smoke)\b"
    r"(?! (?:ban|danger|rating|restriction|season|plan|drill|warning))"
    r"[^.?!]{0,30}\b(?:next to|beside|behind|across|over the road|in front of|outside|nearby|near|close to)\b",
    r"\bfire(?: is| was|['’]s) (?:right )?(?:next to|beside|behind|across|down the|up the|in front of|in my|in our)\b",
    r"\b(?:fire|bushfire|grassfire) (?:next to|beside|behind|across from|in front of) (?:my|our) (?:house|home)\b",
    # What the person is seeing or smelling. "I can see", not "can I see", keeps questions out.
    r"\bI (?:can (?:see|smell)|smell|saw) (?:\w+ )?(?:flames?|smoke|fire)\b(?! (?:danger|rating|ban|map))",
    r"\bsmoke (?:is |was )?(?:in|inside|filling|coming into) (?:the|my|our) (?:house|home|room)\b",
    r"\b(?:a |the )?(?:fire|bushfire|grassfire) (?:just )?(?:started|broke out)\b",
]

_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in EMERGENCY_PATTERNS]


def is_emergency(question: str) -> bool:
    # Tabs, newlines and repeated spaces must not hide a phrase from the patterns.
    normalised = " ".join(question.split())
    return any(pattern.search(normalised) for pattern in _COMPILED)
