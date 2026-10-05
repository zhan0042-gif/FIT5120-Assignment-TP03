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
]

_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in EMERGENCY_PATTERNS]


def is_emergency(question: str) -> bool:
    # Tabs, newlines and repeated spaces must not hide a phrase from the patterns.
    normalised = " ".join(question.split())
    return any(pattern.search(normalised) for pattern in _COMPILED)
