# Voice Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating microphone button that lets a user move around FIREBREAK, press buttons and fill in their plan by speaking, with every command resolved against actions the current page has declared.

**Architecture:** Pages register *targets* (a label plus a `run` function that uses the same code path as the mouse). When an utterance is final, the voice store snapshots the targets, turns them into a batch of typed questions, and asks a judgement engine through the backend, which validates every answer against the options it was offered. A pure policy module turns the answers and their probabilities into execute / confirm / dictate / reject, and every turn is logged to a JSONL file with personal content removed by default. The live JEV client is out of this plan; a deterministic mock judge stands in so everything runs locally today.

**Tech Stack:** FastAPI · Pydantic v2 · pytest · Vue 3 (`<script setup>`, plain JS) · Pinia setup stores · Vue Router · Web Speech API · Node built-in test runner

**Spec:** `docs/design/specs/2026-09-28-voice-control-design.md`

## Global Constraints

- Branch: `experiment/sandbox`. Local experiment; nothing here is deployed.
- Commits: conventional with a scope (`feat(backend): …`, `feat(frontend): …`, `docs: …`). **No `Co-Authored-By`, `Claude-Session` or "Generated with Claude Code" lines** — this repository's owner has asked for none.
- No new dependency, frontend or backend.
- **The judge never writes.** Every answer must be one of the options it was offered (`"yes"`/`"no"` for yes/no questions). The backend turns anything else into `503`, never passes it on.
- **Voice acts only through a registered target's `run`.** No voice code writes to a form, a store or the plan API directly; the only endpoints the voice store calls are `/voice/judge` and `/voice/log`.
- Thresholds, exactly: act at `0.85`, ask at `0.5`. A decision's confidence is the minimum of the answers it uses.
- Limits, exactly: transcript ≤ 500 characters; ≤ 100 questions; ≤ 100 options per question; command options ≤ 99 targets + `none of these`; ≤ 300 targets in `state`; a target's `current` ≤ 500 characters; ≤ 9 address suggestions.
- Session: ends on the button, on `stop` / `cancel` / `stop listening` (exact, trailing punctuation ignored), after 30 s of silence, or after 2 failed turns in a row. Address suggestions are awaited for 3 s.
- Speech recognition language `en-AU`; supported in Chrome and Edge.
- Transcripts, span values and addresses never reach the application logger or an error message. The turn log is the only place they may appear, and only when `VOICE_LOG_CONTENT=true`. Redaction happens on the backend.
- Australian English in all user-facing copy.
- Backend tests: `cd backend && .venv/bin/pytest` (keyless; `tests/conftest.py` sets mock modes). Frontend tests: `cd frontend && npm test`. Frontend build: `cd frontend && npm run build`.

## Review Focus

- **A page offering more targets than the judge accepts** (a large household on the People step): the command question must stay within 100 options, keeping the earliest-registered targets (the global pages and scroll commands) rather than failing with `422`. Pinned in Task 5.
- **Punctuation from speech recognition** ("Stop.", "Name is Minh."): stop must still stop, and span values must not carry the full stop into the plan. Pinned in Task 5 (spans) and Task 9 (stop).
- **Numbers said as words** ("quantity is two"): must become `2`, and something that is not a whole number must be refused with a message rather than written as `NaN`. Pinned in Task 4.
- **A row renamed between hearing and acting** (the label in the snapshot is stale): the executor must act on the live target with the same id, not the stale copy. Pinned in Task 7.
- **The floating button covering controls** — the plan builder's Save plan button sits at the bottom of the screen, and the printable plan must not include the button. Pinned by manual checks in Task 10.

---

### Task 1: Voice contract, judgement boundary, mock judge and selection

**Files:**
- Create: `backend/app/schemas/voice.py`
- Create: `backend/app/providers/jev_judgement.py`
- Modify: `backend/app/providers/interfaces.py`
- Modify: `backend/app/providers/mock.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/dependencies.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Test: `backend/tests/test_voice_judgement.py`

**Interfaces:**
- Consumes: `ExternalDataUnavailable` from `app.core.exceptions`
- Produces:
  - `app.schemas.voice`: `VoiceTarget`, `VoiceState(page, step, mode, transcript, targets)`, `VoiceQuestion(id, type, options)`, `VoiceJudgeRequest(state, questions)`, `VoiceAnswer(id, answer, probability)`, `VoiceJudgeResponse(answers)`, constants `MAX_TRANSCRIPT_CHARS = 500`, `MAX_QUESTIONS = 100`, `MAX_OPTIONS = 100`, `MAX_TARGETS = 300`
  - `JudgementClient` Protocol: `judge(state: VoiceState, questions: list[VoiceQuestion]) -> list[VoiceAnswer]`
  - `MockJudgementClient`, `DisabledJudgementClient`
  - `app.core.config.voice_mode() -> str` (`"off"` | `"mock"`), `ExternalProviders.judgement`
  - `app.core.dependencies.get_judgement_client() -> JudgementClient`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voice_judgement.py`:

```python
import pytest

from app.core.config import build_external_providers
from app.core.exceptions import ExternalDataUnavailable
from app.providers.jev_judgement import DisabledJudgementClient
from app.providers.mock import MockJudgementClient
from app.schemas.voice import VoiceQuestion, VoiceState


def _state(transcript: str) -> VoiceState:
    return VoiceState(page="plan-builder", transcript=transcript)


def _pick(question_id: str, *options: str) -> VoiceQuestion:
    return VoiceQuestion(id=question_id, type="pick_one", options=list(options))


def _yes_no(question_id: str) -> VoiceQuestion:
    return VoiceQuestion(id=question_id, type="yes_no")


def _judge(transcript: str, question: VoiceQuestion):
    [answer] = MockJudgementClient().judge(_state(transcript), [question])
    return answer


def test_the_mock_picks_the_option_sharing_the_most_naming_words() -> None:
    answer = _judge(
        "primary transport is a van",
        _pick(
            "command",
            "go to Overview",
            "set Primary transport",
            "set Backup transport (backup 1)",
            "none of these",
        ),
    )
    assert answer.answer == "set Primary transport"
    assert answer.probability >= 0.85


def test_the_mock_prefers_the_phrase_the_user_actually_said_on_a_tie() -> None:
    # "go back" names the same thing as the plan builder's Back button; the
    # words "go back" were said, "press" was not.
    answer = _judge(
        "go back",
        _pick("command", "go back", "press Back, or say previous step", "none of these"),
    )
    assert answer.answer == "go back"
    assert answer.probability >= 0.85


def test_a_button_alias_counts_as_its_own_phrasing() -> None:
    answer = _judge(
        "next step",
        _pick("command", "press Continue, or say next step", "scroll down", "none of these"),
    )
    assert answer.answer == "press Continue, or say next step"


def test_a_possessive_names_the_person() -> None:
    answer = _judge(
        "Minh's relationship is parent",
        _pick(
            "command",
            "set Relationship to household (Minh)",
            "set Relationship to household (Lan)",
            "none of these",
        ),
    )
    assert answer.answer == "set Relationship to household (Minh)"


def test_the_mock_answers_none_when_nothing_matches() -> None:
    answer = _judge(
        "what a lovely day", _pick("command", "go to Overview", "none of these")
    )
    assert answer.answer == "none of these"


def test_an_unbroken_tie_is_never_confident() -> None:
    answer = _judge(
        "set the name",
        _pick("command", "fill in Name (member 1)", "fill in Name (member 2)", "none of these"),
    )
    assert answer.answer == "fill in Name (member 1)"
    assert answer.probability <= 0.6


def test_the_mock_takes_the_value_after_a_cue_word() -> None:
    answer = _judge(
        "name is Minh", _pick("span", "name", "name is", "is Minh", "Minh", "(none)")
    )
    assert answer.answer == "Minh"


def test_the_mock_finds_no_value_without_a_cue_word() -> None:
    answer = _judge("fill in the name", _pick("span", "fill", "the name", "(none)"))
    assert answer.answer == "(none)"


def test_stop_confirm_and_checked_read_the_transcript() -> None:
    assert _judge("never mind", _yes_no("stop")).answer == "yes"
    assert _judge("scroll to the top", _yes_no("stop")).answer == "no"
    assert _judge("yes please", _yes_no("confirm")).answer == "yes"
    assert _judge("no", _yes_no("confirm")).answer == "no"
    unclear = _judge("hmm", _yes_no("confirm"))
    assert unclear.probability < 0.5
    assert _judge("Minh is not a dependant", _yes_no("checked")).answer == "no"
    assert _judge("Minh is a dependant", _yes_no("checked")).answer == "yes"


def test_the_mock_understands_which_suggestion_was_named() -> None:
    options = (
        "1 first: 12 Smith St, Ballarat VIC 3350",
        "2 second: 12 Smith Rd, Sale VIC 3850",
        "none",
    )
    assert _judge("the second one", _pick("suggestion", *options)).answer == options[1]
    assert _judge("number one", _pick("suggestion", *options)).answer == options[0]
    assert _judge("none of them", _pick("suggestion", *options)).answer == "none"


def test_the_mock_is_deterministic_and_its_probabilities_are_real() -> None:
    questions = [
        _pick("command", "go to Fire Map", "scroll down", "none of these"),
        _pick("span", "fire", "fire map", "(none)"),
        _yes_no("checked"),
        _yes_no("stop"),
    ]
    first = MockJudgementClient().judge(_state("go to fire map"), questions)
    second = MockJudgementClient().judge(_state("go to fire map"), questions)
    assert first == second
    assert all(0.0 <= answer.probability <= 1.0 for answer in first)
    assert [answer.id for answer in first] == ["command", "span", "checked", "stop"]


def test_the_disabled_judge_refuses() -> None:
    with pytest.raises(ExternalDataUnavailable):
        DisabledJudgementClient().judge(_state("go to fire map"), [_yes_no("stop")])


def test_mock_data_mode_always_uses_the_mock_judge(monkeypatch) -> None:
    monkeypatch.delenv("APP_VOICE_MODE", raising=False)
    assert isinstance(build_external_providers("mock").judgement, MockJudgementClient)


def test_live_data_mode_switches_voice_off_by_default(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.delenv("APP_VOICE_MODE", raising=False)
    assert isinstance(build_external_providers("live").judgement, DisabledJudgementClient)


def test_live_data_mode_can_use_the_mock_judge(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("APP_VOICE_MODE", "mock")
    assert isinstance(build_external_providers("live").judgement, MockJudgementClient)


def test_an_unknown_voice_mode_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key")
    monkeypatch.setenv("APP_VOICE_MODE", "jev")
    with pytest.raises(RuntimeError, match="APP_VOICE_MODE"):
        build_external_providers("live")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_voice_judgement.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.providers.jev_judgement'`.

- [ ] **Step 3: Create the voice schema**

Create `backend/app/schemas/voice.py`:

```python
"""Voice control API contract: a judgement batch and its answers.

The judge chooses among options the page offered. It never writes text, so a
batch is a set of small typed questions, and an answer is always one of the
options it was given ("yes"/"no" for a yes/no question).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

MAX_TRANSCRIPT_CHARS = 500
MAX_QUESTIONS = 100
MAX_OPTIONS = 100
MAX_TARGETS = 300

OptionText = Annotated[str, Field(min_length=1, max_length=300)]


class VoiceTarget(BaseModel):
    """What the page offers, as the judge sees it. Handlers stay in the browser."""

    id: str = Field(min_length=1, max_length=160)
    kind: Literal["page", "command", "button", "select", "text", "checkbox", "address"]
    label: str = Field(min_length=1, max_length=300)
    current: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)


class VoiceState(BaseModel):
    page: str = Field(min_length=1, max_length=80)
    step: str | None = Field(default=None, max_length=80)
    mode: Literal["normal", "confirming", "choosing"] = "normal"
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARS)
    targets: list[VoiceTarget] = Field(default_factory=list, max_length=MAX_TARGETS)


class VoiceQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    type: Literal["pick_one", "yes_no"]
    options: list[OptionText] = Field(default_factory=list, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def _options_fit_the_type(self) -> "VoiceQuestion":
        if self.type == "pick_one" and not self.options:
            raise ValueError("A pick_one question needs at least one option.")
        if self.type == "yes_no" and self.options:
            raise ValueError("A yes_no question takes no options.")
        return self


class VoiceJudgeRequest(BaseModel):
    state: VoiceState
    questions: list[VoiceQuestion] = Field(min_length=1, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _question_ids_are_unique(self) -> "VoiceJudgeRequest":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question ids must be unique.")
        return self


class VoiceAnswer(BaseModel):
    """Deliberately unconstrained: the service decides whether to trust it."""

    id: str
    answer: str
    probability: float


class VoiceJudgeResponse(BaseModel):
    answers: list[VoiceAnswer]
```

- [ ] **Step 4: Add the Protocol**

In `backend/app/providers/interfaces.py`, below the existing line `from app.schemas.rendezvous import RendezvousResult`, add:

```python
from app.schemas.voice import VoiceAnswer, VoiceQuestion, VoiceState
```

Append to the end of the file:

```python
class JudgementClient(Protocol):
    """Answer a batch of typed questions about one spoken command.

    Every answer is one of the options offered, with a probability. The
    implementation never writes text.
    """

    def judge(
        self, state: VoiceState, questions: list[VoiceQuestion]
    ) -> list[VoiceAnswer]: ...
```

- [ ] **Step 5: Create the disabled judge**

Create `backend/app/providers/jev_judgement.py`:

```python
"""JEV judgement engine adapter.

JEV answers a batch of small typed questions about a spoken command in one
request, with a probability per answer, and never writes text.

Only the disabled stand-in lives here for now. The live client joins it once
JEV's interface documentation is available (see the voice control design spec,
"Open until JEV's documentation arrives").
"""

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.voice import VoiceAnswer, VoiceQuestion, VoiceState


class DisabledJudgementClient:
    """Stands in when voice judging is switched off.

    Voice control is an optional extra. Switched off, it refuses politely and
    the endpoint answers 503; the rest of the application is unaffected.
    """

    def judge(
        self, state: VoiceState, questions: list[VoiceQuestion]
    ) -> list[VoiceAnswer]:
        raise ExternalDataUnavailable("Voice commands are not configured.")
```

- [ ] **Step 6: Add the mock judge**

In `backend/app/providers/mock.py`, add `import re` to the standard-library imports at the top, and below `from app.schemas.households import …` add:

```python
from app.schemas.voice import VoiceAnswer, VoiceQuestion, VoiceState
```

Append to the end of the file:

```python
_TOKEN = re.compile(r"[a-z0-9']+")
# Words that say what kind of command a phrase is, not which target it names.
_COMMAND_WORDS = {
    "go", "to", "press", "set", "fill", "in", "tick", "or", "untick", "enter",
    "the", "address", "for", "say", "a", "an", "of",
}
_STOP_WORDS = {"stop", "cancel"}
_STOP_PHRASES = ("never mind", "forget it")
_YES_WORDS = {"yes", "yeah", "yep", "sure", "correct", "ok", "okay", "confirm"}
_NO_WORDS = {"no", "nope", "don't", "not"}
_NEGATIONS = {"not", "no", "untick", "uncheck", "isn't", "doesn't", "can't", "cannot", "don't"}
_VALUE_CUES = {"is", "to", "called", "named", "as"}
_NONE_OPTIONS = {"none of these", "(none)", "none"}
_ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                  "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
_DIGITS = {str(number): number for number in range(1, 10)}
_CARDINALS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
              "six": 6, "seven": 7, "eight": 8, "nine": 9}


class MockJudgementClient:
    """Word-overlap stand-in for JEV, for tests and for trying voice control locally.

    Deterministic and deliberately simple. It is not a model of how JEV judges;
    it exists so everything around the judge can be built and exercised.
    """

    def judge(
        self, state: VoiceState, questions: list[VoiceQuestion]
    ) -> list[VoiceAnswer]:
        heard = state.transcript.lower()
        tokens = _tokens(heard)
        answers = []
        for question in questions:
            if question.type == "yes_no":
                answer, probability = _yes_no(question.id, heard, set(tokens))
            elif question.id == "span":
                answer, probability = _span(question.options, tokens)
            elif question.id == "suggestion":
                answer, probability = _suggestion(question.options, tokens)
            else:
                answer, probability = _best_overlap(question.options, set(tokens))
            answers.append(
                VoiceAnswer(id=question.id, answer=answer, probability=probability)
            )
        return answers


def _tokens(text: str) -> list[str]:
    """Lower-case words, with possessives reduced ("Minh's" → "minh")."""
    return [
        token[:-2] if token.endswith("'s") else token
        for token in _TOKEN.findall(text.lower())
    ]


def _yes_no(question_id: str, heard: str, words: set[str]) -> tuple[str, float]:
    if question_id == "stop":
        said = bool(words & _STOP_WORDS) or any(p in heard for p in _STOP_PHRASES)
        return ("yes" if said else "no"), 0.95
    if question_id == "checked":
        return ("no" if words & _NEGATIONS else "yes"), 0.9
    if words & _YES_WORDS and not words & _NO_WORDS:
        return "yes", 0.95
    if words & _NO_WORDS:
        return "no", 0.95
    return "no", 0.4


def _none_option(options: list[str]) -> str:
    return next((o for o in options if o.lower() in _NONE_OPTIONS), options[-1])


def _span(options: list[str], tokens: list[str]) -> tuple[str, float]:
    cues = [index for index, token in enumerate(tokens) if token in _VALUE_CUES]
    if cues:
        value = " ".join(tokens[cues[-1] + 1 :])
        for option in options:
            if value and " ".join(_tokens(option)) == value:
                return option, 0.9
    return _none_option(options), 0.9


def _suggestion(options: list[str], tokens: list[str]) -> tuple[str, float]:
    for table in (_ORDINAL_WORDS, _DIGITS, _CARDINALS):
        for token in tokens:
            if token in table:
                prefix = f"{table[token]} "
                for option in options:
                    if option.startswith(prefix):
                        return option, 0.95
    if "none" in tokens:
        return _none_option(options), 0.95
    return _none_option(options), 0.3


def _overlap(option: str, words: set[str]) -> tuple[float, int]:
    """Share of the option's naming words that were said, then raw words in common."""
    best = 0.0
    for alternative in option.lower().split(", or say "):
        alternative_words = set(_tokens(alternative))
        naming = (alternative_words - _COMMAND_WORDS) or alternative_words
        if naming:
            best = max(best, len(naming & words) / len(naming))
    return best, len(set(_tokens(option)) & words)


def _best_overlap(options: list[str], words: set[str]) -> tuple[str, float]:
    best: tuple[float, int] | None = None
    best_index = 0
    tied = False
    for index, option in enumerate(options):
        if option.lower() in _NONE_OPTIONS:
            continue
        key = _overlap(option, words)
        if key[0] == 0:
            continue
        if best is None or key > best:
            best, best_index, tied = key, index, False
        elif key == best:
            tied = True
    if best is None:
        none = _none_option(options)
        return none, (0.9 if none.lower() in _NONE_OPTIONS else 0.2)
    probability = 0.5 + 0.45 * best[0]
    if tied:
        probability = min(probability, 0.6)
    return options[best_index], round(probability, 2)
```

- [ ] **Step 7: Select the judge**

In `backend/app/core/config.py`:

Add `JudgementClient` to the `from app.providers.interfaces import (…)` list, `MockJudgementClient` to the `from app.providers.mock import (…)` list, and a new import below the NVIDIA import:

