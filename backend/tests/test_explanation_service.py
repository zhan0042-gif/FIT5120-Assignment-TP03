from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.explanation import ExplanationService

CLEAN = (
    "Lan takes 55 minutes and arrives last, so the household is not together "
    "until then. Consider arranging a lift so Lan can set off sooner."
)


def _result(status: str = "ready") -> RendezvousResult:
    return RendezvousResult(
        status=status,
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


class FixedClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def explain(self, result: RendezvousResult) -> str:
        self.calls += 1
        return self.text


class DeadClient:
    def explain(self, result: RendezvousResult) -> str:
        raise ExternalDataUnavailable("The explanation service is unavailable.")


def test_a_clean_passage_is_returned() -> None:
    outcome = ExplanationService(FixedClient(CLEAN)).explain(_result())

    assert outcome.explanation == CLEAN
    assert outcome.reason is None


def test_an_invented_figure_discards_the_whole_passage() -> None:
    outcome = ExplanationService(
        FixedClient("Lan takes 72 minutes, longer than anyone else.")
    ).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "invented_number"


def test_speculation_discards_the_whole_passage() -> None:
    outcome = ExplanationService(
        FixedClient("Lan may be held up by smoke along the way.")
    ).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "speculation"


def test_a_dead_provider_yields_no_explanation_and_no_exception() -> None:
    outcome = ExplanationService(DeadClient()).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "unavailable"


def test_a_result_that_is_not_ready_is_never_sent_to_the_model() -> None:
    client = FixedClient(CLEAN)

    outcome = ExplanationService(client).explain(_result(status="not_applicable"))

    assert outcome.explanation is None
    assert outcome.reason == "not_ready"
    assert client.calls == 0


def test_a_ready_result_with_no_members_is_never_sent_to_the_model() -> None:
    client = FixedClient(CLEAN)
    empty = _result()
    empty.member_etas = []

    outcome = ExplanationService(client).explain(empty)

    assert outcome.explanation is None
    assert outcome.reason == "not_ready"
    assert client.calls == 0


def test_a_rejected_passage_is_never_written_to_the_log(caplog) -> None:
    """The passage can quote household addresses and member names."""
    secret = "Lan may be delayed by smoke near Private Street."

    with caplog.at_level("INFO"):
        ExplanationService(FixedClient(secret)).explain(_result())

    assert "Private Street" not in caplog.text
    assert "speculation" in caplog.text
