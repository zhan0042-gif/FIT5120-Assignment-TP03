"""Compare hosted models on the safety Q&A question set. Run by hand; not part of CI.

    cd backend
    .venv/bin/python scripts/guidance_router_eval.py --model <model-id>

The key is read from the AI_API_KEY environment variable, or failing that from the
AI_API_KEY line of the repository's .env file. Only that line is read; the file is
never run as a shell script, because it is not valid shell and a failed parse can
print its contents.

The questions are fixed test sentences and carry no household data. A pause between
calls keeps the run under the hosted model's per-minute quota.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.nvidia_guidance_router import (  # noqa: E402
    DEFAULT_ROUTER_MODEL,
    NvidiaGuidanceRouter,
)
from app.schemas.safety_guidance import GuidanceCatalogueItem  # noqa: E402
from app.services.guidance_eval import evaluate, format_report, load_cases  # noqa: E402
from app.services.safety_guidance import DEFAULT_ENTRIES  # noqa: E402

DEFAULT_CASES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "guidance_router_eval.json"


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def read_key(env_file: Path) -> str:
    """AI_API_KEY from the environment, else from that one line of the env file."""

    key = os.getenv("AI_API_KEY", "").strip()
    if key or not env_file.exists():
        return key
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("AI_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_ROUTER_MODEL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--pause", type=float, default=1.6, help="seconds between calls")
    args = parser.parse_args()

    api_key = read_key(args.env_file)
    if not api_key:
        print("AI_API_KEY is not set.", file=sys.stderr)
        return 2

    catalogue = [
        GuidanceCatalogueItem(id=entry.id, question=entry.question, asked_as=entry.asked_as)
        for entry in DEFAULT_ENTRIES
        if entry.reviewed_by is not None
    ]
    if not catalogue:
        print("No reviewed entries to route to.", file=sys.stderr)
        return 2

    router = NvidiaGuidanceRouter(api_key=api_key, model=args.model)
    report = evaluate(router, catalogue, load_cases(args.cases), pause_seconds=args.pause)
    print(format_report(report, args.model))
    return 0 if report.meets_bar() else 1


if __name__ == "__main__":
    raise SystemExit(main())