```python
from app.providers.jev_judgement import DisabledJudgementClient
```

Add a field to the end of `ExternalProviders`:

```python
    judgement: JudgementClient
```

Add below `spatial_cache_max_age()`:

```python
def voice_mode() -> str:
    """Which judge answers voice commands in live data mode.

    Mock data mode always uses the mock judge. The live JEV client adds a third
    value once it exists.
    """
    mode = os.getenv("APP_VOICE_MODE", "off").strip().lower()
    if mode not in {"off", "mock"}:
        raise RuntimeError("APP_VOICE_MODE must be either 'off' or 'mock'.")
    return mode
```

Add below `_explanation_client`:

```python
def _judgement_client(mode: str) -> JudgementClient:
    """Voice control is optional; switched off, it refuses rather than stopping the app."""
    if mode == "mock":
        return MockJudgementClient()
    return DisabledJudgementClient()
```

In `build_external_providers`, add `judgement=MockJudgementClient(),` to the mock `ExternalProviders(…)` and `judgement=_judgement_client(voice_mode()),` to the live one.

- [ ] **Step 8: Expose it as a dependency**

In `backend/app/core/dependencies.py`, add `JudgementClient` to the `from app.providers.interfaces import (…)` list and append:

```python
def get_judgement_client() -> JudgementClient:
    return _external_providers.judgement
```

- [ ] **Step 9: Pass the setting through Compose and document it**

In `docker-compose.yml`, under `backend:` → `environment:`, below `AI_API_KEY: ${AI_API_KEY:-}` add:

```yaml
      APP_VOICE_MODE: ${APP_VOICE_MODE:-off}
```

Append to `.env.example`:

```bash

# Voice control judge in live data mode: "off" (default) or "mock". Mock data
# mode always uses the mock judge. The live JEV judge is not connected yet.
APP_VOICE_MODE=off
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_voice_judgement.py -v`
Expected: 16 passed.

Run: `cd backend && .venv/bin/pytest`
Expected: all pass (the existing `build_external_providers` tests still pass because `judgement` is always supplied).

Run: `cd backend && APP_DATA_MODE=mock .venv/bin/python -c "from app.main import app"`
Expected: no output, exit 0.

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas/voice.py backend/app/providers/jev_judgement.py \
  backend/app/providers/interfaces.py backend/app/providers/mock.py \
  backend/app/core/config.py backend/app/core/dependencies.py \
  backend/tests/test_voice_judgement.py docker-compose.yml .env.example
git commit -m "feat(backend): add the voice judgement boundary and mock judge"
```

---

### Task 2: Judge endpoint that trusts only offered answers

**Files:**
- Create: `backend/app/services/voice.py`
- Create: `backend/app/api/routes/voice.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_voice_endpoint.py`

**Interfaces:**
- Consumes: everything Task 1 produces
- Produces:
  - `VoiceJudgementService(client).judge(request: VoiceJudgeRequest) -> VoiceJudgeResponse`
  - `POST /api/v1/voice/judge` → `200 {"answers": [{"id", "answer", "probability"}]}` in question order; `422` on an invalid batch; `503` when the judge is off or answers malformed
  - `app.api.routes.voice.router` (Task 3 adds the log route to it)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voice_endpoint.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_judgement_client
from app.main import app
from app.providers.jev_judgement import DisabledJudgementClient
from app.schemas.voice import VoiceAnswer

COMMAND = {
    "id": "command",
    "type": "pick_one",
    "options": ["set Primary transport", "none of these"],
}
STOP = {"id": "stop", "type": "yes_no", "options": []}


def _batch(transcript: str = "primary transport is a van", questions=None) -> dict:
    return {
        "state": {
            "page": "plan-builder",
            "step": "destinations",
            "mode": "normal",
            "transcript": transcript,
            "targets": [
                {"id": "primary-transport", "kind": "select",
                 "label": "Primary transport", "current": "Not set"},
            ],
        },
        "questions": questions if questions is not None else [COMMAND, STOP],
    }


class ScriptedClient:
    def __init__(self, answers: list[VoiceAnswer]) -> None:
        self.answers = answers

    def judge(self, state, questions):
        return self.answers


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _use(judge) -> None:
    app.dependency_overrides[get_judgement_client] = lambda: judge


def test_the_mock_judge_answers_every_question_in_order(client) -> None:
    response = client.post("/api/v1/voice/judge", json=_batch())

    assert response.status_code == 200
    answers = response.json()["answers"]
    assert [answer["id"] for answer in answers] == ["command", "stop"]
    assert answers[0]["answer"] == "set Primary transport"
    assert answers[1]["answer"] == "no"


@pytest.mark.parametrize(
    "body",
    [
        _batch(transcript="x" * 501),
        _batch(questions=[{"id": f"q{i}", "type": "yes_no", "options": []} for i in range(101)]),
        _batch(questions=[{"id": "command", "type": "pick_one",
                           "options": [f"option {i}" for i in range(101)]}]),
        _batch(questions=[STOP, STOP]),
        _batch(questions=[{"id": "stop", "type": "yes_no", "options": ["yes"]}]),
        _batch(questions=[{"id": "command", "type": "pick_one", "options": []}]),
        _batch(questions=[]),
    ],
    ids=[
        "long transcript", "too many questions", "too many options",
        "duplicate ids", "yes_no with options", "pick_one without options",
        "no questions",
    ],
)
def test_an_invalid_batch_is_refused(client, body) -> None:
    assert client.post("/api/v1/voice/judge", json=body).status_code == 422


def test_a_switched_off_judge_is_unavailable(client) -> None:
    _use(DisabledJudgementClient())
    response = client.post("/api/v1/voice/judge", json=_batch())
    assert response.status_code == 503


@pytest.mark.parametrize(
    "answers",
    [
        [VoiceAnswer(id="command", answer="delete everything", probability=0.99),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=1.5),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="stop", answer="maybe", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="stop", answer="no", probability=0.9),
         VoiceAnswer(id="extra", answer="no", probability=0.9)],
        [VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
         VoiceAnswer(id="command", answer="none of these", probability=0.9),
         VoiceAnswer(id="stop", answer="no", probability=0.9)],
    ],
    ids=[
        "option not offered", "question unanswered", "impossible probability",
        "yes_no not yes or no", "question not asked", "question answered twice",
    ],
)
def test_an_answer_the_judge_had_no_basis_for_is_unavailable(client, answers) -> None:
    _use(ScriptedClient(answers))
    response = client.post("/api/v1/voice/judge", json=_batch())

    assert response.status_code == 503
    # The failure message must never echo what the user said.
    assert "van" not in response.text


def test_answers_come_back_in_question_order(client) -> None:
    _use(ScriptedClient([
        VoiceAnswer(id="stop", answer="no", probability=0.9),
        VoiceAnswer(id="command", answer="set Primary transport", probability=0.9),
    ]))
    answers = client.post("/api/v1/voice/judge", json=_batch()).json()["answers"]
    assert [answer["id"] for answer in answers] == ["command", "stop"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_voice_endpoint.py -v`
Expected: the `422` cases and the others FAIL with `404 != …` — the route does not exist yet.

- [ ] **Step 3: Write the service**

Create `backend/app/services/voice.py`:

```python
"""Voice judgement: ask the judge, then refuse any answer it had no basis to give."""

import math

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import JudgementClient
from app.schemas.voice import (
    VoiceAnswer,
    VoiceJudgeRequest,
    VoiceJudgeResponse,
    VoiceQuestion,
)

YES_NO_ANSWERS = ("yes", "no")


class VoiceJudgementService:
    def __init__(self, client: JudgementClient) -> None:
        self._client = client

    def judge(self, request: VoiceJudgeRequest) -> VoiceJudgeResponse:
        answers = self._client.judge(request.state, request.questions)
        return VoiceJudgeResponse(answers=_checked(answers, request.questions))


def _checked(
    answers: list[VoiceAnswer], questions: list[VoiceQuestion]
) -> list[VoiceAnswer]:
    """Every question answered exactly once, from its own options, with a real probability.

    The browser acts on these answers. An answer the judge was never offered is
    treated as a failed call, never passed on. Messages here never include what
    was said: they reach the client and may reach logs.
    """
    by_id: dict[str, VoiceAnswer] = {}
    for answer in answers:
        if answer.id in by_id:
            raise ExternalDataUnavailable("The voice judge answered a question twice.")
        by_id[answer.id] = answer

    ordered = []
    for question in questions:
        answer = by_id.pop(question.id, None)
        if answer is None:
            raise ExternalDataUnavailable("The voice judge left a question unanswered.")
        allowed = question.options if question.type == "pick_one" else YES_NO_ANSWERS
        if answer.answer not in allowed:
            raise ExternalDataUnavailable("The voice judge gave an answer it was not offered.")
        if not math.isfinite(answer.probability) or not 0.0 <= answer.probability <= 1.0:
            raise ExternalDataUnavailable("The voice judge gave an impossible probability.")
        ordered.append(answer)

    if by_id:
        raise ExternalDataUnavailable("The voice judge answered a question it was not asked.")
    return ordered
```

- [ ] **Step 4: Write the route**

Create `backend/app/api/routes/voice.py`:

```python
"""Voice control: judge a spoken command against the page's own options."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_judgement_client
from app.providers.interfaces import JudgementClient
from app.schemas.voice import VoiceJudgeRequest, VoiceJudgeResponse
from app.services.voice import VoiceJudgementService

router = APIRouter(prefix="/voice", tags=["voice"])
JudgementDependency = Annotated[JudgementClient, Depends(get_judgement_client)]


@router.post("/judge", response_model=VoiceJudgeResponse)
def judge_voice_command(
    request: VoiceJudgeRequest, client: JudgementDependency
) -> VoiceJudgeResponse:
    """Answer the page's question batch about one finished utterance.

    Stateless: nothing is stored, and the plan is never read or changed here.
    """
    return VoiceJudgementService(client).judge(request)
```

In `backend/app/api/router.py`, add the import below the scenarios import:

```python
from app.api.routes.voice import router as voice_router
```

and the registration at the end:

```python
router.include_router(voice_router, prefix="/v1")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_voice_endpoint.py -v`
Expected: 16 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/voice.py backend/app/api/routes/voice.py \
  backend/app/api/router.py backend/tests/test_voice_endpoint.py
git commit -m "feat(backend): add the voice judge endpoint"
```

---

### Task 3: Turn log with backend redaction

**Files:**
- Modify: `backend/app/schemas/voice.py`
- Create: `backend/app/services/voice_log.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/api/routes/voice.py`
- Modify: `docker-compose.yml`, `.env.example`, `.gitignore`
- Test: `backend/tests/test_voice_log.py`

**Interfaces:**
- Consumes: `router` from Task 2
- Produces:
  - `VoiceTurnLog`, `VoiceLoggedAnswer`, `VoiceLoggedAction`, `VoiceLatency`, `VoiceLogAccepted` in `app.schemas.voice`
  - `VoiceTurnLogger(path: Path, *, include_content: bool).record(turn, *, now=None) -> None` (never raises)
  - `app.core.config.voice_log_settings() -> tuple[Path, bool]`
  - `app.core.dependencies.get_voice_turn_logger() -> VoiceTurnLogger`
  - `POST /api/v1/voice/log` → `202 {"accepted": true}`
  - The frontend (Task 9) sends exactly these values: `mode` ∈ `normal | confirming | choosing | dictating`; `decision` ∈ `execute | confirm | dictate | choose | keep | reject | stop | cancel | unclear | dictated | unavailable`; `outcome` ∈ `ok | fail | pending | none`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voice_log.py`:

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import voice_log_settings
from app.core.dependencies import get_voice_turn_logger
from app.main import app
from app.schemas.voice import VoiceTurnLog
from app.services.voice_log import VoiceTurnLogger

TURN = {
    "turn_id": "vt_1",
    "page": "plan-builder",
    "step": "destinations",
    "mode": "normal",
    "transcript": "primary transport is a van",
    "answers": [
        {"id": "command", "answer": "primary-transport", "probability": 0.94},
        {"id": "option:primary-transport", "answer": "Van", "probability": 0.97},
        {"id": "span", "answer": "a van", "probability": 0.9},
        {"id": "stop", "answer": "no", "probability": 0.95},
    ],
    "decision": "execute",
    "action": {"kind": "select", "target": "primary-transport", "value": "Van"},
    "outcome": "ok",
    "latency_ms": {"judge": 240, "turn": 310},
}
NOW = datetime(2026, 9, 28, 10, 14, 3, tzinfo=timezone.utc)


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _record(path: Path, include_content: bool) -> None:
    VoiceTurnLogger(path, include_content=include_content).record(
        VoiceTurnLog.model_validate(TURN), now=NOW
    )


def test_a_turn_is_one_json_line_with_content_when_allowed(tmp_path) -> None:
    path = tmp_path / "logs" / "voice.jsonl"
    _record(path, include_content=True)

    [entry] = _lines(path)
    assert entry["ts"] == "2026-09-28T10:14:03+00:00"
    assert entry["transcript"] == "primary transport is a van"
    assert entry["action"]["value"] == "Van"
    assert entry["latency_ms"] == {"judge": 240, "turn": 310}


def test_each_turn_appends_a_line(tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    _record(path, include_content=True)
    _record(path, include_content=True)
    assert len(_lines(path)) == 2


def test_content_is_removed_unless_allowed(tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    _record(path, include_content=False)

    [entry] = _lines(path)
    assert entry["transcript"] is None
    assert entry["action"] == {"kind": "select", "target": "primary-transport", "value": None}
    answers = {answer["id"]: answer for answer in entry["answers"]}
    assert answers["command"]["answer"] == "primary-transport"
    assert answers["stop"]["answer"] == "no"
    assert answers["option:primary-transport"] == {
        "id": "option:primary-transport", "answer": None, "probability": 0.97,
    }
    assert answers["span"]["answer"] is None
    assert "van" not in path.read_text(encoding="utf-8").lower()


def test_a_failed_write_neither_raises_nor_leaks(tmp_path, caplog) -> None:
    # A directory cannot be opened for appending.
    with caplog.at_level(logging.WARNING):
        _record(tmp_path, include_content=True)

    assert "could not be written" in caplog.text
    assert "primary transport" not in caplog.text


def test_settings_default_to_a_local_file_without_content(monkeypatch) -> None:
    monkeypatch.delenv("VOICE_LOG_PATH", raising=False)
    monkeypatch.delenv("VOICE_LOG_CONTENT", raising=False)
    assert voice_log_settings() == (Path("logs/voice-turns.jsonl"), False)


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes"])
def test_content_can_be_switched_on(monkeypatch, raw) -> None:
    monkeypatch.setenv("VOICE_LOG_CONTENT", raw)
    monkeypatch.setenv("VOICE_LOG_PATH", "/tmp/elsewhere.jsonl")
    assert voice_log_settings() == (Path("/tmp/elsewhere.jsonl"), True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_the_endpoint_accepts_and_writes_a_turn(client, tmp_path) -> None:
    path = tmp_path / "voice.jsonl"
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        path, include_content=False
    )

    response = client.post("/api/v1/voice/log", json=TURN)

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert len(_lines(path)) == 1


def test_the_endpoint_accepts_even_when_the_write_fails(client, tmp_path) -> None:
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        tmp_path, include_content=False
    )
    assert client.post("/api/v1/voice/log", json=TURN).status_code == 202


def test_the_endpoint_refuses_an_unknown_decision(client, tmp_path) -> None:
    app.dependency_overrides[get_voice_turn_logger] = lambda: VoiceTurnLogger(
        tmp_path / "voice.jsonl", include_content=False
    )
    body = {**TURN, "decision": "improvise"}
    assert client.post("/api/v1/voice/log", json=body).status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_voice_log.py -v`
Expected: collection error, `ImportError: cannot import name 'voice_log_settings'`.

- [ ] **Step 3: Add the log models**

Append to `backend/app/schemas/voice.py`:

```python
class VoiceLoggedAnswer(BaseModel):
    """`answer` may be withheld; the probability always stays."""

    id: str = Field(min_length=1, max_length=160)
    answer: str | None = Field(default=None, max_length=300)
    probability: float = Field(ge=0.0, le=1.0)


class VoiceLoggedAction(BaseModel):
    """`target` is a target id, never a spoken label: labels can hold member names."""

    kind: Literal["page", "command", "button", "select", "text", "checkbox", "address"]
    target: str = Field(min_length=1, max_length=160)
    value: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)


class VoiceLatency(BaseModel):
    judge: int | None = Field(default=None, ge=0, le=600_000)
    turn: int = Field(ge=0, le=600_000)


class VoiceTurnLog(BaseModel):
    """One finished utterance: what was heard, what was chosen, what happened."""

    turn_id: str = Field(min_length=1, max_length=80)
    page: str | None = Field(default=None, max_length=80)
    step: str | None = Field(default=None, max_length=80)
    mode: Literal["normal", "confirming", "choosing", "dictating"]
    transcript: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)
    answers: list[VoiceLoggedAnswer] = Field(default_factory=list, max_length=MAX_QUESTIONS)
    decision: Literal[
        "execute", "confirm", "dictate", "choose", "keep", "reject",
        "stop", "cancel", "unclear", "dictated", "unavailable",
    ]
    action: VoiceLoggedAction | None = None
    outcome: Literal["ok", "fail", "pending", "none"]
    latency_ms: VoiceLatency


class VoiceLogAccepted(BaseModel):
    accepted: bool = True
```

- [ ] **Step 4: Write the logger**

Create `backend/app/services/voice_log.py`:

```python
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
```

- [ ] **Step 5: Read the settings and wire the logger**

In `backend/app/core/config.py`, add `from pathlib import Path` to the imports and add below `voice_mode()`:

```python
def voice_log_settings() -> tuple[Path, bool]:
    """Where voice turns are logged, and whether transcripts and values are kept."""
    path = Path(os.getenv("VOICE_LOG_PATH", "logs/voice-turns.jsonl"))
    include_content = os.getenv("VOICE_LOG_CONTENT", "false").strip().lower() in {
        "1", "true", "yes",
    }
    return path, include_content
```

In `backend/app/core/dependencies.py`, add `voice_log_settings` to the `from app.core.config import (…)` list, add

```python
from app.services.voice_log import VoiceTurnLogger
```

below the repository imports, add below `_spatial_provider`:

```python
_voice_log_path, _voice_log_content = voice_log_settings()
_voice_turn_logger = VoiceTurnLogger(_voice_log_path, include_content=_voice_log_content)
```

and append:

```python
def get_voice_turn_logger() -> VoiceTurnLogger:
    return _voice_turn_logger
```

- [ ] **Step 6: Add the route**

In `backend/app/api/routes/voice.py`, replace the imports with:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_judgement_client, get_voice_turn_logger
from app.providers.interfaces import JudgementClient
from app.schemas.voice import (
    VoiceJudgeRequest,
    VoiceJudgeResponse,
    VoiceLogAccepted,
    VoiceTurnLog,
)
from app.services.voice import VoiceJudgementService
from app.services.voice_log import VoiceTurnLogger
```

Add below `JudgementDependency`:

```python
TurnLoggerDependency = Annotated[VoiceTurnLogger, Depends(get_voice_turn_logger)]
```

Append:

```python
@router.post(
    "/log", response_model=VoiceLogAccepted, status_code=status.HTTP_202_ACCEPTED
)
def log_voice_turn(turn: VoiceTurnLog, turn_logger: TurnLoggerDependency) -> VoiceLogAccepted:
    """Record one finished turn. Always accepted: a missed line is never the user's problem.

    Answers 202 with a body rather than 204, because the frontend's HTTP
    boundary parses every successful response as JSON.
    """
    turn_logger.record(turn)
    return VoiceLogAccepted()
```

