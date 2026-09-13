from datetime import datetime, timezone

from app.providers.mock import MockExplanationClient
from app.schemas.rendezvous import MemberEta, RendezvousResult


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1",
                display_name="Minh",
                origin_kind="home",
                travel_seconds=1620,
                distance_meters=21000,
                waiting_seconds=1680,
            )
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m1",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


def test_returns_prose_without_calling_anything() -> None:
    text = MockExplanationClient().explain(_result())

    assert isinstance(text, str)
    assert text.strip()


def test_output_passes_the_projects_own_rules() -> None:
    text = MockExplanationClient().explain(_result())

    assert len(text.split()) <= 120
    assert "\n-" not in text
    for banned in ("fire", "smoke", " he ", " she "):
        assert banned not in f" {text.lower()} "
