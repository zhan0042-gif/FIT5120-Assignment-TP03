"""Manual evaluation of the voice action chooser against the live Decisions API.

Run from backend/:  OPENAI_API_KEY=... python scripts/evaluate_voice_actions.py

Not part of CI: it spends quota and needs the network. It prints accuracy by
category and the executions that would have gone wrong at each confidence
threshold, which is the number that matters (an action run that should not have
been). Utterances here are synthetic; none is real user data.
"""

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import ExternalDataUnavailable  # noqa: E402
from app.providers.openai_decisions import OpenAIDecisionsClient  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "voice_action_cases.json"
# The fixture was written with older page names; these are the labels the browser sends.
PAGE_LABELS = {
    "overview": "overview",
    "plan": "my plan",
    "scenarios": "test my plan",
    "fire_history": "fire map",
    "map": "fire map",
    "safety_insights": "safety insights",
}
THRESHOLDS = (0.3, 0.5, 0.7)


def main() -> int:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("Set OPENAI_API_KEY to run this evaluation.")
        return 2

    client = OpenAIDecisionsClient(api_key=key)
    cases = json.loads(FIXTURE.read_text())["cases"]
    rows = []
    for case in cases:
        started = time.perf_counter()
        try:
            decision = client.decide(case["text"], PAGE_LABELS.get(case["page"], case["page"]), case["last"])
        except ExternalDataUnavailable as exc:
            print(f"#{case['id']} unavailable: {exc}")
            continue
        rows.append((case, decision, (time.perf_counter() - started) * 1000))

    if not rows:
        print("No case could be answered.")
        return 1

    correct = [row for row in rows if row[1].action == row[0]["expected"]]
    print(f"accuracy: {len(correct)}/{len(rows)} = {len(correct) / len(rows):.0%}")
    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case, decision, _ in rows:
        by_category[case["cat"]][1] += 1
        by_category[case["cat"]][0] += decision.action == case["expected"]
    for category, (hit, total) in by_category.items():
        print(f"  {category:12s} {hit}/{total}")

    print("\nthreshold  executed  wrong_executions")
    for threshold in THRESHOLDS:
        executed = [row for row in rows if row[1].action != "none" and row[1].confidence >= threshold]
        wrong = [row for row in executed if row[1].action != row[0]["expected"]]
        print(f"  {threshold:.1f}      {len(executed):4d}      {len(wrong):4d}")

    print("\nwrong answers:")
    for case, decision, _ in rows:
        if decision.action != case["expected"]:
            print(f"  #{case['id']:<2d} expected={case['expected']:<24s} got={decision.action:<24s} conf={decision.confidence:.2f}")

    times = sorted(row[2] for row in rows)
    print(f"\nlatency ms: p50={statistics.median(times):.0f} max={times[-1]:.0f} (n={len(times)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