- [ ] **Step 7: Keep logs out of Git and document the settings**

Append to `.gitignore`:

```
# Voice control turn logs (may contain names and addresses)
logs/
```

In `docker-compose.yml`, below the `APP_VOICE_MODE` line added in Task 1:

```yaml
      VOICE_LOG_PATH: ${VOICE_LOG_PATH:-logs/voice-turns.jsonl}
      VOICE_LOG_CONTENT: ${VOICE_LOG_CONTENT:-false}
```

Append to `.env.example`:

```bash

# One JSON line per voice turn. Transcripts and spoken values contain names and
# addresses, so they are written only when VOICE_LOG_CONTENT=true. Keep it false
# anywhere but a local experiment.
VOICE_LOG_PATH=logs/voice-turns.jsonl
VOICE_LOG_CONTENT=false
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_voice_log.py -v`
Expected: 12 passed.

Run: `cd backend && .venv/bin/pytest`
Expected: all pass. Then `git status --short` must not show a `backend/logs/` directory (no test writes to the default path).

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/voice.py backend/app/services/voice_log.py \
  backend/app/core/config.py backend/app/core/dependencies.py \
  backend/app/api/routes/voice.py backend/tests/test_voice_log.py \
  docker-compose.yml .env.example .gitignore
git commit -m "feat(backend): log voice turns with content redacted by default"
```

---

### Task 4: Registry, target builders and scopes

**Files:**
- Create: `frontend/src/voice/registry.js`
- Create: `frontend/src/voice/targets.js`
- Create: `frontend/src/components/voice/VoiceScope.vue`
- Test: `frontend/tests/voiceRegistry.test.js`
- Test: `frontend/tests/voiceTargets.test.js`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `registry.js`: `registerTargets(getTargets) -> unregister`, `registerContext(getContext) -> unregister`, `snapshotTargets() -> Target[]`, `snapshotContext() -> { page, step }`, `resetVoiceRegistry()`, `nestedScope(parentActive, ownActive) -> () => boolean`, `provideVoiceScope(isActive)`, `useVoiceCommands(getTargets)`, `useVoiceContext(getContext)`
  - `targets.js`: `pageTarget({ id, label, go })`, `commandTarget({ id, label, run })`, `buttonTarget({ id, label, press, aliases?, confirm?, disabled? })`, `textTarget({ id, label, current, set })`, `checkboxTarget({ id, label, current, set })`, `selectTarget({ id, label, choices: [{ label, value }], current, set })`, `addressTarget({ id, label, current, setText, suggestions, choose })`, `uniqueLabels(labels)`, `rowName(name, noun, index)`, `spokenWholeNumber(text)`, `class VoiceActionError`
  - A **Target** is `{ id, kind, label, run, current?, options?, aliases?, confirm?, disabled?, suggestions?, choose? }`, `kind` ∈ `page | command | button | select | text | checkbox | address`. For a select, `run(optionLabel)`; text and address `run(text)`; checkbox `run(boolean)`; the rest `run()`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voiceRegistry.test.js`:

```js
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

const {
  nestedScope,
  registerContext,
  registerTargets,
  resetVoiceRegistry,
  snapshotContext,
  snapshotTargets,
} = await import('../src/voice/registry.js')

afterEach(() => resetVoiceRegistry())

test('a snapshot calls every getter afresh, so labels are never stale', () => {
  let label = 'Before'
  registerTargets(() => [{ id: 'a', label }])
  assert.equal(snapshotTargets()[0].label, 'Before')
  label = 'After'
  assert.equal(snapshotTargets()[0].label, 'After')
})

test('unregistering removes only that component’s targets', () => {
  const removeFirst = registerTargets(() => [{ id: 'first' }])
  registerTargets(() => [{ id: 'second' }])
  removeFirst()
  assert.deepEqual(snapshotTargets().map((target) => target.id), ['second'])
})

test('targets keep registration order, so the layout’s globals come first', () => {
  registerTargets(() => [{ id: 'global' }])
  registerTargets(() => [{ id: 'page' }, { id: 'page-2' }])
  assert.deepEqual(snapshotTargets().map((target) => target.id), ['global', 'page', 'page-2'])
})

test('context from several components merges', () => {
  registerContext(() => ({ page: 'plan-builder' }))
  registerContext(() => ({ step: 'people' }))
  assert.deepEqual(snapshotContext(), { page: 'plan-builder', step: 'people' })
})

test('context defaults to no page and no step', () => {
  assert.deepEqual(snapshotContext(), { page: null, step: null })
})

test('a nested scope is active only when every enclosing scope is', () => {
  assert.equal(nestedScope(() => true, () => true)(), true)
  assert.equal(nestedScope(() => false, () => true)(), false)
  assert.equal(nestedScope(() => true, () => false)(), false)
})
```

Create `frontend/tests/voiceTargets.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  VoiceActionError,
  addressTarget,
  buttonTarget,
  checkboxTarget,
  rowName,
  selectTarget,
  spokenWholeNumber,
  textTarget,
  uniqueLabels,
} = await import('../src/voice/targets.js')

test('a select offers labels and stores the value behind the chosen one', () => {
  let stored = 'unset'
  const target = selectTarget({
    id: 'rel',
    label: 'Relationship to household (Minh)',
    choices: [{ label: 'Prefer not to specify', value: null }, { label: 'Parent', value: 'parent' }],
    current: 'parent',
    set: (value) => { stored = value },
  })
  assert.equal(target.kind, 'select')
  assert.deepEqual(target.options, ['Prefer not to specify', 'Parent'])
  assert.equal(target.current, 'Parent')
  target.run('Prefer not to specify')
  assert.equal(stored, null)
})

test('repeated option labels are numbered and still map to their own values', () => {
  let stored
  const target = selectTarget({
    id: 'who',
    label: 'Primary person',
    choices: [{ label: 'Unnamed member', value: 'm_1' }, { label: 'Unnamed member', value: 'm_2' }],
    current: null,
    set: (value) => { stored = value },
  })
  assert.deepEqual(target.options, ['Unnamed member', 'Unnamed member (2)'])
  assert.equal(target.current, null)
  target.run('Unnamed member (2)')
  assert.equal(stored, 'm_2')
})

test('uniqueLabels never produces a duplicate, even against a numbered label', () => {
  assert.deepEqual(uniqueLabels(['A', 'A (2)', 'A']), ['A', 'A (2)', 'A (3)'])
})

test('text, checkbox and button targets carry their kind and defaults', () => {
  const text = textTarget({ id: 't', label: 'Name (member 2)', current: null, set: () => {} })
  assert.equal(text.kind, 'text')
  assert.equal(text.current, '')
  const box = checkboxTarget({ id: 'c', label: 'Has limited mobility (Minh)', current: undefined, set: () => {} })
  assert.equal(box.kind, 'checkbox')
  assert.equal(box.current, false)
  const button = buttonTarget({ id: 'b', label: 'Save plan', press: () => {} })
  assert.deepEqual(
    [button.kind, button.aliases, button.confirm, button.disabled],
    ['button', [], false, false],
  )
})

test('an address target exposes its text, suggestions and chooser', () => {
  const chosen = []
  const target = addressTarget({
    id: 'address-1',
    label: 'Primary destination address',
    current: '12 Smith St',
    setText: () => {},
    suggestions: () => ['12 Smith St, Ballarat VIC 3350'],
    choose: (index) => chosen.push(index),
  })
  assert.equal(target.kind, 'address')
  assert.deepEqual(target.suggestions(), ['12 Smith St, Ballarat VIC 3350'])
  target.choose(0)
  assert.deepEqual(chosen, [0])
})

test('rows are named by the person, or by position until they have a name', () => {
  assert.equal(rowName('Minh', 'member', 0), 'Minh')
  assert.equal(rowName('  ', 'member', 1), 'member 2')
  assert.equal(rowName(null, 'transport', 0), 'transport 1')
})

test('whole numbers can be said as words or digits', () => {
  assert.equal(spokenWholeNumber('two'), 2)
  assert.equal(spokenWholeNumber(' 3 '), 3)
  assert.equal(spokenWholeNumber('Twelve'), 12)
})

test('anything that is not a whole number of at least one is refused with a message', () => {
  for (const heard of ['a lot', '0', '2.5', '']) {
    assert.throws(() => spokenWholeNumber(heard), (error) =>
      error instanceof VoiceActionError && /whole number/.test(error.message))
  }
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceRegistry.test.js tests/voiceTargets.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/voice/registry.js`.

- [ ] **Step 3: Write the registry**

Create `frontend/src/voice/registry.js`:

```js
import { inject, onBeforeUnmount, provide } from 'vue'

// Components register getters, not targets. The voice store calls every getter
// once when an utterance is final, so a snapshot is always current and nothing
// has to stay reactive in between.
const targetGetters = new Map()
const contextGetters = new Map()

export const VOICE_SCOPE = Symbol('voiceScope')

export function registerTargets(getTargets) {
  const key = Symbol('targets')
  targetGetters.set(key, getTargets)
  return () => targetGetters.delete(key)
}

export function registerContext(getContext) {
  const key = Symbol('context')
  contextGetters.set(key, getContext)
  return () => contextGetters.delete(key)
}

export function snapshotTargets() {
  return [...targetGetters.values()].flatMap((getTargets) => getTargets() ?? [])
}

export function snapshotContext() {
  return Object.assign(
    { page: null, step: null },
    ...[...contextGetters.values()].map((getContext) => getContext() ?? {}),
  )
}

export function resetVoiceRegistry() {
  targetGetters.clear()
  contextGetters.clear()
}

// A section is active only when every section around it is.
export function nestedScope(parentActive, ownActive) {
  return () => parentActive() && ownActive()
}

export function provideVoiceScope(isActive) {
  const parentActive = inject(VOICE_SCOPE, () => true)
  provide(VOICE_SCOPE, nestedScope(parentActive, isActive))
}

// Hidden sections (the plan builder keeps all five mounted) offer nothing, so a
// command can never reach a field the user cannot see.
export function useVoiceCommands(getTargets) {
  const isActive = inject(VOICE_SCOPE, () => true)
  const unregister = registerTargets(() => (isActive() ? getTargets() : []))
  onBeforeUnmount(unregister)
}

export function useVoiceContext(getContext) {
  const unregister = registerContext(getContext)
  onBeforeUnmount(unregister)
}
```

- [ ] **Step 4: Write the target builders**

Create `frontend/src/voice/targets.js`:

```js
// Builders for everything a page can offer to voice control. Every target has a
// stable id (never a person's name), a kind, a spoken label, and `run`, which
// performs it through the same code the mouse and keyboard use.

// A problem the user can fix by saying it differently. Its message is shown as-is;
// any other error from `run` is reported generically.
export class VoiceActionError extends Error {}

export function pageTarget({ id, label, go }) {
  return { id, kind: 'page', label, run: go }
}

export function commandTarget({ id, label, run }) {
  return { id, kind: 'command', label, run }
}

export function buttonTarget({ id, label, press, aliases = [], confirm = false, disabled = false }) {
  return { id, kind: 'button', label, aliases, confirm, disabled, run: press }
}

export function textTarget({ id, label, current, set }) {
  return { id, kind: 'text', label, current: current ?? '', run: set }
}

export function checkboxTarget({ id, label, current, set }) {
  return { id, kind: 'checkbox', label, current: Boolean(current), run: set }
}

// `choices` are { label, value } pairs taken from the constants the template
// renders. Repeated labels (two unnamed members) are numbered so each spoken
// option still maps to exactly one value.
export function selectTarget({ id, label, choices, current, set }) {
  const options = uniqueLabels(choices.map((choice) => choice.label))
  const valueByOption = new Map(options.map((option, index) => [option, choices[index].value]))
  const currentIndex = choices.findIndex((choice) => choice.value === current)
  return {
    id,
    kind: 'select',
    label,
    options,
    current: currentIndex === -1 ? null : options[currentIndex],
    run: (option) => set(valueByOption.get(option)),
  }
}

export function addressTarget({ id, label, current, setText, suggestions, choose }) {
  return { id, kind: 'address', label, current: current ?? '', run: setText, suggestions, choose }
}

export function uniqueLabels(labels) {
  const used = new Set()
  return labels.map((label) => {
    let candidate = label
    for (let count = 2; used.has(candidate); count += 1) candidate = `${label} (${count})`
    used.add(candidate)
    return candidate
  })
}

// "member 2" until the row has a name, because that is how the row reads.
export function rowName(name, noun, index) {
  return name?.trim() || `${noun} ${index + 1}`
}

const NUMBER_WORDS = {
  a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
  seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
}

export function spokenWholeNumber(text) {
  const word = String(text).trim().toLowerCase()
  const value = NUMBER_WORDS[word] ?? (word === '' ? Number.NaN : Number(word))
  if (!Number.isInteger(value) || value < 1) {
    throw new VoiceActionError('Say the quantity as a whole number, such as 2.')
  }
  return value
}
```

- [ ] **Step 5: Write the scope component**

Create `frontend/src/components/voice/VoiceScope.vue`:

```vue
<script setup>
import { provideVoiceScope } from '../../voice/registry.js'

// Wraps a section that may be hidden while mounted. Voice targets registered
// anywhere inside are offered only while `active` is true.
const props = defineProps({ active: { type: Boolean, required: true } })
provideVoiceScope(() => props.active)
</script>

<template>
  <slot />
</template>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceRegistry.test.js tests/voiceTargets.test.js`
Expected: 14 tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/voice/registry.js frontend/src/voice/targets.js \
  frontend/src/components/voice/VoiceScope.vue \
  frontend/tests/voiceRegistry.test.js frontend/tests/voiceTargets.test.js
git commit -m "feat(frontend): add the voice target registry and builders"
```

---

### Task 5: Question batches

**Files:**
- Create: `frontend/src/voice/questions.js`
- Test: `frontend/tests/voiceQuestions.test.js`

**Interfaces:**
- Consumes: `uniqueLabels` and the target builders from Task 4
- Produces:
  - Constants `NONE_OF_THESE = 'none of these'`, `NO_SPAN = '(none)'`, `NO_SUGGESTION = 'none'`, `MAX_COMMANDS = 99`
  - `commandPhrase(target) -> string`
  - `buildCatalogue(targets) -> [{ phrase, target }]` (at most `MAX_COMMANDS`)
  - `spanCandidates(transcript) -> string[]` (ends with `NO_SPAN`, at most 100)
  - `suggestionOptions(suggestions) -> string[]` (`'1 first: …'`, at most 9, then `NO_SUGGESTION`)
  - `buildBatch({ transcript, targets, context, mode = 'normal', choosing = [] }) -> { state, questions, catalogue }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voiceQuestions.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  MAX_COMMANDS,
  NONE_OF_THESE,
  NO_SPAN,
  NO_SUGGESTION,
  buildBatch,
  buildCatalogue,
  commandPhrase,
  spanCandidates,
  suggestionOptions,
} = await import('../src/voice/questions.js')
const {
  addressTarget,
  buttonTarget,
  checkboxTarget,
  commandTarget,
  pageTarget,
  selectTarget,
  textTarget,
} = await import('../src/voice/targets.js')

const noop = () => {}
const transportSelect = (id, label) => selectTarget({
  id,
  label,
  choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
  current: null,
  set: noop,
})

test('each kind of target reads as a command phrase', () => {
  assert.equal(commandPhrase(pageTarget({ id: 'p', label: 'Fire Map', go: noop })), 'go to Fire Map')
  assert.equal(commandPhrase(commandTarget({ id: 'c', label: 'scroll down', run: noop })), 'scroll down')
  assert.equal(
    commandPhrase(buttonTarget({ id: 'b', label: 'Continue', aliases: ['next step'], press: noop })),
    'press Continue, or say next step',
  )
  assert.equal(commandPhrase(buttonTarget({ id: 'b', label: 'Save plan', press: noop })), 'press Save plan')
  assert.equal(commandPhrase(transportSelect('s', 'Primary transport')), 'set Primary transport')
  assert.equal(
    commandPhrase(textTarget({ id: 't', label: 'Name (member 2)', current: '', set: noop })),
    'fill in Name (member 2)',
  )
  assert.equal(
    commandPhrase(checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: false, set: noop })),
    'tick or untick Has limited mobility (Minh)',
  )
  assert.equal(
    commandPhrase(addressTarget({ id: 'a', label: 'Primary destination address', current: '', setText: noop, suggestions: () => [], choose: noop })),
    'enter the address for Primary destination address',
  )
})

test('two targets with the same phrase get distinct phrases', () => {
  const catalogue = buildCatalogue([
    buttonTarget({ id: 'r1', label: 'Retry', press: noop }),
    buttonTarget({ id: 'r2', label: 'Retry', press: noop }),
  ])
  assert.deepEqual(catalogue.map((entry) => entry.phrase), ['press Retry', 'press Retry (2)'])
  assert.deepEqual(catalogue.map((entry) => entry.target.id), ['r1', 'r2'])
})

test('a page offering more than the judge accepts keeps the earliest targets', () => {
  const targets = Array.from({ length: 150 }, (_, index) =>
    buttonTarget({ id: `b${index}`, label: `Button ${index}`, press: noop }))
  const catalogue = buildCatalogue(targets)
  assert.equal(MAX_COMMANDS, 99)
  assert.equal(catalogue.length, 99)
  assert.equal(catalogue[0].target.id, 'b0')

  const { questions, state } = buildBatch({ transcript: 'hello', targets, context: { page: 'plan-builder' } })
  assert.equal(questions[0].options.length, 100)
  assert.equal(state.targets.length, 99)
})

test('a normal batch asks for the command, every select, a span, checked and stop', () => {
  const targets = [
    pageTarget({ id: 'page-overview', label: 'Overview', go: noop }),
    transportSelect('primary-transport', 'Primary transport'),
    transportSelect('backup-0-transport', 'Backup transport (backup 1)'),
    textTarget({ id: 'meeting-point', label: 'Meeting point', current: '', set: noop }),
  ]
  const { state, questions, catalogue } = buildBatch({
    transcript: 'primary transport is a van',
    targets,
    context: { page: 'plan-builder', step: 'destinations' },
  })

  assert.deepEqual(questions.map((question) => question.id), [
    'command', 'option:primary-transport', 'option:backup-0-transport', 'span', 'checked', 'stop',
  ])
  assert.equal(questions[0].type, 'pick_one')
  assert.equal(questions[0].options.at(-1), NONE_OF_THESE)
  assert.deepEqual(questions[1].options, ['Not set', 'Van'])
  assert.deepEqual(questions[4], { id: 'checked', type: 'yes_no', options: [] })
  assert.equal(catalogue.length, 4)
  assert.deepEqual(
    [state.page, state.step, state.mode, state.transcript],
    ['plan-builder', 'destinations', 'normal', 'primary transport is a van'],
  )
})

test('state describes targets as plain data, without their handlers', () => {
  const { state } = buildBatch({
    transcript: 'hello',
    targets: [
      checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: true, set: noop }),
      textTarget({ id: 't', label: 'Name (member 2)', current: '', set: noop }),
    ],
    context: { page: 'plan-builder', step: 'people' },
  })
  assert.deepEqual(state.targets, [
    { id: 'x', kind: 'checkbox', label: 'Has limited mobility (Minh)', current: 'true' },
    { id: 't', kind: 'text', label: 'Name (member 2)' },
  ])
})

