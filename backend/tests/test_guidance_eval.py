from pathlib import Path

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.safety_guidance import GuidanceCatalogueItem
from app.services.guidance_emergency import is_emergency
from app.services.guidance_eval import (
    EvalCase,
    EvalReport,
    evaluate,
    format_report,
    load_cases,
)
from app.services.safety_guidance import DEFAULT_ENTRIES

FIXTURE = Path(__file__).parent / "fixtures" / "guidance_router_eval.json"

CATALOGUE = [
    GuidanceCatalogueItem(id="a", question="Question a?"),
    GuidanceCatalogueItem(id="b", question="Question b?"),
]

CASES = [
    EvalCase("Ask for a", ("a",)),
    EvalCase("Ask for b", ("b",)),
    EvalCase("Ask for a or b", ("a", "b")),
    EvalCase("Unrelated", (), "off_topic"),
    EvalCase("Predict", (), "prediction"),
]


class Scripted:
    def __init__(self, replies: dict[str, list]) -> None:
        self.replies = replies

    def route(self, question, catalogue):
        reply = self.replies.get(question, [])
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_the_shipped_question_set_has_enough_cases() -> None:
    cases = load_cases(FIXTURE)

    assert sum(1 for case in cases if case.expected) >= 25
    assert sum(1 for case in cases if not case.expected) >= 10


def test_every_expected_id_is_a_real_entry() -> None:
    known = {entry.id for entry in DEFAULT_ENTRIES}
    for case in load_cases(FIXTURE):
        assert set(case.expected) <= known, case.question


def test_no_question_is_repeated() -> None:
    questions = [case.question for case in load_cases(FIXTURE)]

    assert len(questions) == len(set(questions))


def test_no_evaluation_question_is_emergency_wording() -> None:
    for case in load_cases(FIXTURE):
        assert not is_emergency(case.question), case.question


def test_a_perfect_router_meets_the_bar() -> None:
    router = Scripted({"Ask for a": ["a"], "Ask for b": ["b"], "Ask for a or b": ["b"]})

    report = evaluate(router, CATALOGUE, CASES)

    assert (report.positives, report.top_correct) == (3, 3)
    assert (report.negatives, report.declined) == (2, 2)
    assert report.wrong_ids == 0
    assert report.top_accuracy == 1.0
    assert report.decline_rate == 1.0
    assert report.meets_bar()


def test_a_router_that_never_matches_fails_the_positives_but_declines_every_negative() -> None:
    report = evaluate(Scripted({}), CATALOGUE, CASES)

    assert report.top_correct == 0
    assert report.decline_rate == 1.0
    assert not report.meets_bar()


def test_a_wrong_first_choice_is_counted_and_listed() -> None:
    router = Scripted({"Ask for a": ["b"], "Ask for b": ["b"], "Ask for a or b": ["a"]})

    report = evaluate(router, CATALOGUE, CASES)

    assert report.top_correct == 2
    assert report.wrong_ids == 1
    assert any("Ask for a" in miss for miss in report.misses)


def test_matching_a_question_that_should_be_declined_is_a_miss() -> None:
    router = Scripted({"Predict": ["a"]})

    report = evaluate(router, CATALOGUE, CASES)

    assert report.declined == 1
    assert any("Predict" in miss for miss in report.misses)


def test_ids_that_are_not_in_the_catalogue_do_not_count_as_a_match() -> None:
    router = Scripted({"Ask for a": ["invented"], "Unrelated": ["invented"]})

    report = evaluate(router, CATALOGUE, CASES)

    assert report.top_correct == 0
    assert report.declined == 2


def test_an_unavailable_router_is_counted_and_fails_the_bar() -> None:
    router = Scripted({case.question: ExternalDataUnavailable("down") for case in CASES})

    report = evaluate(router, CATALOGUE, CASES)

    assert report.unavailable == len(CASES)
    assert not report.meets_bar()


def test_a_pause_is_taken_between_calls_but_not_before_the_first() -> None:
    pauses: list[float] = []

    evaluate(Scripted({}), CATALOGUE, CASES, pause_seconds=1.5, sleep=pauses.append)

    assert pauses == [1.5] * (len(CASES) - 1)


def test_latency_is_measured_per_call() -> None:
    ticks = iter(range(0, 100))

    report = evaluate(Scripted({}), CATALOGUE, CASES[:3], clock=lambda: next(ticks) / 1000)

    assert len(report.latencies_ms) == 3
    assert report.median_latency_ms > 0


def test_the_report_names_the_model_and_the_bar() -> None:
    text = format_report(EvalReport(positives=2, top_correct=2, negatives=2, declined=2), "vendor/model")

    assert "vendor/model" in text
    assert "100%" in text
    assert "meets the 90% bar" in text
