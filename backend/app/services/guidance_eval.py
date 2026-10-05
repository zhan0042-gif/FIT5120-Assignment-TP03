"""Score a guidance router against a fixed set of questions.

Used by hand to compare models; nothing at runtime imports it. The same gates as the
ask service apply, so a router is judged on the ids a user could actually be shown.
"""

import json
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import GuidanceRouter
from app.schemas.safety_guidance import GuidanceCatalogueItem

MAX_MATCHES = 2
DEFAULT_BAR = 0.9


@dataclass(frozen=True)
class EvalCase:
    question: str
    # Acceptable first choices. Empty means the router must match nothing.
    expected: tuple[str, ...]
    kind: str = "positive"


def load_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        EvalCase(item["question"], tuple(item["expected"]))
        for item in data["positives"]
    ]
    cases += [
        EvalCase(item["question"], (), item.get("kind", "negative"))
        for item in data["negatives"]
    ]
    return cases


@dataclass
class EvalReport:
    positives: int = 0
    top_correct: int = 0
    negatives: int = 0
    declined: int = 0
    wrong_ids: int = 0
    unavailable: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def top_accuracy(self) -> float:
        return self.top_correct / self.positives if self.positives else 0.0

    @property
    def decline_rate(self) -> float:
        return self.declined / self.negatives if self.negatives else 0.0

    @property
    def median_latency_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    def meets_bar(self, bar: float = DEFAULT_BAR) -> bool:
        return (
            self.top_accuracy >= bar
            and self.decline_rate >= bar
            and self.unavailable == 0
        )


def evaluate(
    router: GuidanceRouter,
    catalogue: Sequence[GuidanceCatalogueItem],
    cases: Sequence[EvalCase],
    *,
    pause_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.perf_counter,
) -> EvalReport:
    known = {item.id for item in catalogue}
    report = EvalReport()
    for index, case in enumerate(cases):
        if index and pause_seconds:
            sleep(pause_seconds)
        started = clock()
        try:
            returned = router.route(case.question, catalogue)
        except ExternalDataUnavailable:
            report.unavailable += 1
            if case.expected:
                report.positives += 1
            else:
                report.negatives += 1
            report.misses.append(f"{case.question} -> unavailable")
            continue
        report.latencies_ms.append((clock() - started) * 1000)

        ids: list[str] = []
        for entry_id in returned:
            if isinstance(entry_id, str) and entry_id in known and entry_id not in ids:
                ids.append(entry_id)
        ids = ids[:MAX_MATCHES]

        if case.expected:
            report.positives += 1
            if ids and ids[0] in case.expected:
                report.top_correct += 1
            else:
                report.misses.append(f"{case.question} -> {ids}")
            report.wrong_ids += sum(1 for entry_id in ids if entry_id not in case.expected)
        else:
            report.negatives += 1
            if not ids:
                report.declined += 1
            else:
                report.misses.append(f"{case.question} -> {ids}")
    return report


def format_report(report: EvalReport, model: str) -> str:
    verdict = "meets" if report.meets_bar() else "does not meet"
    lines = [
        f"Model: {model}",
        f"Questions that should match: {report.top_correct}/{report.positives} "
        f"first choice correct ({report.top_accuracy:.1%})",
        f"Questions that should be declined: {report.declined}/{report.negatives} "
        f"declined ({report.decline_rate:.1%})",
        f"Wrong ids returned: {report.wrong_ids}",
        f"Unavailable: {report.unavailable}",
        f"Median latency: {report.median_latency_ms:.0f} ms",
        f"Result: {verdict} the {DEFAULT_BAR:.0%} bar",
    ]
    if report.misses:
        lines.append("Misses:")
        lines.extend(f"  - {miss}" for miss in report.misses)
    return "\n".join(lines)