test('spans cover runs of up to eight words, cleaned of punctuation, ending in (none)', () => {
  const spans = spanCandidates('Name is Minh.')
  assert.ok(spans.includes('Minh'))
  assert.ok(spans.includes('Name is Minh'))
  assert.ok(!spans.some((span) => span.endsWith('.')))
  assert.equal(spans.at(-1), NO_SPAN)
  assert.equal(new Set(spans).size, spans.length)
})

test('long transcripts keep the spans nearest the end, where values usually are', () => {
  // Seventeen different words give 108 distinct spans, more than fit.
  const spans = spanCandidates(
    'please could you now set the name for my second household member over here to Lan Nguyen',
  )
  assert.equal(spans.length, 100)
  assert.ok(spans.includes('Lan Nguyen'))
})

test('a confirming batch asks only yes/no questions', () => {
  const { questions, catalogue } = buildBatch({
    transcript: 'yes', targets: [], context: {}, mode: 'confirming',
  })
  assert.deepEqual(questions, [
    { id: 'confirm', type: 'yes_no', options: [] },
    { id: 'stop', type: 'yes_no', options: [] },
  ])
  assert.deepEqual(catalogue, [])
})

test('a choosing batch numbers the suggestions and offers none', () => {
  const { questions } = buildBatch({
    transcript: 'the first one',
    targets: [],
    context: {},
    mode: 'choosing',
    choosing: ['12 Smith St, Ballarat VIC 3350', '12 Smith Rd, Sale VIC 3850'],
  })
  assert.deepEqual(questions[0], {
    id: 'suggestion',
    type: 'pick_one',
    options: ['1 first: 12 Smith St, Ballarat VIC 3350', '2 second: 12 Smith Rd, Sale VIC 3850', NO_SUGGESTION],
  })
  assert.equal(questions[1].id, 'stop')
})

test('at most nine suggestions are offered', () => {
  const options = suggestionOptions(Array.from({ length: 12 }, (_, index) => `Address ${index}`))
  assert.equal(options.length, 10)
  assert.equal(options[8], '9 ninth: Address 8')
  assert.equal(options[9], NO_SUGGESTION)
})

test('a page is always named, even before the layout registers', () => {
  const { state } = buildBatch({ transcript: 'hello', targets: [], context: { page: null, step: null } })
  assert.equal(state.page, 'unknown')
  assert.equal(state.step, null)
})

