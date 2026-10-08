import math
from typing import get_args

from app.schemas.live import ActionDecision, Emotion
from app.services.voice_actions import (
    EMOTION_INSTRUCTIONS,
    EMOTIONS,
    MIN_CONFIDENCE,
    normalise_emotion,
)


def test_the_emotion_list_is_closed_and_every_value_is_described() -> None:
    assert list(EMOTIONS) == ["calm", "worried", "urgent", "frustrated", "playful"]
    assert all(description.strip() for description in EMOTIONS.values())


def test_the_schema_and_the_list_agree() -> None:
    assert set(get_args(Emotion)) == set(EMOTIONS)


def test_a_decision_is_calm_unless_told_otherwise() -> None:
    assert ActionDecision(action="none", confidence=0).emotion == "calm"


def test_a_known_emotion_with_enough_confidence_is_kept() -> None:
    assert normalise_emotion("worried", 0.8) == "worried"
    assert normalise_emotion("playful", MIN_CONFIDENCE) == "playful"


def test_low_confidence_is_calm() -> None:
    assert normalise_emotion("urgent", 0.49) == "calm"


def test_anything_unusable_is_calm() -> None:
    assert normalise_emotion("angry", 0.9) == "calm"
    assert normalise_emotion(None, 0.9) == "calm"
    assert normalise_emotion(7, 0.9) == "calm"
    assert normalise_emotion("worried", "high") == "calm"
    assert normalise_emotion("worried", None) == "calm"
    assert normalise_emotion("worried", math.nan) == "calm"
    assert normalise_emotion("worried", math.inf) == "calm"


def test_the_instructions_default_to_calm_when_there_is_no_clear_feeling() -> None:
    assert "calm" in EMOTION_INSTRUCTIONS
    assert "no clear sign" in EMOTION_INSTRUCTIONS
