from datetime import datetime, timezone

from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.explanation_gates import allowed_numbers, rejection_reason


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65000, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m2",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


def test_allowed_numbers_cover_every_figure_a_reader_can_see() -> None:
    allowed = allowed_numbers(_result())

    assert "27" in allowed      # Minh's 1620 seconds
    assert "55" in allowed      # Lan's 3300 seconds, and the household total
    assert "28" in allowed      # Minh's 1680 seconds of waiting
    assert "21" in allowed      # Minh's 21000 metres
    assert "65" in allowed      # Lan's 65000 metres
    assert "2" in allowed       # the number of members
    assert "99" not in allowed


def test_a_clean_passage_is_accepted() -> None:
    text = (
        "Lan takes 55 minutes and arrives last, so the household is not together "
        "until then. Consider arranging a lift so Lan can set off sooner."
    )

    assert rejection_reason(text, _result()) is None


def test_a_number_that_is_not_in_the_result_is_rejected() -> None:
    text = "Lan takes 72 minutes, which is the longest journey in the household."

    assert rejection_reason(text, _result()) == "invented_number"


def test_speculation_about_fire_or_smoke_is_rejected() -> None:
    text = "Lan may be delayed by smoke on the roads, which would hold everyone up."

    assert rejection_reason(text, _result()) == "speculation"


def test_the_word_fire_is_rejected() -> None:
    text = "If the fire reaches the highway, Lan will not get through at all."

    assert rejection_reason(text, _result()) == "speculation"


def test_a_gendered_pronoun_is_rejected() -> None:
    text = "Lan cannot drive, so he will need a lift from somebody else."

    assert rejection_reason(text, _result()) == "gendered"


def test_a_passage_longer_than_120_words_is_rejected() -> None:
    text = " ".join(["Lan arrives last and the household waits."] * 30)

    assert rejection_reason(text, _result()) == "shape"


def test_a_bulleted_list_is_rejected() -> None:
    text = "The problems are:\n- Lan cannot drive\n- Minh drives everyone"

    assert rejection_reason(text, _result()) == "shape"


def test_gates_run_in_order_so_the_first_failure_is_reported() -> None:
    text = "He will be delayed by smoke for 72 minutes."

    assert rejection_reason(text, _result()) == "invented_number"


def test_her_inside_another_word_is_not_treated_as_a_pronoun() -> None:
    text = "Gathering there first would shorten the wait for everyone involved."

    assert rejection_reason(text, _result()) is None


# Five passages actually produced by nvidia/nemotron-3-super-120b-a12b on
# 2026-09-13, for a household of Minh (27 min), Bo (43 min) and Lan (55 min).
# Kept verbatim so the gates are tested against real model behaviour rather
# than against sentences written to pass them.
OBSERVED = [
    (
        "The single biggest weakness is that the plan relies on Bo and Lan, who "
        "cannot drive or travel independently, to reach the destination without "
        "assistance, creating a risk of delay or failure if no one is available "
        "to help them en route. A practical fix is to assign a specific household "
        "member to collect them.",
        None,
    ),
    (
        "The single biggest weakness is that the plan relies on Minh being "
        "available and able to drive to pick up Bo and Lan, but if Minh is "
        "delayed, injured, or unable to drive due to smoke, road closures, or "
        "vehicle failure, the entire household cannot reunite. A practical fix "
        "is to designate a secondary driver.",
        "speculation",
    ),
    (
        "The single biggest weakness is that the plan relies on Minh being "
        "available and able to drive to pick up Bo and Lan, but if Minh is "
        "delayed, injured, or unable to drive due to smoke, road closures, or "
        "vehicle failure, the household cannot reunite. A practical fix is to "
        "pre-arrange a trusted neighbour.",
        "speculation",
    ),
    (
        "The single biggest weakness is that the plan relies on Minh being able "
        "to drive everyone to the destination, but Minh is the only one who can "
        "drive, and if Minh is delayed, injured, or unavailable, the entire "
        "household cannot evacuate together. A practical fix is to ensure at "
        "least one other household member can drive.",
        None,
    ),
    (
        "The single biggest weakness is that the household cannot be together "
        "until the last person arrives, meaning vulnerable members like Bo and "
        "Lan are left waiting alone at their locations for extended periods "
        "without support or transportation. A practical fix is to arrange for a "
        "trusted neighbour to help.",
        None,
    ),
]


def _three_member_result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Bo", origin_kind="school",
                travel_seconds=2580, distance_meters=47600, waiting_seconds=720,
            ),
            MemberEta(
                member_id="m3", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65400, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m3",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


def test_real_model_output_is_classified_as_measured() -> None:
    result = _three_member_result()

    outcomes = [rejection_reason(text, result) for text, _ in OBSERVED]

    assert outcomes == [expected for _, expected in OBSERVED]


def test_the_observed_rejection_rate_is_two_in_five() -> None:
    """The design states this rate plainly; this pins it to real samples."""
    result = _three_member_result()

    rejected = sum(
        1 for text, _ in OBSERVED if rejection_reason(text, result) is not None
    )

    assert rejected == 2