test('current values are cut to what the backend accepts', () => {
  const { state } = buildBatch({
    transcript: 'hello',
    targets: [textTarget({ id: 't', label: 'Notes', current: 'x'.repeat(600), set: noop })],
    context: {},
  })
  assert.equal(state.targets[0].current.length, 500)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceQuestions.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/voice/questions.js`.

- [ ] **Step 3: Write the module**

Create `frontend/src/voice/questions.js`:

```js
import { uniqueLabels } from './targets.js'

export const NONE_OF_THESE = 'none of these'
export const NO_SPAN = '(none)'
export const NO_SUGGESTION = 'none'
// The backend accepts 100 options per question; one is NONE_OF_THESE.
export const MAX_COMMANDS = 99

const MAX_QUESTIONS = 100
const MAX_OPTIONS = 100
const MAX_SPAN_WORDS = 8
const MAX_CURRENT = 500
const MAX_SUGGESTIONS = 9
const ORDINALS = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth']

export function commandPhrase(target) {
  switch (target.kind) {
    case 'page':
      return `go to ${target.label}`
    case 'button':
      return target.aliases?.length
        ? `press ${target.label}, or say ${target.aliases.join(', or say ')}`
        : `press ${target.label}`
    case 'select':
      return `set ${target.label}`
    case 'text':
      return `fill in ${target.label}`
    case 'checkbox':
      return `tick or untick ${target.label}`
    case 'address':
      return `enter the address for ${target.label}`
    default:
      return target.label
  }
}

// One phrase per target; the phrases are the options the judge chooses among,
// so each must name exactly one target. Registration order decides what is kept
// when a page offers too much: the layout's pages and scroll commands come first.
export function buildCatalogue(targets) {
  const kept = targets.slice(0, MAX_COMMANDS)
  const phrases = uniqueLabels(kept.map(commandPhrase))
  return kept.map((target, index) => ({ phrase: phrases[index], target }))
}

function cleanWord(word) {
  return word.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
}

// Every run of up to eight words, latest-starting first: values ("to Lan
// Nguyen") usually end the sentence, so those survive when the list is capped.
export function spanCandidates(transcript) {
  const words = transcript.split(/\s+/).map(cleanWord).filter(Boolean)
  const spans = []
  const seen = new Set()
  for (let start = words.length - 1; start >= 0; start -= 1) {
    const last = Math.min(words.length, start + MAX_SPAN_WORDS)
    for (let end = start + 1; end <= last; end += 1) {
      const span = words.slice(start, end).join(' ')
      if (!seen.has(span)) {
        seen.add(span)
        spans.push(span)
      }
    }
  }
  return [...spans.slice(0, MAX_OPTIONS - 1), NO_SPAN]
}

export function suggestionOptions(suggestions) {
  const numbered = suggestions
    .slice(0, MAX_SUGGESTIONS)
    .map((text, index) => `${index + 1} ${ORDINALS[index]}: ${text}`)
  return [...numbered, NO_SUGGESTION]
}

function describeTarget(target) {
  const summary = { id: target.id, kind: target.kind, label: target.label }
  if (target.current !== undefined && target.current !== null && target.current !== '') {
    summary.current = String(target.current).slice(0, MAX_CURRENT)
  }
  return summary
}

const yesNo = (id) => ({ id, type: 'yes_no', options: [] })

export function buildBatch({ transcript, targets, context, mode = 'normal', choosing = [] }) {
  const catalogue = mode === 'normal' ? buildCatalogue(targets) : []
  const state = {
    page: context?.page ?? 'unknown',
    step: context?.step ?? null,
    mode,
    transcript,
    targets: targets.slice(0, MAX_COMMANDS).map(describeTarget),
  }

  if (mode === 'confirming') {
    return { state, questions: [yesNo('confirm'), yesNo('stop')], catalogue }
  }
  if (mode === 'choosing') {
    const suggestion = { id: 'suggestion', type: 'pick_one', options: suggestionOptions(choosing) }
    return { state, questions: [suggestion, yesNo('stop')], catalogue }
  }

  // Every select's value is asked up front, so any command costs exactly one call.
  const optionQuestions = catalogue
    .filter((entry) => entry.target.kind === 'select')
    .slice(0, MAX_QUESTIONS - 4)
    .map((entry) => ({ id: `option:${entry.target.id}`, type: 'pick_one', options: entry.target.options }))

  const questions = [
    { id: 'command', type: 'pick_one', options: [...catalogue.map((entry) => entry.phrase), NONE_OF_THESE] },
    ...optionQuestions,
    { id: 'span', type: 'pick_one', options: spanCandidates(transcript) },
    yesNo('checked'),
    yesNo('stop'),
  ]
  return { state, questions, catalogue }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceQuestions.test.js`
Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/voice/questions.js frontend/tests/voiceQuestions.test.js
git commit -m "feat(frontend): build voice question batches from the page's targets"
```

---

### Task 6: Decision policy

**Files:**
- Create: `frontend/src/voice/policy.js`
- Test: `frontend/tests/voicePolicy.test.js`

**Interfaces:**
- Consumes: `NONE_OF_THESE`, `NO_SPAN`, `NO_SUGGESTION`, `buildCatalogue` from Task 5; target builders from Task 4
- Produces:
  - `ACT_AT = 0.85`, `ASK_AT = 0.5`
  - An **Action** is `{ kind, target, value }` (`value` is the option label, text, boolean, or `null`)
  - `decideCommand(answers, catalogue)` → `{ type: 'stop' | 'reject' }` | `{ type: 'execute' | 'confirm', action }` | `{ type: 'dictate', target }`
  - `decideConfirmation(answers)` → `{ type: 'stop' | 'execute' | 'cancel' | 'unclear' }`
  - `decideSuggestion(answers)` → `{ type: 'stop' | 'keep' | 'unclear' }` | `{ type: 'choose', index }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voicePolicy.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { ACT_AT, ASK_AT, decideCommand, decideConfirmation, decideSuggestion } =
  await import('../src/voice/policy.js')
const { NONE_OF_THESE, NO_SPAN, NO_SUGGESTION, buildCatalogue } = await import('../src/voice/questions.js')
const { addressTarget, buttonTarget, checkboxTarget, pageTarget, selectTarget, textTarget } =
  await import('../src/voice/targets.js')

const noop = () => {}
const catalogue = buildCatalogue([
  pageTarget({ id: 'page-map', label: 'Fire Map', go: noop }),
  selectTarget({
    id: 'primary-transport',
    label: 'Primary transport',
    choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
    current: null,
    set: noop,
  }),
  textTarget({ id: 'm2-name', label: 'Name (member 2)', current: '', set: noop }),
  textTarget({ id: 'm1-name', label: 'Name (Minh)', current: 'Minh', set: noop }),
  checkboxTarget({ id: 'm1-mobility', label: 'Has limited mobility (Minh)', current: false, set: noop }),
  addressTarget({
    id: 'address-1', label: 'Primary destination address', current: '',
    setText: noop, suggestions: () => [], choose: noop,
  }),
  buttonTarget({ id: 'm1-remove', label: 'Remove member Minh', confirm: true, press: noop }),
])

const a = (id, answer, probability) => ({ id, answer, probability })
const NO_STOP = a('stop', 'no', 0.95)
const decide = (...answers) => decideCommand([...answers, NO_STOP], catalogue)

test('the thresholds are exactly 0.85 to act and 0.5 to ask', () => {
  assert.equal(ACT_AT, 0.85)
  assert.equal(ASK_AT, 0.5)
})

test('a command at exactly 0.85 is carried out', () => {
  const decision = decide(a('command', 'go to Fire Map', 0.85))
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.kind, 'page')
  assert.equal(decision.action.target.id, 'page-map')
})

test('just under 0.85 asks first, and exactly 0.5 still asks', () => {
  assert.equal(decide(a('command', 'go to Fire Map', 0.84)).type, 'confirm')
  assert.equal(decide(a('command', 'go to Fire Map', 0.5)).type, 'confirm')
})

test('below 0.5 nothing happens', () => {
  assert.equal(decide(a('command', 'go to Fire Map', 0.49)).type, 'reject')
})

test('confidence is the lowest answer the decision uses', () => {
  const decision = decide(
    a('command', 'set Primary transport', 0.95),
    a('option:primary-transport', 'Van', 0.6),
  )
  assert.equal(decision.type, 'confirm')
  assert.deepEqual(
    [decision.action.kind, decision.action.target.id, decision.action.value],
    ['select', 'primary-transport', 'Van'],
  )
})

test('a confident select is carried out with the chosen option', () => {
  const decision = decide(
    a('command', 'set Primary transport', 0.95),
    a('option:primary-transport', 'Van', 0.97),
  )
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.value, 'Van')
})

test('a target marked confirm asks even at 0.99', () => {
  const decision = decide(a('command', 'press Remove member Minh', 0.99))
  assert.equal(decision.type, 'confirm')
  assert.equal(decision.action.target.id, 'm1-remove')
})

test('a confident span fills an empty text field', () => {
  const decision = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', 'Lan', 0.9))
  assert.equal(decision.type, 'execute')
  assert.deepEqual([decision.action.kind, decision.action.value], ['text', 'Lan'])
})

test('an unsure or missing value turns into dictation', () => {
  const unsure = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', 'Lan', 0.7))
  assert.deepEqual([unsure.type, unsure.target.id], ['dictate', 'm2-name'])
  const missing = decide(a('command', 'fill in Name (member 2)', 0.95), a('span', NO_SPAN, 0.95))
  assert.equal(missing.type, 'dictate')
})

test('replacing something already typed always asks first', () => {
  const decision = decide(a('command', 'fill in Name (Minh)', 0.95), a('span', 'Lan', 0.95))
  assert.equal(decision.type, 'confirm')
  assert.equal(decision.action.value, 'Lan')
})

test('saying the value that is already there is not an overwrite', () => {
  const decision = decide(a('command', 'fill in Name (Minh)', 0.95), a('span', 'Minh', 0.95))
  assert.equal(decision.type, 'execute')
})

test('an address is always dictated, never taken from the sentence', () => {
  const decision = decide(
    a('command', 'enter the address for Primary destination address', 0.99),
    a('span', '12 Smith Street', 0.99),
  )
  assert.deepEqual([decision.type, decision.target.id], ['dictate', 'address-1'])
})

test('a checkbox is set from the checked answer', () => {
  const decision = decide(
    a('command', 'tick or untick Has limited mobility (Minh)', 0.95),
    a('checked', 'no', 0.9),
  )
  assert.equal(decision.type, 'execute')
  assert.equal(decision.action.value, false)
})

test('none of these, a missing command, an unknown phrase or a missing value is rejected', () => {
  assert.equal(decide(a('command', NONE_OF_THESE, 0.99)).type, 'reject')
  assert.equal(decideCommand([NO_STOP], catalogue).type, 'reject')
  assert.equal(decide(a('command', 'press Launch', 0.99)).type, 'reject')
  assert.equal(decide(a('command', 'set Primary transport', 0.99)).type, 'reject')
})

test('stop wins over a confident command, but only at 0.5 or more', () => {
  const confident = a('command', 'go to Fire Map', 0.99)
  assert.equal(decideCommand([confident, a('stop', 'yes', 0.9)], catalogue).type, 'stop')
  assert.equal(decideCommand([confident, a('stop', 'yes', 0.4)], catalogue).type, 'execute')
})

test('a confirmation needs a confident yes; a no only needs to be likely', () => {
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.9), NO_STOP]).type, 'execute')
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.8), NO_STOP]).type, 'unclear')
  assert.equal(decideConfirmation([a('confirm', 'no', 0.6), NO_STOP]).type, 'cancel')
  assert.equal(decideConfirmation([a('confirm', 'no', 0.4), NO_STOP]).type, 'unclear')
  assert.equal(decideConfirmation([a('confirm', 'yes', 0.9), a('stop', 'yes', 0.9)]).type, 'stop')
})

test('a suggestion is chosen by its number only when confident', () => {
  assert.deepEqual(
    decideSuggestion([a('suggestion', '2 second: 12 Smith Rd, Sale VIC 3850', 0.9), NO_STOP]),
    { type: 'choose', index: 1 },
  )
  assert.equal(decideSuggestion([a('suggestion', NO_SUGGESTION, 0.9), NO_STOP]).type, 'keep')
  assert.equal(decideSuggestion([a('suggestion', '1 first: x', 0.7), NO_STOP]).type, 'unclear')
  assert.equal(decideSuggestion([a('suggestion', '1 first: x', 0.9), a('stop', 'yes', 0.9)]).type, 'stop')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voicePolicy.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/voice/policy.js`.

- [ ] **Step 3: Write the module**

Create `frontend/src/voice/policy.js`:

```js
import { NONE_OF_THESE, NO_SPAN, NO_SUGGESTION } from './questions.js'

// Starting values. The turn log exists to replace them with measured ones.
export const ACT_AT = 0.85
export const ASK_AT = 0.5

function byId(answers) {
  return new Map(answers.map((answer) => [answer.id, answer]))
}

function stopRequested(answers) {
  const stop = answers.get('stop')
  return stop?.answer === 'yes' && stop.probability >= ASK_AT
}

// Replacing something the user already typed is never done on a guess about
// which row they meant: rows look alike ("Name (Minh)", "Name (member 2)").
function overwrites(target, value) {
  return Boolean(target.current) && target.current !== value
}

function settle(action, confidence, mustConfirm) {
  if (confidence < ASK_AT) return { type: 'reject' }
  if (mustConfirm || confidence < ACT_AT) return { type: 'confirm', action }
  return { type: 'execute', action }
}

export function decideCommand(answerList, catalogue) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }

  const command = answers.get('command')
  if (!command || command.answer === NONE_OF_THESE) return { type: 'reject' }
  const entry = catalogue.find((item) => item.phrase === command.answer)
  if (!entry) return { type: 'reject' }
  const { target } = entry

  // Addresses are long and one misheard word is a different street: always
  // dictated, never lifted out of a sentence.
  if (target.kind === 'address') {
    return command.probability >= ASK_AT ? { type: 'dictate', target } : { type: 'reject' }
  }

  if (target.kind === 'text') {
    const span = answers.get('span')
    const usable = span && span.answer !== NO_SPAN && span.probability >= ACT_AT
    if (!usable) {
      return command.probability >= ASK_AT ? { type: 'dictate', target } : { type: 'reject' }
    }
    return settle(
      { kind: 'text', target, value: span.answer },
      Math.min(command.probability, span.probability),
      overwrites(target, span.answer),
    )
  }

  if (target.kind === 'select') {
    const option = answers.get(`option:${target.id}`)
    if (!option) return { type: 'reject' }
    return settle(
      { kind: 'select', target, value: option.answer },
      Math.min(command.probability, option.probability),
      false,
    )
  }

  if (target.kind === 'checkbox') {
    const checked = answers.get('checked')
    if (!checked) return { type: 'reject' }
    return settle(
      { kind: 'checkbox', target, value: checked.answer === 'yes' },
      Math.min(command.probability, checked.probability),
      false,
    )
  }

  return settle({ kind: target.kind, target, value: null }, command.probability, target.confirm === true)
}

export function decideConfirmation(answerList) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }
  const confirm = answers.get('confirm')
  if (confirm?.answer === 'yes' && confirm.probability >= ACT_AT) return { type: 'execute' }
  if (confirm?.answer === 'no' && confirm.probability >= ASK_AT) return { type: 'cancel' }
  return { type: 'unclear' }
}

export function decideSuggestion(answerList) {
  const answers = byId(answerList)
  if (stopRequested(answers)) return { type: 'stop' }
  const suggestion = answers.get('suggestion')
  if (!suggestion || suggestion.probability < ACT_AT) return { type: 'unclear' }
  if (suggestion.answer === NO_SUGGESTION) return { type: 'keep' }
  const index = Number.parseInt(suggestion.answer, 10) - 1
  return Number.isInteger(index) && index >= 0 ? { type: 'choose', index } : { type: 'unclear' }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voicePolicy.test.js`
Expected: 17 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/voice/policy.js frontend/tests/voicePolicy.test.js
git commit -m "feat(frontend): decide voice actions from judged probabilities"
```

---

### Task 7: Executor

**Files:**
- Create: `frontend/src/voice/executor.js`
- Test: `frontend/tests/voiceExecutor.test.js`

**Interfaces:**
- Consumes: Action shape from Task 6; `VoiceActionError` and builders from Task 4
- Produces:
  - `describeAction(action) -> string` (e.g. `'Set Primary transport to Van'`)
  - `executeAction(action, liveTargets) -> Promise<{ ok: boolean, message: string }>` — acts on the live target with `action.target.id`, never on the snapshot copy

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voiceExecutor.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { describeAction, executeAction } = await import('../src/voice/executor.js')
const {
  VoiceActionError,
  addressTarget,
  buttonTarget,
  checkboxTarget,
  commandTarget,
  pageTarget,
  selectTarget,
  textTarget,
} = await import('../src/voice/targets.js')

const noop = () => {}
const transport = (set = noop) => selectTarget({
  id: 'primary-transport',
  label: 'Primary transport',
  choices: [{ label: 'Not set', value: null }, { label: 'Van', value: 't_1' }],
  current: null,
  set,
})

test('the live target runs with the chosen value', async () => {
  let stored
  const target = transport((value) => { stored = value })
  const result = await executeAction({ kind: 'select', target, value: 'Van' }, [target])
  assert.deepEqual(result, { ok: true, message: '✓ Set Primary transport to Van' })
  assert.equal(stored, 't_1')
})

test('a row renamed since it was heard is still acted on through its id', async () => {
  const heard = textTarget({ id: 'm2-name', label: 'Name (member 2)', current: '', set: noop })
  let written
  const live = textTarget({ id: 'm2-name', label: 'Name (Lan)', current: 'Lan', set: (value) => { written = value } })
  const result = await executeAction({ kind: 'text', target: heard, value: 'Lan Nguyen' }, [live])
  assert.equal(written, 'Lan Nguyen')
  assert.equal(result.message, '✓ Fill in Name (Lan) with “Lan Nguyen”')
})

test('a target no longer on the page is refused', async () => {
  const target = transport()
  const result = await executeAction({ kind: 'select', target, value: 'Van' }, [])
  assert.deepEqual(result, { ok: false, message: 'That’s no longer on this page.' })
})

test('a disabled button is refused without being pressed', async () => {
  let pressed = 0
  const target = buttonTarget({ id: 'save', label: 'Save plan', disabled: true, press: () => { pressed += 1 } })
  const result = await executeAction({ kind: 'button', target, value: null }, [target])
  assert.deepEqual(result, { ok: false, message: 'That isn’t available right now.' })
  assert.equal(pressed, 0)
})

test('an option the select does not offer is refused', async () => {
  let stored = 'untouched'
  const target = transport((value) => { stored = value })
  const result = await executeAction({ kind: 'select', target, value: 'Truck' }, [target])
  assert.deepEqual(result, { ok: false, message: 'That option isn’t available.' })
  assert.equal(stored, 'untouched')
})

test('a VoiceActionError reaches the user; any other error does not', async () => {
  const fixable = textTarget({ id: 'q', label: 'Quantity (Coco)', current: '', set: () => {
    throw new VoiceActionError('Say the quantity as a whole number, such as 2.')
  } })
  assert.deepEqual(
    await executeAction({ kind: 'text', target: fixable, value: 'lots' }, [fixable]),
    { ok: false, message: 'Say the quantity as a whole number, such as 2.' },
  )
  const broken = buttonTarget({ id: 'b', label: 'Retry', press: () => { throw new Error('TypeError at line 4') } })
  assert.deepEqual(
    await executeAction({ kind: 'button', target: broken, value: null }, [broken]),
    { ok: false, message: 'That could not be done.' },
  )
})

test('an asynchronous run is finished before success is reported', async () => {
  let arrived = false
  const target = pageTarget({ id: 'page-map', label: 'Fire Map', go: async () => {
    await new Promise((resolve) => setTimeout(resolve, 5))
    arrived = true
  } })
  const result = await executeAction({ kind: 'page', target, value: null }, [target])
  assert.equal(arrived, true)
  assert.equal(result.ok, true)
})

test('every kind of action is described in plain words', () => {
  const box = checkboxTarget({ id: 'x', label: 'Has limited mobility (Minh)', current: false, set: noop })
  const address = addressTarget({ id: 'a', label: 'Primary destination address', current: '', setText: noop, suggestions: () => [], choose: noop })
  assert.equal(describeAction({ kind: 'checkbox', target: box, value: true }), 'Tick Has limited mobility (Minh)')
  assert.equal(describeAction({ kind: 'checkbox', target: box, value: false }), 'Untick Has limited mobility (Minh)')
  assert.equal(
    describeAction({ kind: 'button', target: buttonTarget({ id: 'b', label: 'Remove member Minh', press: noop }), value: null }),
    'Press Remove member Minh',
  )
  assert.equal(describeAction({ kind: 'page', target: pageTarget({ id: 'p', label: 'Overview', go: noop }), value: null }), 'Go to Overview')
  assert.equal(describeAction({ kind: 'command', target: commandTarget({ id: 'c', label: 'scroll down', run: noop }), value: null }), 'Scroll down')
  assert.equal(describeAction({ kind: 'address', target: address, value: '12 Smith St' }), 'Enter “12 Smith St” for Primary destination address')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceExecutor.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/voice/executor.js`.

- [ ] **Step 3: Write the module**

Create `frontend/src/voice/executor.js`:

```js
import { VoiceActionError } from './targets.js'

export function describeAction({ kind, target, value }) {
  switch (kind) {
    case 'select':
      return `Set ${target.label} to ${value}`
    case 'text':
      return `Fill in ${target.label} with “${value}”`
    case 'checkbox':
      return `${value ? 'Tick' : 'Untick'} ${target.label}`
    case 'button':
      return `Press ${target.label}`
    case 'page':
      return `Go to ${target.label}`
    case 'address':
      return `Enter “${value}” for ${target.label}`
    default:
      return target.label.charAt(0).toUpperCase() + target.label.slice(1)
  }
}

// Acts only on a target that is on the page right now, looked up by id: the user
// may have moved on, or renamed the row, while the judge was answering.
export async function executeAction(action, liveTargets) {
  const target = liveTargets.find((item) => item.id === action.target.id)
  if (!target) return { ok: false, message: 'That’s no longer on this page.' }
  if (target.disabled) return { ok: false, message: 'That isn’t available right now.' }
  if (target.kind === 'select' && !target.options.includes(action.value)) {
    return { ok: false, message: 'That option isn’t available.' }
  }
  try {
    await target.run(action.value)
  } catch (error) {
    return {
      ok: false,
      message: error instanceof VoiceActionError ? error.message : 'That could not be done.',
    }
  }
  return { ok: true, message: `✓ ${describeAction({ ...action, target })}` }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceExecutor.test.js`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/voice/executor.js frontend/tests/voiceExecutor.test.js
git commit -m "feat(frontend): execute voice actions through live targets"
```

---

### Task 8: Speech recognition adapter

**Files:**
- Create: `frontend/src/voice/stt.js`
- Test: `frontend/tests/voiceStt.test.js`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `speechRecognitionAvailable(scope = globalThis) -> boolean`
  - `createWebSpeechStt(scope = globalThis) -> { start({ onInterim, onFinal, onError }), stop() }`
  - Error codes passed to `onError`: the browser's own (`'not-allowed'`, `'service-not-allowed'`, `'audio-capture'`, `'network'`, …) plus `'restart-failed'`. `'no-speech'` and `'aborted'` are never passed on.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voiceStt.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createWebSpeechStt, speechRecognitionAvailable } = await import('../src/voice/stt.js')

function fakeScope() {
  const instances = []
  class FakeRecognition {
    constructor() {
      this.starts = 0
      this.stopped = false
      instances.push(this)
    }
    start() { this.starts += 1 }
    stop() { this.stopped = true; this.onend?.() }
  }
  return { scope: { webkitSpeechRecognition: FakeRecognition }, instances }
}

function result(text, isFinal) {
  return Object.assign([{ transcript: text }], { isFinal })
}

function listen(scope) {
  const heard = { interim: [], final: [], errors: [] }
  const stt = createWebSpeechStt(scope)
  stt.start({
    onInterim: (text) => heard.interim.push(text),
    onFinal: (text) => heard.final.push(text),
    onError: (code) => heard.errors.push(code),
  })
  return { stt, heard }
}

test('availability follows either constructor name', () => {
  assert.equal(speechRecognitionAvailable({}), false)
  assert.equal(speechRecognitionAvailable({ webkitSpeechRecognition: class {} }), true)
  assert.equal(speechRecognitionAvailable({ SpeechRecognition: class {} }), true)
})

test('recognition listens continuously in Australian English with interim words', () => {
  const { scope, instances } = fakeScope()
  listen(scope)
  const [recognition] = instances
  assert.deepEqual(
    [recognition.lang, recognition.continuous, recognition.interimResults, recognition.starts],
    ['en-AU', true, true, 1],
  )
})

test('interim and final words are reported trimmed, and empty ones are dropped', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onresult({
    resultIndex: 0,
    results: [result(' scroll ', false), result(' scroll down ', true), result('   ', true)],
  })
  assert.deepEqual(heard.interim, ['scroll'])
  assert.deepEqual(heard.final, ['scroll down'])
})

test('only results from resultIndex onwards are new', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onresult({ resultIndex: 1, results: [result('old', true), result('new', true)] })
  assert.deepEqual(heard.final, ['new'])
})

test('silence and Chrome ending the session on its own restart quietly', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onerror({ error: 'no-speech' })
  instances[0].onend()
  assert.equal(instances[0].starts, 2)
  assert.deepEqual(heard.errors, [])
})

test('a blocked microphone is reported and not retried', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onerror({ error: 'not-allowed' })
  instances[0].onend()
  assert.deepEqual(heard.errors, ['not-allowed'])
  assert.equal(instances[0].starts, 1)
})

test('stopping ends recognition without a restart', () => {
  const { scope, instances } = fakeScope()
  const { stt } = listen(scope)
  stt.stop()
  assert.equal(instances[0].stopped, true)
  assert.equal(instances[0].starts, 1)
})

test('a restart the browser refuses is reported rather than thrown', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].start = () => { throw new Error('InvalidStateError') }
  instances[0].onend()
  assert.deepEqual(heard.errors, ['restart-failed'])
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceStt.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/voice/stt.js`.

- [ ] **Step 3: Write the adapter**

Create `frontend/src/voice/stt.js`:

```js
// Chrome's Web Speech API behind the small interface the voice store needs. Chrome
// sends the audio to Google's servers; see docs/security/privacy-requirements.md.

// Neither is a failure: silence, and our own stop().
const QUIET_ERRORS = new Set(['no-speech', 'aborted'])

function recognitionClass(scope) {
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

export function speechRecognitionAvailable(scope = globalThis) {
  return recognitionClass(scope) !== null
}

export function createWebSpeechStt(scope = globalThis) {
  const Recognition = recognitionClass(scope)
  let recognition = null
  let wanted = false

  return {
    start({ onInterim, onFinal, onError }) {
      wanted = true
      recognition = new Recognition()
      recognition.lang = 'en-AU'
      recognition.continuous = true
      recognition.interimResults = true

      recognition.onresult = (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const piece = event.results[index]
          const text = piece[0].transcript.trim()
          if (!text) continue
          if (piece.isFinal) onFinal(text)
          else onInterim(text)
        }
      }

      recognition.onerror = (event) => {
        if (QUIET_ERRORS.has(event.error)) return
        wanted = false
        onError(event.error)
      }

      // Chrome ends "continuous" recognition by itself after a pause; carry on
      // until the session is really over.
      recognition.onend = () => {
        if (!wanted) return
        try {
          recognition.start()
        } catch {
          wanted = false
          onError('restart-failed')
        }
      }

      recognition.start()
    },

    stop() {
      wanted = false
      recognition?.stop()
    },
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceStt.test.js`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/voice/stt.js frontend/tests/voiceStt.test.js
git commit -m "feat(frontend): add the Web Speech recognition adapter"
```

---

### Task 9: API calls and the voice session store

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/stores/voice.js`
- Test: `frontend/tests/voiceStore.test.js`

**Interfaces:**
- Consumes: `snapshotTargets`, `snapshotContext` (Task 4); `buildBatch`, `NONE_OF_THESE` (Task 5); `decideCommand`, `decideConfirmation`, `decideSuggestion` (Task 6); `executeAction`, `describeAction` (Task 7); `createWebSpeechStt`, `speechRecognitionAvailable` (Task 8); `POST /api/v1/voice/judge` and `/voice/log` (Tasks 2–3)
- Produces:
  - `api.judgeVoiceCommand({ state, questions }) -> Promise<{ answers }>`, `api.logVoiceTurn(record) -> Promise<{ accepted }>`
  - `isStopPhrase(transcript) -> boolean`
  - `useVoiceStore()` exposing refs `status` (`idle | listening | judging | confirming | dictating | choosing`), `interim`, `heard`, `message`, `prompt`, `suggestions`, and functions `isSupported()`, `toggle()`, `startSession({ createStt?, silenceMs?, suggestionWaitMs? })`, `endSession(finalMessage?)`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/voiceStore.test.js`:

```js
import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'

const { createPinia, setActivePinia } = await import('pinia')
const { api } = await import('../src/api/client.js')
const { registerTargets, resetVoiceRegistry } = await import('../src/voice/registry.js')
const { NONE_OF_THESE, NO_SPAN } = await import('../src/voice/questions.js')
const { addressTarget, buttonTarget, pageTarget, textTarget } = await import('../src/voice/targets.js')
const { isStopPhrase, useVoiceStore } = await import('../src/stores/voice.js')

const originalJudge = api.judgeVoiceCommand
const originalLog = api.logVoiceTurn
let logs
let current

beforeEach(() => {
  logs = []
  api.logVoiceTurn = async (record) => {
    logs.push(record)
    return { accepted: true }
  }
})

afterEach(() => {
  current?.endSession()
  current = null
  api.judgeVoiceCommand = originalJudge
  api.logVoiceTurn = originalLog
  resetVoiceRegistry()
})

const a = (id, answer, probability) => ({ id, answer, probability })
const NO_STOP = a('stop', 'no', 0.95)
const flush = () => new Promise((resolve) => setImmediate(resolve))
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// The judge replies in order, one reply per call. An Error reply is thrown.
function judgeReplies(...replies) {
  const calls = []
  api.judgeVoiceCommand = async (batch) => {
    calls.push(batch)
    const reply = replies.shift()
    if (reply instanceof Error) throw reply
    return { answers: reply }
  }
  return calls
}

function begin(options = {}) {
  setActivePinia(createPinia())
  const store = useVoiceStore()
  const stt = {
    handlers: null,
    stopped: false,
    start(handlers) { this.handlers = handlers },
    stop() { this.stopped = true },
  }
  store.startSession({ createStt: () => stt, ...options })
  current = store
  return { store, stt, say: (text) => stt.handlers.onFinal(text) }
}

const fireMap = (counter) =>
  pageTarget({ id: 'page-map', label: 'Fire Map', go: () => { counter.visits += 1 } })

const removeMinh = (counter) => buttonTarget({
  id: 'm1-remove', label: 'Remove member Minh', confirm: true, press: () => { counter.presses += 1 },
})

const RESULTS = ['12 Smith St, Ballarat VIC 3350', '12 Smith Rd, Sale VIC 3850']
const destination = (place) => addressTarget({
  id: 'address-1',
  label: 'Primary destination address',
  current: place.text,
  setText: (value) => { place.text = value; place.searched = true },
  suggestions: () => (place.searched ? place.results : []),
  choose: (index) => { place.chosen = index },
})
const ADDRESS_COMMAND = [a('command', 'enter the address for Primary destination address', 0.95), NO_STOP]

test('stop phrases are matched exactly, ignoring trailing punctuation', () => {
  assert.equal(isStopPhrase('Stop.'), true)
  assert.equal(isStopPhrase(' cancel '), true)
  assert.equal(isStopPhrase('stop listening!'), true)
  assert.equal(isStopPhrase('stop the car'), false)
})

test('a session listens until it is ended', () => {
  const { store, stt } = begin()
  assert.equal(store.status, 'listening')
  store.endSession()
  assert.equal(store.status, 'idle')
  assert.equal(stt.stopped, true)
})

test('interim words are shown but never judged', () => {
  const calls = judgeReplies()
  const { store, stt } = begin()
  stt.handlers.onInterim('go to')
  assert.equal(store.interim, 'go to')
  assert.equal(calls.length, 0)
})

test('a confident command is carried out and logged once, by target id', async () => {
  const counter = { visits: 0 }
  registerTargets(() => [fireMap(counter)])
  judgeReplies([a('command', 'go to Fire Map', 0.95), NO_STOP])
  const { store, say } = begin()

  await say('go to fire map')
  await flush()

  assert.equal(counter.visits, 1)
  assert.equal(store.status, 'listening')
  assert.equal(store.message, '✓ Go to Fire Map')
  assert.equal(logs.length, 1)
  assert.deepEqual(
    [logs[0].decision, logs[0].outcome, logs[0].mode, logs[0].transcript],
    ['execute', 'ok', 'normal', 'go to fire map'],
  )
  assert.deepEqual(logs[0].answers[0], { id: 'command', answer: 'page-map', probability: 0.95 })
  assert.deepEqual(logs[0].action, { kind: 'page', target: 'page-map', value: null })
})

test('saying stop ends the session without asking the judge', async () => {
  const calls = judgeReplies()
  const { store, stt, say } = begin()
  await say('Stop.')
  await flush()
  assert.equal(calls.length, 0)
  assert.equal(store.status, 'idle')
  assert.equal(stt.stopped, true)
  assert.deepEqual(logs.map((log) => log.decision), ['stop'])
})

test('stop while a command is being judged means it is never carried out', async () => {
  const counter = { visits: 0 }
  registerTargets(() => [fireMap(counter)])
  let release
  api.judgeVoiceCommand = () => new Promise((resolve) => { release = resolve })
  const { store, say } = begin()

  const pending = say('go to fire map')
  await say('stop')
  release({ answers: [a('command', 'go to Fire Map', 0.95), NO_STOP] })
  await pending

  assert.equal(counter.visits, 0)
  assert.equal(store.status, 'idle')
})

test('while one command is judged, only the newest utterance waits its turn', async () => {
  const heard = []
  let release
  api.judgeVoiceCommand = (batch) => {
    heard.push(batch.state.transcript)
    if (heard.length === 1) return new Promise((resolve) => { release = resolve })
    return Promise.resolve({ answers: [a('command', NONE_OF_THESE, 0.9), NO_STOP] })
  }
  const { say } = begin()

  const first = say('first')
  say('second')
  say('third')
  release({ answers: [a('command', NONE_OF_THESE, 0.9), NO_STOP] })
  await first

  assert.deepEqual(heard, ['first', 'third'])
})

test('an important action waits for yes', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  const calls = judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'yes', 0.95), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  assert.equal(store.status, 'confirming')
  assert.equal(store.prompt, 'Press Remove member Minh? Say yes or no.')
  assert.equal(counter.presses, 0)

  await say('yes')
  await flush()
  assert.equal(counter.presses, 1)
  assert.equal(store.status, 'listening')
  assert.deepEqual(calls[1].questions.map((question) => question.id), ['confirm', 'stop'])
  assert.deepEqual(logs.map((log) => log.decision), ['confirm', 'execute'])
})

test('no drops the held action', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'no', 0.95), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  await say('no')

  assert.equal(counter.presses, 0)
  assert.equal(store.status, 'listening')
  assert.equal(store.message, 'Cancelled. Nothing was changed.')
})

test('an unclear answer is asked once more, then dropped', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'no', 0.3), NO_STOP],
    [a('confirm', 'no', 0.3), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  await say('hmm')
  assert.equal(store.status, 'confirming')
  assert.match(store.prompt, /^Please say yes or no\./)

  await say('hmm')
  assert.equal(store.status, 'listening')
  assert.equal(counter.presses, 0)
})

