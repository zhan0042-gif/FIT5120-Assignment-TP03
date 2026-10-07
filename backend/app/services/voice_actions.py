"""The closed list of voice actions and the rule that turns a model answer into one of them.

The model can only name an action in this list and the browser can only run an
action it has a handler for, so a wrong or invented answer fails safe as `none`.
Nothing here logs the utterance, because it can contain a name or an address.
"""

import math
import re
from typing import Final

from app.schemas.live import MAX_LABEL_LENGTH, MAX_UTTERANCE_LENGTH, ActionDecision

NONE_ACTION: Final = "none"
# Below this the request is treated as not understood and the person is asked to rephrase.
MIN_CONFIDENCE: Final = 0.5

ACTIONS: Final[dict[str, str]] = {
    "open_overview": "Go to the Overview page: plan completion, local bushfire context, weather and fire danger.",
    "open_plan": "Go to My Plan, where the household builds or edits its evacuation plan.",
    "open_fire_map": "Open the fire map page.",
    "open_scenarios": "Open Test My Plan, where preparedness scenarios and checks are run.",
    "open_travel_readiness": "Open the Travel Readiness page with road routes to saved destinations.",
    "show_fire_history": "Open and read the historical fire context for the household's verified location.",
    "read_weather": "Read the current weather observations (temperature, wind and similar).",
    "read_fire_danger": "Read the official Fire Danger Rating for the household's area today.",
    "read_plan_completion": "Read how complete the household's saved plan is.",
    "check_travel_disruptions": "Check current road disruptions near the saved evacuation destinations.",
    "ask_safety_question": "Answer a question about bushfire safety guidance, such as when to leave, what to pack, pets, or staying to defend.",
    "repeat_last": "Repeat the last thing that was read out.",
    "go_back": "Go back to the previous page.",
    NONE_ACTION: "The request is not clearly one of these actions, is missing needed information, is small talk, or asks for something the app cannot do (including saving, editing or deleting data, or predicting a fire).",
}

DECISION_INSTRUCTIONS: Final = (
    "Which single app action best matches the user's last request? "
    "Choose 'none' if the request is not clearly one of these actions, needs "
    "information that is missing, or asks for something the app cannot do."
)

_WHITESPACE = re.compile(r"\s+")


def _one_line(text: str, limit: int) -> str:
    """Collapse newlines so untrusted text cannot start a new section of the input."""

    return _WHITESPACE.sub(" ", text).strip()[:limit]


def decision_input(utterance: str, page: str, last_readout: str) -> str:
    """The text the chooser sees: the request and two neutral labels, nothing else."""

    return (
        "User conversation:\n(none)\n\n"
        f"Last user request:\n{_one_line(utterance, MAX_UTTERANCE_LENGTH)}\n\n"
        "Current state:\n"
        f"- Current page: {_one_line(page, MAX_LABEL_LENGTH) or 'unknown'}\n"
        f"- Last thing read out: {_one_line(last_readout, MAX_LABEL_LENGTH) or 'none'}"
    )


def normalise(action: object, confidence: object) -> ActionDecision:
    """Anything outside the list, or below MIN_CONFIDENCE, becomes `none`."""

    try:
        value = float(confidence)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = 0.0
    if not math.isfinite(value):
        value = 0.0
    value = min(max(value, 0.0), 1.0)

    if not isinstance(action, str) or action not in ACTIONS or value < MIN_CONFIDENCE:
        return ActionDecision(action=NONE_ACTION, confidence=value)
    return ActionDecision(action=action, confidence=value)
