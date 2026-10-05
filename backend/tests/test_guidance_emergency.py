import pytest

from app.services.guidance_emergency import is_emergency
from app.services.safety_guidance import DEFAULT_ENTRIES

EMERGENCIES = [
    "My house is on fire",
    "The fire is coming and I am trapped",
    "I can't breathe",
    "I can’t breathe",
    "fire is near my house right now",
    "The flames are at the door",
    "Call triple zero",
    "What number is 000?",
    "help me",
    "We have to evacuate now",
    "MY HOUSE IS ON FIRE",
    "the fire's here",
    "fire’s coming",
    "on  fire",
    "on\tfire",
    "my house is burning",
    "Our shed is burning",
    "fire is at the door",
    "fire is approaching",
    "surrounded by fire",
    "flames at the back fence",
    "get out now",
    "I can't breath",
]

PLANNING_QUESTIONS = [
    "When should I leave on a high-risk day?",
    "What should I pack for my dog?",
    "How do I prepare my house for fire season?",
    "What if it is too late to leave?",
    "Why is leaving late so dangerous?",
    "Is staying a good option?",
    "What should I do around my house on a catastrophic fire day?",
    "How much did my house cost in 2000?",
    "When is burning off allowed before fire season?",
    "What does a fire danger rating at extreme mean?",
    "We need help planning for my mother",
    "Is it safe to leave early on a catastrophic day?",
]


@pytest.mark.parametrize("question", EMERGENCIES)
def test_emergency_wording_is_detected(question: str) -> None:
    assert is_emergency(question) is True


@pytest.mark.parametrize("question", PLANNING_QUESTIONS)
def test_planning_questions_are_not_emergencies(question: str) -> None:
    assert is_emergency(question) is False


def test_no_shipped_question_or_phrasing_looks_like_an_emergency() -> None:
    for entry in DEFAULT_ENTRIES:
        for text in [entry.question, *entry.asked_as]:
            assert not is_emergency(text), f"{entry.id}: {text}"