test('a value the judge could not lift is dictated and written exactly as heard', async () => {
  let name = ''
  registerTargets(() => [textTarget({
    id: 'm2-name', label: 'Name (member 2)', current: name, set: (value) => { name = value },
  })])
  const calls = judgeReplies([a('command', 'fill in Name (member 2)', 0.95), a('span', NO_SPAN, 0.9), NO_STOP])
  const { store, say } = begin()

  await say('fill in the name')
  assert.equal(store.status, 'dictating')
  assert.equal(store.prompt, 'What should I enter for Name (member 2)?')

  await say('Lan Nguyen')
  assert.equal(name, 'Lan Nguyen')
  assert.equal(calls.length, 1)
  assert.equal(store.status, 'listening')
})

test('a spoken address is typed as heard, then a numbered suggestion is chosen', async () => {
  const place = { text: '', searched: false, results: RESULTS, chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND, [a('suggestion', '2 second: 12 Smith Rd, Sale VIC 3850', 0.95), NO_STOP])
  const { store, say } = begin({ suggestionWaitMs: 500 })

  await say('primary destination')
  assert.equal(store.status, 'dictating')
  assert.equal(store.prompt, 'Say the address for Primary destination address.')

  await say('12 smith road sale')
  assert.equal(place.text, '12 smith road sale')
  assert.equal(store.status, 'choosing')
  assert.deepEqual(store.suggestions, RESULTS)

  await say('the second one')
  assert.equal(place.chosen, 1)
  assert.equal(store.message, '✓ Chose 12 Smith Rd, Sale VIC 3850')
})

test('saying none keeps the address as typed and unverified', async () => {
  const place = { text: '', searched: false, results: RESULTS, chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND, [a('suggestion', 'none', 0.95), NO_STOP])
  const { store, say } = begin({ suggestionWaitMs: 500 })

  await say('primary destination')
  await say('12 smith road sale')
  await say('none of them')

  assert.equal(place.chosen, null)
  assert.equal(place.text, '12 smith road sale')
  assert.equal(store.message, 'The address is kept as entered. It is not verified.')
})

test('with no suggestions the address stays as typed and unverified', async () => {
  const place = { text: '', searched: false, results: [], chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND)
  const { store, say } = begin({ suggestionWaitMs: 250 })

  await say('primary destination')
  await say('somewhere unknown')

  assert.equal(store.status, 'listening')
  assert.equal(place.text, 'somewhere unknown')
  assert.match(store.message, /not verified/)
})

test('one failed turn keeps listening; a second in a row ends the session', async () => {
  judgeReplies(new Error('503'), new Error('503'))
  const { store, say } = begin()

  await say('go to fire map')
  assert.equal(store.status, 'listening')
  assert.equal(store.message, 'Voice commands are unavailable right now.')

  await say('go to fire map')
  assert.equal(store.status, 'idle')
})

test('a target that disappears while the judge answers is not acted on', async () => {
  const counter = { visits: 0 }
  const unregister = registerTargets(() => [fireMap(counter)])
  api.judgeVoiceCommand = async () => {
    unregister()
    return { answers: [a('command', 'go to Fire Map', 0.95), NO_STOP] }
  }
  const { store, say } = begin()

  await say('go to fire map')
  await flush()

  assert.equal(counter.visits, 0)
  assert.equal(store.message, 'That’s no longer on this page.')
  assert.equal(logs[0].outcome, 'fail')
})

test('an overlong utterance is refused without asking the judge', async () => {
  const calls = judgeReplies()
  const { store, say } = begin()
  await say('word '.repeat(120))
  assert.equal(calls.length, 0)
  assert.equal(store.message, 'That was too long. Try a shorter command.')
})

test('silence ends the session', async () => {
  const { store } = begin({ silenceMs: 30 })
  await sleep(80)
  assert.equal(store.status, 'idle')
})

test('a blocked microphone ends the session with a way forward', () => {
  const { store, stt } = begin()
  stt.handlers.onError('not-allowed')
  assert.equal(store.status, 'idle')
  assert.equal(store.message, 'Microphone blocked — allow it in your browser settings.')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceStore.test.js`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/stores/voice.js`.

- [ ] **Step 3: Add the API calls**

In `frontend/src/api/client.js`, inside `export const api = { … }`, add after `getTestResult`:

```js
  judgeVoiceCommand: (batch) =>
    request('/voice/judge', { method: 'POST', body: JSON.stringify(batch) }),

  logVoiceTurn: (turn) =>
    request('/voice/log', { method: 'POST', body: JSON.stringify(turn) }),
```

- [ ] **Step 4: Write the store**

Create `frontend/src/stores/voice.js`:

```js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, newId } from '../api/client.js'
import { describeAction, executeAction } from '../voice/executor.js'
import { decideCommand, decideConfirmation, decideSuggestion } from '../voice/policy.js'
import { NONE_OF_THESE, buildBatch } from '../voice/questions.js'
import { snapshotContext, snapshotTargets } from '../voice/registry.js'
import { createWebSpeechStt, speechRecognitionAvailable } from '../voice/stt.js'

const MAX_TRANSCRIPT = 500
const MAX_FAILURES = 2
const MAX_SUGGESTIONS = 9
const SILENCE_MS = 30000
const SUGGESTION_WAIT_MS = 3000
const SUGGESTION_POLL_MS = 100
const STOP_PHRASES = new Set(['stop', 'cancel', 'stop listening'])

const RECOGNITION_MESSAGES = {
  'not-allowed': 'Microphone blocked — allow it in your browser settings.',
  'service-not-allowed': 'Microphone blocked — allow it in your browser settings.',
  'audio-capture': 'No microphone was found.',
  network: 'Voice recognition lost its connection. Try again.',
}

// Matched in the browser before any request, so stopping works even when the
// judge is down.
export function isStopPhrase(transcript) {
  return STOP_PHRASES.has(transcript.trim().toLowerCase().replace(/[.!?,]+$/, ''))
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export const useVoiceStore = defineStore('voice', () => {
  // idle | listening | judging | confirming | dictating | choosing
  const status = ref('idle')
  const interim = ref('')
  const heard = ref('')
  const message = ref('')
  const prompt = ref('')
  const suggestions = ref([])

  let stt = null
  // Every session and every ending bumps this, so a reply that arrives late
  // for a session already over is ignored.
  let session = 0
  let silenceTimer = null
  let settings = { silenceMs: SILENCE_MS, suggestionWaitMs: SUGGESTION_WAIT_MS }
  // What the next utterance answers: a command, a yes/no, a dictated value, or
  // a numbered suggestion.
  let phase = 'normal'
  // The action awaiting yes while confirming; the target while dictating or choosing.
  let held = null
  let reasked = false
  let failures = 0
  let busy = false
  let queued = null

  function isSupported() {
    return speechRecognitionAvailable()
  }

  function toggle() {
    if (status.value === 'idle') startSession()
    else endSession()
  }

  function startSession(options = {}) {
    if (status.value !== 'idle') return
    settings = {
      silenceMs: options.silenceMs ?? SILENCE_MS,
      suggestionWaitMs: options.suggestionWaitMs ?? SUGGESTION_WAIT_MS,
    }
    session += 1
    failures = 0
    busy = false
    queued = null
    heard.value = ''
    interim.value = ''
    clearHeld()
    setPhase('normal')
    message.value = 'Listening…'
    stt = (options.createStt ?? createWebSpeechStt)()
    stt.start({ onInterim, onFinal, onError })
    armSilence()
  }

  // Ending always discards a held action: nothing waits across sessions.
  function endSession(finalMessage = 'Stopped listening.') {
    session += 1
    clearTimeout(silenceTimer)
    const ending = stt
    stt = null
    ending?.stop()
    busy = false
    queued = null
    interim.value = ''
    clearHeld()
    phase = 'normal'
    status.value = 'idle'
    message.value = finalMessage
  }

  function setPhase(next) {
    phase = next
    status.value = next === 'normal' ? 'listening' : next
  }

  function clearHeld() {
    held = null
    reasked = false
    prompt.value = ''
    suggestions.value = []
  }

  function armSilence() {
    clearTimeout(silenceTimer)
    silenceTimer = setTimeout(
      () => endSession('Stopped listening after 30 seconds of silence.'),
      settings.silenceMs,
    )
  }

  function onInterim(text) {
    interim.value = text
    armSilence()
  }

  function onError(code) {
    endSession(RECOGNITION_MESSAGES[code] ?? 'Voice recognition stopped unexpectedly.')
  }

  function onFinal(text) {
    if (status.value === 'idle') return Promise.resolve()
    interim.value = ''
    heard.value = text
    armSilence()
    if (isStopPhrase(text)) {
      logTurn({
        turnId: newId('vt'), mode: phase, transcript: text,
        decision: 'stop', outcome: 'none', startedAt: Date.now(),
      })
      endSession('Stopped.')
      return Promise.resolve()
    }
    // One turn at a time. Only the newest waiting utterance is kept.
    if (busy) {
      queued = text
      return Promise.resolve()
    }
    return process(text)
  }

  async function process(transcript) {
    const mySession = session
    busy = true
    try {
      if (phase === 'dictating') await takeDictation(transcript, mySession)
      else await judgeTurn(transcript, mySession)
    } finally {
      if (mySession === session) busy = false
    }
    if (mySession === session && queued !== null) {
      const next = queued
      queued = null
      await process(next)
    }
  }

  async function judgeTurn(transcript, mySession) {
    const turn = {
      turnId: newId('vt'), mode: phase, transcript,
      answers: [], catalogue: [], judgeMs: null, startedAt: Date.now(),
    }
    if (transcript.length > MAX_TRANSCRIPT) {
      message.value = 'That was too long. Try a shorter command.'
      logTurn({ ...turn, decision: 'reject', outcome: 'none' })
      return
    }

    const batch = buildBatch({
      transcript,
      targets: snapshotTargets(),
      context: snapshotContext(),
      mode: phase,
      choosing: suggestions.value,
    })
    status.value = 'judging'
    let answers
    try {
      ({ answers } = await api.judgeVoiceCommand({ state: batch.state, questions: batch.questions }))
    } catch {
      if (mySession !== session) return
      failures += 1
      logTurn({ ...turn, decision: 'unavailable', outcome: 'none' })
      if (failures >= MAX_FAILURES) {
        endSession('Voice commands are unavailable right now.')
        return
      }
      clearHeld()
      setPhase('normal')
      message.value = 'Voice commands are unavailable right now.'
      return
    }
    if (mySession !== session) return

    failures = 0
    Object.assign(turn, {
      answers, catalogue: batch.catalogue, judgeMs: Date.now() - turn.startedAt,
    })
    if (turn.mode === 'confirming') await settleConfirmation(turn, mySession)
    else if (turn.mode === 'choosing') settleChoice(turn)
    else await settleCommand(turn, mySession)
  }

  async function settleCommand(turn, mySession) {
    const decision = decideCommand(turn.answers, turn.catalogue)
    switch (decision.type) {
      case 'stop':
        logTurn({ ...turn, decision: 'stop', outcome: 'none' })
        endSession('Stopped.')
        return
      case 'reject':
        setPhase('normal')
        message.value = 'I didn’t catch that.'
        logTurn({ ...turn, decision: 'reject', outcome: 'none' })
        return
      case 'confirm':
        held = decision.action
        reasked = false
        setPhase('confirming')
        message.value = ''
        prompt.value = `${describeAction(decision.action)}? Say yes or no.`
        logTurn({ ...turn, decision: 'confirm', action: decision.action, outcome: 'pending' })
        return
      case 'dictate': {
        const { target } = decision
        held = target
        setPhase('dictating')
        message.value = ''
        prompt.value = target.kind === 'address'
          ? `Say the address for ${target.label}.`
          : `What should I enter for ${target.label}?`
        logTurn({
          ...turn, decision: 'dictate',
          action: { kind: target.kind, target, value: null }, outcome: 'pending',
        })
        return
      }
      default:
        await perform(decision.action, turn, 'execute', mySession)
    }
  }

  async function perform(action, turn, decision, mySession) {
    const result = await executeAction(action, snapshotTargets())
    logTurn({ ...turn, decision, action, outcome: result.ok ? 'ok' : 'fail' })
    if (mySession !== session) return
    clearHeld()
    setPhase('normal')
    message.value = result.message
  }

  async function settleConfirmation(turn, mySession) {
    const decision = decideConfirmation(turn.answers)
    const action = held
    if (decision.type === 'stop') {
      logTurn({ ...turn, decision: 'stop', action, outcome: 'none' })
      endSession('Stopped.')
      return
    }
    if (decision.type === 'execute') {
      await perform(action, turn, 'execute', mySession)
      return
    }
    if (decision.type === 'unclear' && !reasked) {
      reasked = true
      setPhase('confirming')
      prompt.value = `Please say yes or no. ${describeAction(action)}?`
      logTurn({ ...turn, decision: 'unclear', action, outcome: 'pending' })
      return
    }
    logTurn({ ...turn, decision: decision.type, action, outcome: 'none' })
    clearHeld()
    setPhase('normal')
    message.value = decision.type === 'cancel'
      ? 'Cancelled. Nothing was changed.'
      : 'I still didn’t catch that, so nothing was changed.'
  }

  function settleChoice(turn) {
    const decision = decideSuggestion(turn.answers)
    const target = held
    const logged = (value = null) => ({ kind: 'address', target, value })
    if (decision.type === 'stop') {
      logTurn({ ...turn, decision: 'stop', action: logged(), outcome: 'none' })
      endSession('Stopped.')
      return
    }
    if (decision.type === 'choose') {
      const chosen = suggestions.value[decision.index]
      const live = snapshotTargets().find((item) => item.id === target.id)
      // Only the very list the user was shown: the field may have changed since.
      const ok = chosen !== undefined && live?.suggestions?.()[decision.index] === chosen
      if (ok) live.choose(decision.index)
      logTurn({ ...turn, decision: 'choose', action: logged(chosen ?? null), outcome: ok ? 'ok' : 'fail' })
      clearHeld()
      setPhase('normal')
      message.value = ok
        ? `✓ Chose ${chosen}`
        : 'Those suggestions changed, so the address is kept as entered and is not verified.'
      return
    }
    if (decision.type === 'unclear' && !reasked) {
      reasked = true
      setPhase('choosing')
      prompt.value = 'Please say a number from the list, or none.'
      logTurn({ ...turn, decision: 'unclear', action: logged(), outcome: 'pending' })
      return
    }
    logTurn({ ...turn, decision: decision.type, action: logged(), outcome: 'none' })
    clearHeld()
    setPhase('normal')
    message.value = 'The address is kept as entered. It is not verified.'
  }

  async function takeDictation(transcript, mySession) {
    const turn = {
      turnId: newId('vt'), mode: 'dictating', transcript,
      answers: [], catalogue: [], judgeMs: null, startedAt: Date.now(),
    }
    const target = held
    const action = { kind: target.kind, target, value: transcript }
    if (target.kind !== 'address') {
      await perform(action, turn, 'dictated', mySession)
      return
    }

    // The address goes in exactly as heard; the component's own lookup runs.
    const result = await executeAction(action, snapshotTargets())
    if (!result.ok) {
      logTurn({ ...turn, decision: 'dictated', action, outcome: 'fail' })
      if (mySession !== session) return
      clearHeld()
      setPhase('normal')
      message.value = result.message
      return
    }
    clearHeld()
    status.value = 'judging'
    const found = await waitForSuggestions(target.id, mySession)
    if (mySession !== session) return
    if (!found.length) {
      logTurn({ ...turn, decision: 'dictated', action, outcome: 'ok' })
      setPhase('normal')
      message.value = 'No matching addresses were found. The address is kept as entered and is not verified.'
      return
    }
    held = target
    reasked = false
    suggestions.value = found.slice(0, MAX_SUGGESTIONS)
    setPhase('choosing')
    message.value = ''
    prompt.value = 'Say a number from the list, or none.'
    logTurn({ ...turn, decision: 'dictated', action, outcome: 'pending' })
  }

  async function waitForSuggestions(targetId, mySession) {
    const deadline = Date.now() + settings.suggestionWaitMs
    while (Date.now() < deadline) {
      await sleep(SUGGESTION_POLL_MS)
      if (mySession !== session) return []
      const live = snapshotTargets().find((item) => item.id === targetId)
      const found = live?.suggestions?.() ?? []
      if (found.length) return found
    }
    return []
  }

  // Logged as the target id, never the spoken phrase: phrases can hold names.
  function commandTargetId(phrase, catalogue) {
    if (phrase === NONE_OF_THESE) return NONE_OF_THESE
    return catalogue.find((entry) => entry.phrase === phrase)?.target.id ?? null
  }

  function logTurn({
    turnId, mode, transcript, answers = [], catalogue = [],
    decision, action = null, outcome, judgeMs = null, startedAt,
  }) {
    const context = snapshotContext()
    const value = action?.value
    const record = {
      turn_id: turnId,
      page: context.page,
      step: context.step,
      mode,
      transcript: transcript.slice(0, MAX_TRANSCRIPT),
      answers: answers.map((answer) => ({
        id: answer.id,
        answer: answer.id === 'command' ? commandTargetId(answer.answer, catalogue) : answer.answer,
        probability: answer.probability,
      })),
      decision,
      action: action && {
        kind: action.kind,
        target: action.target.id,
        value: value === null || value === undefined ? null : String(value).slice(0, MAX_TRANSCRIPT),
      },
      outcome,
      latency_ms: { judge: judgeMs, turn: Math.max(0, Date.now() - startedAt) },
    }
    // Fire and forget: a missed log line is never the user's problem.
    Promise.resolve()
      .then(() => api.logVoiceTurn(record))
      .catch(() => {})
  }

  return {
    status,
    interim,
    heard,
    message,
    prompt,
    suggestions,
    isSupported,
    toggle,
    startSession,
    endSession,
  }
})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceStore.test.js`
Expected: 19 tests pass.

Run: `cd frontend && npm test`
Expected: every test file passes, old and new.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/stores/voice.js frontend/tests/voiceStore.test.js
git commit -m "feat(frontend): add the voice session store"
```

---

### Task 10: Microphone button and the layout's global commands

**Files:**
- Create: `frontend/src/components/voice/VoiceButton.vue`
- Modify: `frontend/src/components/layout/AppLayout.vue`

**Interfaces:**
- Consumes: `useVoiceStore` (Task 9); `useVoiceCommands`, `useVoiceContext` (Task 4); `pageTarget`, `commandTarget` (Task 4)
- Produces: global targets on every page, with ids `page-home`, `page-plan`, `page-overview`, `page-map`, `page-scenarios`, `go-back`, `scroll-down`, `scroll-up`, `scroll-top`, `scroll-bottom`; context `{ page: <route name> }`

Component wiring has no unit tests (`node --test` has no DOM). Each step below is verified by the build and by hand.

- [ ] **Step 1: Create the button**

Create `frontend/src/components/voice/VoiceButton.vue`:

```vue
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useVoiceStore } from '../../stores/voice'

const voice = useVoiceStore()
const supported = voice.isSupported()
const active = computed(() => voice.status !== 'idle')
const label = computed(() => (active.value ? 'Stop voice control' : 'Start voice control'))

// When a session ends, its last message stays briefly so a reason such as a
// blocked microphone can be read, then the panel closes.
const lingering = ref(false)
let lingerTimer
watch(active, (isActive) => {
  clearTimeout(lingerTimer)
  lingering.value = !isActive && Boolean(voice.message)
  if (lingering.value) lingerTimer = setTimeout(() => { lingering.value = false }, 6000)
})

onBeforeUnmount(() => {
  clearTimeout(lingerTimer)
  if (active.value) voice.endSession()
})
</script>

<template>
  <div class="voice">
    <section v-if="active || lingering" class="voice-panel" aria-live="polite">
      <p v-if="voice.interim" class="voice-interim">{{ voice.interim }}…</p>
      <p v-else-if="active && voice.heard" class="voice-heard">“{{ voice.heard }}”</p>
      <p v-if="voice.status === 'judging'" class="voice-working">Working…</p>
      <p v-if="voice.prompt" class="voice-prompt">{{ voice.prompt }}</p>
      <ol v-if="voice.suggestions.length" class="voice-suggestions">
        <li v-for="suggestion in voice.suggestions" :key="suggestion">{{ suggestion }}</li>
      </ol>
      <p v-if="voice.message" class="voice-message">{{ voice.message }}</p>
    </section>
    <button
      type="button"
      class="voice-button"
      :class="{ 'is-active': active }"
      :disabled="!supported"
      :aria-pressed="active"
      :aria-label="label"
      :title="supported ? label : 'Voice control needs Chrome or Edge'"
      @click="voice.toggle()"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="3" width="6" height="11" rx="3"></rect>
        <path d="M5 11a7 7 0 0 0 14 0"></path>
        <path d="M12 18v3"></path>
      </svg>
    </button>
  </div>
</template>

<style scoped>
/* Raised above the plan builder's save bar so it never covers Save plan. */
.voice { position: fixed; right: 1.5rem; bottom: 6.5rem; z-index: 30; display: flex; flex-direction: column; align-items: flex-end; gap: 0.75rem; pointer-events: none; }
.voice > * { pointer-events: auto; }
.voice-panel { width: min(22rem, calc(100vw - 3rem)); padding: 0.9rem 1rem; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-card); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16); }
.voice-panel p { margin: 0; }
.voice-panel > * + * { margin-top: 0.5rem; }
.voice-interim, .voice-working { color: var(--color-text-muted); }
.voice-heard { font-style: italic; }
.voice-prompt { font-weight: 600; }
.voice-suggestions { margin-bottom: 0; padding-left: 1.25rem; }
.voice-button { display: grid; place-items: center; width: 3.25rem; height: 3.25rem; border: 1px solid var(--color-border); border-radius: var(--radius-pill); background: var(--color-bg-card); color: var(--color-accent); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18); cursor: pointer; }
.voice-button.is-active { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-bg-card); }
.voice-button:disabled { cursor: not-allowed; opacity: 0.5; }
.voice-button:focus-visible { outline: 3px solid var(--color-accent-soft); outline-offset: 2px; }
@media print { .voice { display: none; } }
</style>
```

- [ ] **Step 2: Register the global commands in the layout**

In `frontend/src/components/layout/AppLayout.vue`, add a script block before `<template>`:

```vue
<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VoiceButton from '../voice/VoiceButton.vue'
import { useVoiceCommands, useVoiceContext } from '../../voice/registry.js'
import { commandTarget, pageTarget } from '../../voice/targets.js'

