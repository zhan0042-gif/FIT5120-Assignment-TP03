"""Append one line per voice turn, with personal content removed unless allowed.

Transcripts hold member names and home addresses. They are written only when
VOICE_LOG_CONTENT is switched on, and the application logger never sees them.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.voice import VoiceTurnLog

logger = logging.getLogger(__name__)

# Answers that say which command or which yes/no was chosen, never what was said.
# The browser writes the command answer as a target id, not the spoken phrase.
CONTENT_FREE_ANSWERS = frozenset({"command", "checked", "confirm", "stop"})


class VoiceTurnLogger:
    def __init__(self, path: Path, *, include_content: bool) -> None:
        self._path = path
        self._include_content = include_content

    def record(self, turn: VoiceTurnLog, *, now: datetime | None = None) -> None:
        """Never raises: a missed log line must not reach the user."""
        entry = {
            "ts": (now or datetime.now(timezone.utc)).isoformat(),
            **self._redacted(turn).model_dump(mode="json"),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # The record itself is deliberately absent from this message.
            logger.warning("A voice turn could not be written to the voice log.")

    def _redacted(self, turn: VoiceTurnLog) -> VoiceTurnLog:
        if self._include_content:
            return turn
        answers = [
            answer
            if answer.id in CONTENT_FREE_ANSWERS
            else answer.model_copy(update={"answer": None})
            for answer in turn.answers
        ]
        action = turn.action.model_copy(update={"value": None}) if turn.action else None
        return turn.model_copy(
            update={"transcript": None, "answers": answers, "action": action}
        )