const router = useRouter()
const route = useRoute()
// The page scrolls inside <main>, not the window: the layout fixes its height
// and hides window overflow.
const content = ref(null)

const PAGES = [
  ['page-home', 'Home', '/'],
  ['page-plan', 'My Plan', '/plan'],
  ['page-overview', 'Overview', '/overview'],
  ['page-map', 'Fire Map', '/map'],
  ['page-scenarios', 'Test My Plan', '/scenarios'],
]

function scrollByScreens(screens) {
  const main = content.value
  main?.scrollBy({ top: main.clientHeight * screens, behavior: 'smooth' })
}

function scrollToEnd(end) {
  const main = content.value
  main?.scrollTo({ top: end === 'top' ? 0 : main.scrollHeight, behavior: 'smooth' })
}

useVoiceContext(() => ({ page: typeof route.name === 'string' ? route.name : null }))

// Registered first, so these survive if a page offers more than the judge accepts.
useVoiceCommands(() => [
  ...PAGES.map(([id, label, path]) => pageTarget({ id, label, go: () => router.push(path) })),
  commandTarget({ id: 'go-back', label: 'go back', run: () => router.back() }),
  commandTarget({ id: 'scroll-down', label: 'scroll down', run: () => scrollByScreens(0.8) }),
  commandTarget({ id: 'scroll-up', label: 'scroll up', run: () => scrollByScreens(-0.8) }),
  commandTarget({ id: 'scroll-top', label: 'scroll to the top', run: () => scrollToEnd('top') }),
  commandTarget({ id: 'scroll-bottom', label: 'scroll to the bottom', run: () => scrollToEnd('bottom') }),
])
</script>
```

Replace `<main class="content"><router-view /></main>` with:

```vue
    <main ref="content" class="content"><router-view /></main>
    <VoiceButton />
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 4: Check it by hand**

Start the backend with the mock judge and full logging (from `backend/`):

```bash
APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock VOICE_LOG_CONTENT=true \
  .venv/bin/uvicorn app.main:app --reload --port 8000
```

and the frontend (`cd frontend && npm run dev`). In **Chrome** at http://localhost:5173:

1. The microphone button sits at the bottom right on every page.
2. Press it and allow the microphone. The panel shows "Listening…" and your words as you speak.
3. "go to fire map" opens Fire Map; "overview" opens Overview; "go back" returns.
4. On Overview, "scroll down", "scroll up", "scroll to the top", "scroll to the bottom" move the page.
5. "stop" closes the session; the panel's last message fades after about six seconds.
6. On My Plan, the button does not cover the **Save plan** button at the bottom of the page. At a narrow window width too.
7. In Firefox or Safari the button is dimmed and its tooltip reads "Voice control needs Chrome or Edge".
8. `tail -n 3 backend/logs/voice-turns.jsonl` shows one line per thing you said.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/voice/VoiceButton.vue frontend/src/components/layout/AppLayout.vue
git commit -m "feat(frontend): add the voice button and global voice commands"
```

---

### Task 11: Plan builder, household members and address fields

**Files:**
- Modify: `frontend/src/views/PlanBuilderView.vue`
- Modify: `frontend/src/components/household/HouseholdMembersForm.vue`
- Modify: `frontend/src/components/common/AddressAutocompleteInput.vue`

**Interfaces:**
- Consumes: `VoiceScope` and `useVoiceCommands`, `useVoiceContext` (Task 4); target builders, `rowName`, `spokenWholeNumber` (Task 4)
- Produces: `AddressAutocompleteInput` accepts `voiceLabel` (String, default `''`) and registers an address target only when it is set; context `{ step: <plan step id> }` on the plan builder. Task 12 passes `voiceLabel` from the destination fields.

- [ ] **Step 1: Let address fields take part**

In `frontend/src/components/common/AddressAutocompleteInput.vue`:

Add to the imports:

```js
import { useVoiceCommands } from '../../voice/registry.js'
import { addressTarget } from '../../voice/targets.js'
```

Add to `defineProps({ … })`:

```js
  // The spoken name for this field. Without it the field is not voice-controlled.
  voiceLabel: { type: String, default: '' },
```

Append at the end of `<script setup>`, after `keydown`:

```js
function describeSuggestion(suggestion) {
  return `${suggestion.address}, ${suggestion.suburb_or_locality} ${suggestion.state} ${suggestion.postcode}`
}

// Suggestions are offered only once a lookup has finished for the current text,
// so a list left over from earlier typing is never read out as the new result.
useVoiceCommands(() => (props.voiceLabel && !props.disabled
  ? [addressTarget({
      id: `address-${componentId}`,
      label: props.voiceLabel,
      current: props.modelValue,
      setText: update,
      suggestions: () => (status.value === 'success' ? suggestions.value.map(describeSuggestion) : []),
      choose: (index) => select(suggestions.value[index]),
    })]
  : []))
```

- [ ] **Step 2: Register the plan builder's own commands and scope its steps**

In `frontend/src/views/PlanBuilderView.vue`:

Replace `import { useRoute } from 'vue-router'` with `import { useRoute, useRouter } from 'vue-router'`, and add below the other component imports:

```js
import VoiceScope from '../components/voice/VoiceScope.vue'
import { useVoiceCommands, useVoiceContext } from '../voice/registry.js'
import { buttonTarget, commandTarget } from '../voice/targets.js'
```

Below `const route = useRoute()` add `const router = useRouter()`.

Append at the end of `<script setup>`, after `save()`:

```js
useVoiceContext(() => ({ step: currentStep.value.id }))

useVoiceCommands(() => {
  if (!draft.value) return []
  const targets = STEPS.map((step, index) =>
    commandTarget({ id: `step-${step.id}`, label: `${step.label} section`, run: () => goToStep(index) }))
  targets.push(buttonTarget({
    id: 'step-back',
    label: 'Back',
    aliases: ['previous step'],
    disabled: stepIndex.value === 0,
    press: () => goToStep(stepIndex.value - 1),
  }))
  if (stepIndex.value < STEPS.length - 1) {
    targets.push(buttonTarget({
      id: 'step-continue',
      label: 'Continue',
      aliases: ['next step'],
      press: () => goToStep(stepIndex.value + 1),
    }))
  } else {
    targets.push(buttonTarget({ id: 'test-my-plan', label: 'Test my plan', press: () => router.push('/scenarios') }))
  }
  targets.push(buttonTarget({
    id: 'save-plan',
    label: 'Save plan',
    confirm: true,
    disabled: !hasUnsavedChanges.value || validationErrors.value.length > 0 || householdStore.saveStatus === 'loading',
    press: save,
  }))
  return targets
})
```

In the template, replace the five step blocks:

```vue
        <div v-show="stepIndex === 0">
          <HouseholdMembersForm v-model:members="draft.members" v-model:animals="draft.animals" />
        </div>
        <div v-show="stepIndex === 1">
          <TransportForm
            id="plan-transport"
            tabindex="-1"
            v-model:transports="draft.transports"
            v-model:has-private-transport="draft.has_private_transport"
            :members="draft.members"
          />
        </div>
        <div v-show="stepIndex === 2">
          <ArrangementsForm id="plan-destinations" v-model="draft.arrangements" :transports="draft.transports" tabindex="-1" />
        </div>
        <div v-show="stepIndex === 3">
          <ResponsibilitiesForm id="plan-responsibilities" v-model="draft.responsibilities" :members="draft.members" tabindex="-1" />
        </div>
        <div v-show="stepIndex === 4">
          <PlanChecks :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
        </div>
```

with:

```vue
        <!-- All five steps stay mounted; each scope offers voice commands only while visible. -->
        <VoiceScope :active="stepIndex === 0">
          <div v-show="stepIndex === 0">
            <HouseholdMembersForm v-model:members="draft.members" v-model:animals="draft.animals" />
          </div>
        </VoiceScope>
        <VoiceScope :active="stepIndex === 1">
          <div v-show="stepIndex === 1">
            <TransportForm
              id="plan-transport"
              tabindex="-1"
              v-model:transports="draft.transports"
              v-model:has-private-transport="draft.has_private_transport"
              :members="draft.members"
            />
          </div>
        </VoiceScope>
        <VoiceScope :active="stepIndex === 2">
          <div v-show="stepIndex === 2">
            <ArrangementsForm id="plan-destinations" v-model="draft.arrangements" :transports="draft.transports" tabindex="-1" />
          </div>
        </VoiceScope>
        <VoiceScope :active="stepIndex === 3">
          <div v-show="stepIndex === 3">
            <ResponsibilitiesForm id="plan-responsibilities" v-model="draft.responsibilities" :members="draft.members" tabindex="-1" />
          </div>
        </VoiceScope>
        <div v-show="stepIndex === 4">
          <PlanChecks :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
        </div>
```

- [ ] **Step 3: Register every member and animal field**

In `frontend/src/components/household/HouseholdMembersForm.vue`:

Add to the imports:

```js
import { useVoiceCommands } from '../../voice/registry.js'
import {
  buttonTarget,
  checkboxTarget,
  rowName,
  selectTarget,
  spokenWholeNumber,
  textTarget,
} from '../../voice/targets.js'
```

Append at the end of `<script setup>`, after `changeAnimalCategory`:

```js
function memberTargets(member, index) {
  const who = rowName(member.display_name, 'member', index)
  const key = member.member_id
  const targets = [
    textTarget({
      id: `${key}-name`, label: `Name (${who})`, current: member.display_name,
      set: (value) => { member.display_name = value },
    }),
    selectTarget({
      id: `${key}-relationship`,
      label: `Relationship to household (${who})`,
      choices: [
        { label: 'Prefer not to specify', value: null },
        ...RELATIONSHIPS.map(([value, label]) => ({ label, value })),
      ],
      current: member.relationship,
      set: (value) => { member.relationship = value },
    }),
    selectTarget({
      id: `${key}-usual-kind`,
      label: `Where they are during the day (${who})`,
      choices: [
        { label: 'Not recorded', value: '' },
        ...USUAL_LOCATION_KINDS.map(([value, label]) => ({ label, value })),
      ],
      current: member.usual_location?.kind ?? '',
      set: (value) => setUsualKind(member, value),
    }),
    textTarget({
      id: `${key}-support`, label: `Other support needs (${who})`, current: member.support_notes,
      set: (value) => { member.support_notes = value },
    }),
    checkboxTarget({
      id: `${key}-dependant`, label: `Needs help from another household member (${who})`,
      current: member.is_dependant, set: (value) => { member.is_dependant = value },
    }),
    checkboxTarget({
      id: `${key}-mobility`, label: `Has limited mobility (${who})`,
      current: member.mobility_support_required,
      set: (value) => { member.mobility_support_required = value },
    }),
    buttonTarget({
      id: `${key}-remove`, label: `Remove member ${who}`, confirm: true,
      press: () => removeMember(key),
    }),
  ]
  if (member.relationship === 'other') {
    targets.push(textTarget({
      id: `${key}-relationship-other`, label: `Relationship details (${who})`,
      current: member.relationship_other, set: (value) => { member.relationship_other = value },
    }))
  }
  return targets
}

function animalTargets(animal, index) {
  const which = rowName(animal.display_name, 'animal', index)
  const key = animal.animal_id
  const targets = [
    selectTarget({
      id: `${key}-category`,
      label: `Category (${which})`,
      choices: [{ label: 'Pet', value: 'pet' }, { label: 'Livestock', value: 'livestock' }],
      current: animal.category,
      set: (value) => {
        animal.category = value
        changeAnimalCategory(animal)
      },
    }),
    selectTarget({
      id: `${key}-type`,
      label: `Animal type (${which})`,
      choices: ANIMAL_TYPES[animal.category].map(([value, label]) => ({ label, value })),
      current: animal.animal_type,
      set: (value) => { animal.animal_type = value },
    }),
    textTarget({
      id: `${key}-quantity`, label: `Quantity (${which})`, current: String(animal.quantity ?? ''),
      set: (value) => { animal.quantity = spokenWholeNumber(value) },
    }),
    textTarget({
      id: `${key}-name`, label: `Name (${which})`, current: animal.display_name,
      set: (value) => { animal.display_name = value },
    }),
    textTarget({
      id: `${key}-notes`, label: `Special transport or care notes (${which})`, current: animal.support_notes,
      set: (value) => { animal.support_notes = value },
    }),
    buttonTarget({
      id: `${key}-remove`, label: `Remove animal ${which}`, confirm: true,
      press: () => removeAnimal(key),
    }),
  ]
  if (animal.animal_type === 'other') {
    targets.push(textTarget({
      id: `${key}-type-other`, label: `Other animal type (${which})`, current: animal.animal_type_other,
      set: (value) => { animal.animal_type_other = value },
    }))
  }
  return targets
}

useVoiceCommands(() => [
  buttonTarget({
    id: 'add-member',
    label: members.value.length ? 'Add another member' : 'Add member',
    press: addMember,
  }),
  ...members.value.flatMap(memberTargets),
  buttonTarget({
    id: 'add-animal',
    label: animals.value.length ? 'Add another animal' : 'Add animal',
    press: addAnimal,
  }),
  ...animals.value.flatMap(animalTargets),
])
```

In the template, replace `<div v-for="member in members" :key="member.member_id" class="member-row">` with:

```vue
      <div v-for="(member, index) in members" :key="member.member_id" class="member-row">
```

and in the member's `<AddressAutocompleteInput`, below `label="Address"`, add:

```vue
              :voice-label="`Daytime address (${rowName(member.display_name, 'member', index)})`"
```

- [ ] **Step 4: Build and run the tests**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 5: Check it by hand**

With the backend and frontend running as in Task 10, on **My Plan → People** in Chrome. The mock judge only counts shared words, so a command that partly matches its label ("where is Minh during the day") asks "…? Say yes or no." before acting; answer "yes". That is the mock's matching, not a fault, and the log records it.

1. "add member" adds a member. "name is Minh" fills that member's name.
2. "Minh's relationship is parent" sets Relationship to Parent.
3. "add another member", then "fill in the name" asks "What should I enter for Name (member 2)?"; saying "Lan" fills it.
4. "name is Tom" now asks to confirm before changing either filled name.
5. "Minh has limited mobility" ticks the box; "Minh does not have limited mobility" unticks it.
6. "where is Minh during the day, work", then "daytime address for Minh", then a real Victorian street address: the suggestions appear numbered in the panel; "the first one" picks it and the field reads "Verified address" after saving.
7. "remove member Lan" asks for yes or no; "no" leaves Lan in place.
8. "add animal", "quantity is two" sets 2 (after confirming, because 1 was already there); "quantity is lots" shows "Say the quantity as a whole number, such as 2."
9. "next step" moves to Transport; "Minh" fields no longer respond ("name is Tom" is not understood).
10. "People section" returns. "save plan" asks to confirm, then saves.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PlanBuilderView.vue \
  frontend/src/components/household/HouseholdMembersForm.vue \
  frontend/src/components/common/AddressAutocompleteInput.vue
git commit -m "feat(frontend): voice commands for the plan builder and household members"
```

---

### Task 12: Transport, destinations and responsibilities

**Files:**
- Modify: `frontend/src/components/household/TransportForm.vue`
- Modify: `frontend/src/components/household/ArrangementsForm.vue`
- Modify: `frontend/src/components/household/ResponsibilitiesForm.vue`

**Interfaces:**
- Consumes: `useVoiceCommands`, target builders, `rowName` (Task 4); `AddressAutocompleteInput`'s `voiceLabel` (Task 11)
- Produces: nothing new for later tasks

- [ ] **Step 1: Transport**

In `frontend/src/components/household/TransportForm.vue`:

Add to the imports:

```js
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget, checkboxTarget, rowName, selectTarget, textTarget } from '../../voice/targets.js'
```

Add below `const hasPrivateTransport = …`:

```js
// One list for the dropdown and for voice, so the options can never drift apart.
const TRANSPORT_TYPES = [
  ['car', 'Car / SUV'],
  ['ute', 'Ute / Pickup'],
  ['van', 'Van'],
  ['motorbike', 'Motorbike'],
  ['truck', 'Truck'],
  ['other', 'Other'],
]
```

In the template, replace the six hard-coded options:

```vue
              <option value="car">Car / SUV</option>
              <option value="ute">Ute / Pickup</option>
              <option value="van">Van</option>
              <option value="motorbike">Motorbike</option>
              <option value="truck">Truck</option>
              <option value="other">Other</option>
```

with:

```vue
              <option v-for="[value, label] in TRANSPORT_TYPES" :key="value" :value="value">{{ label }}</option>
```

Append at the end of `<script setup>`:

```js
function transportTargets(transport, index) {
  const vehicle = rowName(transport.display_name, 'transport', index)
  const key = transport.transport_id
  const targets = [
    selectTarget({
      id: `${key}-type`,
      label: `Type (${vehicle})`,
      choices: TRANSPORT_TYPES.map(([value, label]) => ({ label, value })),
      current: transport.transport_type,
      set: (value) => {
        transport.transport_type = value
        markPrivateTransport(transport)
      },
    }),
    textTarget({
      id: `${key}-name`, label: `Vehicle name (${vehicle})`, current: transport.display_name,
      set: (value) => { transport.display_name = value },
    }),
    ...props.members.map((member) => checkboxTarget({
      id: `${key}-driver-${member.member_id}`,
      label: `${memberName(member.member_id)} can drive (${vehicle})`,
      current: transport.driver_member_ids.includes(member.member_id),
      set: (value) => {
        if (value !== transport.driver_member_ids.includes(member.member_id)) {
          toggleDriver(transport, member.member_id)
        }
      },
    })),
    buttonTarget({
      id: `${key}-remove`, label: `Remove transport ${vehicle}`, confirm: true,
      press: () => removeTransport(key),
    }),
  ]
  if (transport.transport_type === 'other') {
    targets.push(textTarget({
      id: `${key}-type-other`, label: `Other transport type (${vehicle})`,
      current: transport.transport_type_other,
      set: (value) => { transport.transport_type_other = value },
    }))
  }
  return targets
}

useVoiceCommands(() => {
  if (transports.value.length === 0) {
    return [
      buttonTarget({ id: 'add-private-transport', label: 'Add private transport', press: addPrivateTransport }),
      hasPrivateTransport.value !== false
        ? buttonTarget({ id: 'no-private-transport', label: 'We have no private transport', press: recordNoPrivateTransport })
        : buttonTarget({ id: 'add-other-arrangement', label: 'Add another transport arrangement', press: addOtherArrangement }),
    ]
  }
  return [
    ...transports.value.flatMap(transportTargets),
    buttonTarget({
      id: 'add-transport-option',
      label: 'Add another transport option',
      press: () => (hasPrivateTransport.value === false ? addOtherArrangement() : addPrivateTransport()),
    }),
  ]
})
```

- [ ] **Step 2: Destinations**

In `frontend/src/components/household/ArrangementsForm.vue`:

Replace `defineProps({ transports: { type: Array, required: true } })` with:

```js
const props = defineProps({ transports: { type: Array, required: true } })
```

Add to the imports:

```js
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget, selectTarget, textTarget } from '../../voice/targets.js'
```

Append at the end of `<script setup>`:

```js
function transportChoices() {
  return [
    { label: 'Not set', value: null },
    ...props.transports.map((transport) => ({
      label: transportOptionLabel(transport),
      value: transport.transport_id,
    })),
  ]
}

function backupTargets(backup, index) {
  const which = `backup ${index + 1}`
  const targets = [
    selectTarget({
      id: `backup-${index}-transport`,
      label: `Backup transport (${which})`,
      choices: transportChoices(),
      current: backup.transport_id,
      set: (value) => { backup.transport_id = value },
    }),
    textTarget({
      id: `backup-${index}-name`,
      label: `Backup destination name (${which})`,
      current: backup.destination?.display_name ?? '',
      set: (value) => setBackupDestinationField(backup, 'display_name', value),
    }),
    buttonTarget({
      id: `backup-${index}-remove`, label: `Remove ${which}`, confirm: true,
      press: () => removeBackupArrangement(index),
    }),
  ]
  if (backup.destination) {
    targets.push(buttonTarget({
      id: `backup-${index}-clear`, label: `Clear destination (${which})`, confirm: true,
      press: () => { backup.destination = null },
    }))
  }
  return targets
}

useVoiceCommands(() => [
  selectTarget({
    id: 'primary-transport',
    label: 'Primary transport',
    choices: transportChoices(),
    current: arrangements.value.primary_transport_id,
    set: (value) => { arrangements.value.primary_transport_id = value },
  }),
  textTarget({
    id: 'primary-destination-name',
    label: 'Primary destination name',
    current: primaryName.value,
    set: (value) => { primaryName.value = value },
  }),
  buttonTarget({ id: 'add-backup', label: 'Add backup arrangement', press: addBackupArrangement }),
  ...(arrangements.value.backup_arrangements ?? []).flatMap(backupTargets),
  textTarget({
    id: 'meeting-point',
    label: 'Meeting point',
    current: arrangements.value.meeting_point,
    set: (value) => { arrangements.value.meeting_point = value },
  }),
])
```

In the template, add to the primary destination's `<AddressAutocompleteInput` (the one bound to `primaryAddress`):

```vue
voice-label="Primary destination address"
```

and to the backup destination's `<AddressAutocompleteInput` (the one bound to `backup.destination?.address`):

```vue
:voice-label="`Backup destination address (backup ${index + 1})`"
```

- [ ] **Step 3: Responsibilities**

In `frontend/src/components/household/ResponsibilitiesForm.vue`:

Replace `defineProps({ members: { type: Array, required: true } })` with:

```js
const props = defineProps({ members: { type: Array, required: true } })
```

Add to the imports:

```js
import { useVoiceCommands } from '../../voice/registry.js'
import { buttonTarget, rowName, selectTarget, textTarget } from '../../voice/targets.js'
```

Append at the end of `<script setup>`:

```js
function personChoices() {
  return [
    { label: 'Not set', value: null },
    ...props.members.map((member) => ({
      label: member.display_name || 'Unnamed member',
      value: member.member_id,
    })),
  ]
}

function responsibilityTargets(r, index) {
  const which = rowName(r.task_name, 'responsibility', index)
  const key = r.responsibility_id
  const targets = [
    selectTarget({
      id: `${key}-task`,
      label: `Task (${which})`,
      choices: [...TASK_PRESETS.map((task) => ({ label: task, value: task })), { label: 'Other', value: 'other' }],
      current: selectedTask(r.task_name),
      set: (value) => changeTask(r, value),
    }),
    selectTarget({
      id: `${key}-primary`, label: `Primary person (${which})`, choices: personChoices(),
      current: r.primary_member_id, set: (value) => { r.primary_member_id = value },
    }),
    selectTarget({
      id: `${key}-backup`, label: `Backup person (${which})`, choices: personChoices(),
      current: r.backup_member_id, set: (value) => { r.backup_member_id = value },
    }),
    buttonTarget({
      id: `${key}-remove`, label: `Remove responsibility ${which}`, confirm: true,
      press: () => removeResponsibility(key),
    }),
  ]
  if (selectedTask(r.task_name) === 'other') {
    targets.push(textTarget({
      id: `${key}-custom`, label: `Custom task (${which})`, current: r.task_name,
      set: (value) => { r.task_name = value },
    }))
  }
  return targets
}

useVoiceCommands(() => [
  responsibilities.value.length
    ? buttonTarget({ id: 'add-responsibility', label: 'Add another responsibility', press: addResponsibility })
    : buttonTarget({
        id: 'add-responsibility',
        label: 'Add responsibility',
        disabled: props.members.length === 0,
        press: addResponsibility,
      }),
  ...responsibilities.value.flatMap(responsibilityTargets),
])
```

- [ ] **Step 4: Build and run the tests**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 5: Check it by hand**

In Chrome, with a plan that has members Minh and Lan:

1. **Transport:** "add private transport"; "type is van"; "vehicle name is Family Van"; "Minh can drive the family van" ticks Minh; "remove transport Family Van" asks first.
2. **Destinations:** "primary transport is family van" selects it; "primary destination name is Grandma's house"; "primary destination address", an address, then a number; "add backup arrangement"; "backup transport for backup 1, not set"; "meeting point is the front gate".
3. **Responsibilities:** "add responsibility"; "task is drive the household"; "primary person for drive the household is Minh"; "backup person is Lan".
4. On each step, commands for the other steps' fields are not understood.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/household/TransportForm.vue \
  frontend/src/components/household/ArrangementsForm.vue \
  frontend/src/components/household/ResponsibilitiesForm.vue
git commit -m "feat(frontend): voice commands for transport, destinations and responsibilities"
```

---

### Task 13: The other pages

**Files:**
- Modify: `frontend/src/views/WelcomeView.vue`
- Modify: `frontend/src/views/OverviewView.vue`
- Modify: `frontend/src/views/MapView.vue`
- Modify: `frontend/src/views/ScenarioTesterView.vue`
- Modify: `frontend/src/components/scenario/ScenarioList.vue`
- Modify: `frontend/src/components/scenario/RendezvousPanel.vue`
- Modify: `frontend/src/components/scenario/TestResultPanel.vue`
- Modify: `frontend/src/components/common/ErrorState.vue`

**Interfaces:**
- Consumes: `useVoiceCommands`, `buttonTarget` (Task 4)
- Produces: nothing new

Every file gets the same two imports, adjusted for its depth (`../voice/…` from `views/`, `../../voice/…` from `components/*/`):

```js
import { useVoiceCommands } from '../voice/registry.js'
import { buttonTarget } from '../voice/targets.js'
```

- [ ] **Step 1: Welcome**

In `frontend/src/views/WelcomeView.vue`, add `import { useRouter } from 'vue-router'` and the two voice imports, and append to `<script setup>`:

```js
const router = useRouter()

useVoiceCommands(() => (householdStore.householdId
  ? [
      buttonTarget({ id: 'continue-plan', label: 'Continue my plan', press: () => router.push('/plan') }),
      buttonTarget({ id: 'see-where-i-am', label: 'See where I am', press: () => router.push('/overview') }),
    ]
  : [buttonTarget({ id: 'start-plan', label: 'Start my plan', press: () => router.push('/plan') })]))
```

- [ ] **Step 2: Overview**

In `frontend/src/views/OverviewView.vue`, add `import { useRouter } from 'vue-router'` and the two voice imports, and append to `<script setup>`:

```js
const router = useRouter()

useVoiceCommands(() => {
  const targets = [buttonTarget({
    id: 'export-plan',
    label: 'Export preparedness plan',
    aliases: ['download my plan'],
    disabled: noSavedPlan.value || exportStatus.value === 'loading',
    press: exportPdf,
  })]
  if (noSavedPlan.value) {
    targets.push(buttonTarget({ id: 'create-plan', label: 'Create my plan', press: () => router.push('/plan') }))
  }
  return targets
})
```

- [ ] **Step 3: Fire Map**

In `frontend/src/views/MapView.vue`, add the two voice imports and append to `<script setup>`:

```js
useVoiceCommands(() => {
  const targets = []
  if (store.nearestFire) {
    targets.push(buttonTarget({
      id: 'nearest-fire', label: 'Nearest historical fire', aliases: ['show the nearest fire'],
      press: () => focusFire(store.nearestFire),
    }))
  }
  if (store.mostRecentFire) {
    targets.push(buttonTarget({
      id: 'most-recent-fire', label: 'Most recent historical fire', aliases: ['show the most recent fire'],
      press: () => focusFire(store.mostRecentFire),
    }))
  }
  return targets
})
```

- [ ] **Step 4: Scenarios, the rendezvous panel and test results**

In `frontend/src/components/scenario/ScenarioList.vue`, replace `defineProps({ scenarios: …, selectedId: … })` with `const props = defineProps({ scenarios: { type: Array, required: true }, selectedId: { type: String, default: null } })`, add the two voice imports, and append:

```js
useVoiceCommands(() => props.scenarios.map((scenario) => buttonTarget({
  id: `scenario-${scenario.scenario_id}`,
  label: `${copy[scenario.scenario_id]?.title ?? scenario.title} scenario`,
  disabled: !scenario.enabled,
  press: () => emit('select', scenario.scenario_id),
})))
```

In `frontend/src/views/ScenarioTesterView.vue`, add the two voice imports and append:

```js
useVoiceCommands(() => (scenarioStore.selectedScenarioId
  ? [buttonTarget({
      id: 'run-test',
      label: 'Run test',
      disabled: scenarioStore.testStatus === 'loading' || !selectedScenario.value?.enabled,
      press: () => scenarioStore.runTest(),
    })]
  : []))
```

In `frontend/src/components/scenario/RendezvousPanel.vue`, add the two voice imports and append:

```js
useVoiceCommands(() => {
  const targets = [buttonTarget({
    id: 'run-rendezvous',
    label: result.value ? 'Run again' : 'Run simulation',
    aliases: ['run the simulation'],
    disabled: rendezvousStore.status === 'loading',
    press: run,
  })]
  if (isReady.value && !rendezvousStore.explanation) {
    targets.push(buttonTarget({
      id: 'explain-rendezvous',
      label: 'Explain this result',
      disabled: rendezvousStore.explanationStatus === 'loading',
      press: explain,
    }))
  }
  return targets
})
```

In `frontend/src/components/scenario/TestResultPanel.vue`, add `import { useRouter } from 'vue-router'` and the two voice imports, and append:

```js
const router = useRouter()

useVoiceCommands(() => (props.result.overall_status !== 'pass'
  ? [buttonTarget({ id: 'edit-my-plan', label: 'Edit my plan', press: () => router.push(editPlanTarget(props.result)) })]
  : []))
```

- [ ] **Step 5: Retry on any error**

In `frontend/src/components/common/ErrorState.vue`, add `import { useId } from 'vue'` and the two voice imports (`../../voice/…`), and append to `<script setup>`:

```js
const voiceId = useId()
useVoiceCommands(() => [buttonTarget({ id: `retry-${voiceId}`, label: 'Retry', press: () => emit('retry') })])
```

- [ ] **Step 6: Build and run the tests**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 7: Check it by hand**

In Chrome:

1. **Home:** "start my plan" (or "continue my plan") opens My Plan.
2. **Overview:** "export preparedness plan" downloads the PDF.
3. **Fire Map:** "show the nearest fire" focuses the map on it.
4. **Test My Plan:** "primary transport unavailable scenario" selects it; "run test" runs it; "edit my plan" opens the matching step when the result is not a pass; "run simulation" and "explain this result" work on the rendezvous panel.
5. Stop the backend; on a page that shows an error, restart it and say "retry".

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/WelcomeView.vue frontend/src/views/OverviewView.vue \
  frontend/src/views/MapView.vue frontend/src/views/ScenarioTesterView.vue \
  frontend/src/components/scenario/ScenarioList.vue \
  frontend/src/components/scenario/RendezvousPanel.vue \
  frontend/src/components/scenario/TestResultPanel.vue \
  frontend/src/components/common/ErrorState.vue
git commit -m "feat(frontend): voice commands for the remaining pages"
```

---

### Task 14: Contract, privacy and the full walkthrough

**Files:**
- Modify: `docs/iteration1-integration-contract.md`
- Modify: `docs/security/privacy-requirements.md`

**Interfaces:**
- Consumes: everything above
- Produces: documentation only

- [ ] **Step 1: Document the endpoints**

In `docs/iteration1-integration-contract.md`, add two rows to the **HTTP endpoints** table, after the `GET /households/{household_id}/tests/{test_run_id}` row:

```markdown
| `POST /voice/judge` | Answer a batch of typed questions (`pick_one`, `yes_no`) about one spoken command. Every answer is one of the options offered, with a probability; anything else is refused as `503`. `422` for an oversized batch (transcript over 500 characters, over 100 questions, over 100 options). `503` when voice judging is off. Stateless. |
| `POST /voice/log` | Append one voice turn to the local JSONL turn log. Always `202 {"accepted": true}`, even when the write fails. Transcript, spoken values and value answers are removed unless `VOICE_LOG_CONTENT=true`. |
```

Append a subsection at the end of the file:

```markdown
### Voice control

The browser, not the server, knows what the current page offers. Pages register
targets (a label and the function the mouse would call); on each finished
utterance the browser sends the judge a `state` (page, step, transcript, target
labels and current values) and a batch of questions, and acts only on a target
that is still registered when the answer returns.

The judge never writes text. `APP_DATA_MODE=mock` uses a deterministic
word-overlap judge. In live data mode `APP_VOICE_MODE` is `off` (default) or
`mock`; the JEV judge is not connected yet.

Voice edits go through the same code as typed edits: they change the unsaved
draft, and the plan is stored only through Save plan, which voice always
confirms first.
```

- [ ] **Step 2: Document the data boundaries**

In `docs/security/privacy-requirements.md`:

Add to the list under **4. What must not appear in the repository or logs**:

```markdown
- Voice transcripts and spoken values, except in the local voice turn log with `VOICE_LOG_CONTENT=true`. The application logger and error messages never carry them. `logs/` is gitignored.
```

Add two rows to the table under **5. External data boundaries**:

```markdown
| Browser speech recognition (Chrome / Edge Web Speech API) | The audio of what the user says while voice control is on | High — may include names and addresses; sent by the browser to Google, not by our backend |
| Voice judge (`/voice/judge`; mock locally, JEV once connected) | The transcript, the current page's field labels and current values (member names, typed addresses) | High in combination |
```

and a note below the NVIDIA note:

```markdown
**Note on voice control.** Voice control is off until the user presses the
microphone button, and a session ends on "stop", on the button, or after 30
seconds of silence. The mock judge runs inside our backend; nothing leaves the
machine except the browser's own audio stream to its speech service. Before JEV
is connected, the payload it receives must be reviewed here, as for NVIDIA.
```

- [ ] **Step 3: Run everything**

Run: `cd backend && .venv/bin/pytest`
Expected: all pass.

Run: `cd backend && APP_DATA_MODE=mock .venv/bin/python -c "from app.main import app"`
Expected: exit 0.

Run: `cd frontend && npm test && npm run build`
Expected: all pass; build succeeds.

Run: `git status --short`
Expected: no `logs/` directory and no `.env` listed.

- [ ] **Step 4: Walk through the Epic by hand**

With the backend running as in Task 10 and a fresh household, in Chrome, one line per acceptance criterion:

- US8.1 AC1: press the button; words appear while speaking.
- US8.1 AC2: "stop", "cancel", and pressing the button each end the session; a held "Remove" is discarded.
- US8.1 AC3: in Firefox, the button is disabled with its tooltip; in Chrome with the microphone blocked, the panel says how to allow it.
- US8.2 AC1–AC4: pages by name, "go back", four scroll commands, "next step" / "previous step".
- US8.3 AC1: "add another member" presses it and says so. AC2: on Fire Map, "add member" is not understood and nothing changes.
- US8.4 AC1: "primary transport is a van". AC2: "name is Minh"; "fill in the name" then dictation. AC3: an address, then a number. AC4: an address, then "none" — the field keeps the text and shows "Address saved but not verified" after saving.
- US8.5 AC1: an ambiguous command asks first. AC2: "remove member Minh" and "save plan" always ask. AC3: gibberish gives "I didn’t catch that."
- US8.6 AC1: restart the backend with `APP_DATA_MODE=live` and no `APP_VOICE_MODE`; a command gives "Voice commands are unavailable right now." and the rest of the app works. AC2: say a command and click to another page before it lands; nothing happens on the new page.
- US8.7 AC1: `backend/logs/voice-turns.jsonl` has one line per utterance. AC2: restart without `VOICE_LOG_CONTENT`; new lines have `"transcript": null`. AC3: make `backend/logs/voice-turns.jsonl` a directory; commands still work.

- [ ] **Step 5: Commit**

```bash
git add docs/iteration1-integration-contract.md docs/security/privacy-requirements.md
git commit -m "docs: document the voice endpoints and their data boundaries"
```
