# Koala Character Implementation Plan

**Goal:** Add a koala in the bottom-right corner of every page that is the voice button and whose face (eyes, eyebrows, mouth) changes instantly as the conversation moves, using the Decisions API to read the speaker's emotion in the request that already chooses the action.

**Architecture:** `/live/decide` asks Decisions a second `choice` question (`emotion`) in the same request and returns it beside the action. A pure function in the browser turns conversation state, the speaker's emotion, the outcome and an emergency pin into one of seven faces; the voice store tracks those inputs from events it already receives and exposes `face` and `talking`. A table-driven SVG draws the koala; a button component places it, shows a speech bubble and replaces `VoiceDock`.

**Tech Stack:** FastAPI + Pydantic + httpx, pytest; Vue 3 + Pinia, inline SVG and CSS (no animation library), Node built-in test runner.

**Spec:** `docs/design/specs/2026-10-08-koala-character-design.md`

## Global Constraints

- No new npm or Python dependency.
- The koala only shows state. It never starts or stops anything except voice, and it never chooses an action.
- Faces are a closed set: `neutral`, `listening`, `thinking`, `happy`, `concerned`, `serious`, `sorry`. Emotions are a closed set: `calm`, `worried`, `urgent`, `frustrated`, `playful`. Anything unusable is `calm`.
- The face is `serious` for an emergency by rule and the model can never override it. The koala never smiles at a weather, fire, travel, simulation, plan or safety answer; `happy` is only for opening a page, scrolling or jumping to a part of a page.
- Nothing new is sent to OpenAI: the emotion question reads the same utterance, page label and read-out label. Nothing about emotion is stored or logged.
- Colour comes from the theme where it is the app's chrome; the character's own colours are fixed so it looks the same in dark mode. Motion respects `prefers-reduced-motion`.
- Meaning is never carried by animation alone: the status text is always present, errors and notices are `role="alert"`.
- `localStorage` access is wrapped in try/catch and the page works without it.
- Backend: Python, type hints, tests for every behaviour. Frontend: plain JavaScript, 2-space indent, no semicolons, single quotes, Pinia setup stores.
- Commits are Conventional Commits with a scope (`feat(backend): …`, `feat(frontend): …`, `docs: …`). A commit message holds only the change: no attribution lines and no mention of the tools used. Do not push.

## Review Focus

Failure modes the spec implies that no task's happy path exercises. Each has a pinned test in the task that owns the code.

1. **An emergency while the model labels the speaker `playful` or `calm`** must still show `serious`. Pinned in Task 7 (`the emergency pin outranks a playful reading`).
2. **A `playful` reading on a safety, fire, weather or travel request** must not make the koala smile. Pinned in Task 5 (`playful is ignored for anything that is not a page or scroll action`) and Task 7.
3. **Decisions down, refused, below 0.5 or returning a value outside the list** must give `calm` while the action still works. Pinned in Task 2.
4. **A stale delegation** must not show its reaction or outcome after a newer request has started. Pinned in Task 7 (`a stale delegation does not change the face`).
5. **A minimised koala must never hide a start error or the figures notice.** Pinned in Task 9.
6. **No `localStorage`, or one that throws (private window)** must not break the component. Pinned in Task 9.
7. **The talking flag or the emergency pin stuck on** after the session closes or the assistant goes quiet. Pinned in Task 7 (`the pin is released ...`, `closing the session clears the face`).
8. **A start failure or a not-understood request** must show `sorry`, not a smile. Pinned in Task 7.

---

### Task 0: Baseline and spec

**Files:**
- Modify: none (git only)

- [ ] **Step 1: Confirm the branch and that both suites are green**

Run:
```bash
git branch --show-current
cd backend && .venv/bin/pytest -q
cd ../frontend && npm test
```
Expected: branch `feature/voice-assistant`; backend and frontend suites pass. Note any failures here first.

- [ ] **Step 2: Commit the spec and this plan**

```bash
git add docs/design/specs/2026-10-08-koala-character-design.md docs/design/plans/2026-10-08-koala-character.md
git commit -m "docs: add the koala character design spec and implementation plan"
```

---

### Task 1: The emotion contract (backend)

**Files:**
- Modify: `backend/app/schemas/live.py`
- Modify: `backend/app/services/voice_actions.py`
- Test: `backend/tests/test_voice_emotion.py`

**Interfaces:**
- Produces (`app.schemas.live`): `Emotion = Literal["calm", "worried", "urgent", "frustrated", "playful"]`; `ActionDecision.emotion: Emotion = "calm"`.
- Produces (`app.services.voice_actions`): `EMOTIONS: dict[str, str]`, `EMOTION_INSTRUCTIONS: str`, `normalise_emotion(emotion: object, confidence: object) -> Emotion`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voice_emotion.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_voice_emotion.py -v`
Expected: FAIL with `ImportError: cannot import name 'Emotion' from 'app.schemas.live'`.

- [ ] **Step 3: Write the schema change**

In `backend/app/schemas/live.py`, add after `MAX_LABEL_LENGTH = 40`:

```python
Emotion = Literal["calm", "worried", "urgent", "frustrated", "playful"]
```

and replace the `ActionDecision` class with:

```python
class ActionDecision(BaseModel):
    """One action from the closed list, how sure the chooser was, and how the speaker sounded."""

    action: str
    confidence: float
    # Only ever changes the character's face for a moment; never what the app does.
    emotion: Emotion = "calm"
```

- [ ] **Step 4: Write the emotion list and the rule**

In `backend/app/services/voice_actions.py`, change the schema import line to:

```python
from app.schemas.live import MAX_LABEL_LENGTH, MAX_UTTERANCE_LENGTH, ActionDecision, Emotion
```

and add after the `DECISION_INSTRUCTIONS` block:

```python
EMOTIONS: Final[dict[str, str]] = {
    "calm": "The speaker sounds neutral. An ordinary request.",
    "worried": "The speaker sounds anxious, scared or unsure.",
    "urgent": "The speaker is in a hurry or sounds like they are in danger.",
    "frustrated": "The speaker sounds annoyed or impatient, including with the assistant.",
    "playful": "The speaker is joking or being friendly and light-hearted.",
}

EMOTION_INSTRUCTIONS: Final = (
    "How does the speaker sound? Choose 'calm' for an ordinary, neutral request, and "
    "whenever the wording gives no clear sign of a feeling."
)


def normalise_emotion(emotion: object, confidence: object) -> Emotion:
    """Anything outside the list, or below MIN_CONFIDENCE, is `calm`."""

    try:
        value = float(confidence)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "calm"
    if not math.isfinite(value) or value < MIN_CONFIDENCE:
        return "calm"
    if isinstance(emotion, str) and emotion in EMOTIONS:
        return emotion  # type: ignore[return-value]
    return "calm"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_voice_emotion.py tests/test_voice_actions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/live.py backend/app/services/voice_actions.py backend/tests/test_voice_emotion.py
git commit -m "feat(backend): add the emotion list and the rule that makes anything unusable calm"
```

---

### Task 2: Ask Decisions for the emotion (backend)

**Files:**
- Modify: `backend/app/providers/openai_decisions.py`
- Modify: `backend/app/providers/mock.py` (`MockActionDecisionClient`)
- Modify: `backend/tests/test_openai_decisions_provider.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `OpenAIDecisionsClient.decide(...) -> ActionDecision` whose `emotion` comes from a second question named `emotion` in the same request; `EMOTION_QUESTION = "emotion"`; `MockActionDecisionClient.decide` fills `emotion` from keywords.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_openai_decisions_provider.py`:

1. Replace the `_answer` helper with:

```python
def _answer(choice, confidence, emotion=None, emotion_confidence=0.9) -> dict:
    answers = [
        {
            "type": "choice",
            "name": "action",
            "choice": choice,
            "probabilities": [],
            "confidence": confidence,
        }
    ]
    if emotion is not None:
        answers.append(
            {
                "type": "choice",
                "name": "emotion",
                "choice": emotion,
                "probabilities": [],
                "confidence": emotion_confidence,
            }
        )
    return {"answers": answers}
```

2. Add the import `from app.services.voice_actions import ACTIONS, EMOTIONS`.

3. In `test_the_request_asks_one_choice_question_over_the_closed_list`, rename it to `test_the_request_asks_the_action_and_the_emotion_in_one_call` and replace everything from `(question,) = body["questions"]` to the end of the test with:

```python
    action, emotion = body["questions"]
    assert action["type"] == "choice"
    assert action["name"] == "action"
    assert [choice["value"] for choice in action["choices"]] == list(ACTIONS)
    assert all(choice["description"] for choice in action["choices"])
    assert emotion["type"] == "choice"
    assert emotion["name"] == "emotion"
    assert [choice["value"] for choice in emotion["choices"]] == list(EMOTIONS)
    assert all(choice["description"] for choice in emotion["choices"])
```

4. Append these tests:

```python
def _decide(payload, text="x"):
    return _client(lambda r: httpx.Response(200, json=payload)).decide(text, "overview", "")


def test_the_emotion_is_returned_with_the_action() -> None:
    decision = _decide(_answer("read_weather", 0.9, "worried", 0.8))

    assert decision.action == "read_weather"
    assert decision.emotion == "worried"


def test_no_emotion_answer_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9)).emotion == "calm"


def test_a_low_confidence_emotion_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9, "urgent", 0.3)).emotion == "calm"


def test_an_emotion_outside_the_list_is_calm() -> None:
    assert _decide(_answer("read_weather", 0.9, "furious", 0.99)).emotion == "calm"


def test_a_refused_or_wrong_type_emotion_is_calm() -> None:
    refused = {
        "answers": [
            {"type": "choice", "name": "action", "choice": "read_weather", "confidence": 0.9},
            {"type": "refusal", "name": "emotion"},
        ]
    }
    wrong_type = {
        "answers": [
            {"type": "choice", "name": "action", "choice": "read_weather", "confidence": 0.9},
            {"type": "predicate", "name": "emotion", "probability": 0.9},
        ]
    }

    assert _decide(refused).emotion == "calm"
    assert _decide(wrong_type).emotion == "calm"


def test_the_emotion_survives_when_the_action_is_not_understood() -> None:
    decision = _decide(_answer("read_weather", 0.2, "frustrated", 0.9))

    assert decision.action == "none"
    assert decision.emotion == "frustrated"


@pytest.mark.parametrize(
    ("text", "emotion"),
    [
        ("I'm really scared, should we leave?", "worried"),
        ("Hurry, I need the fire danger now", "urgent"),
        ("Ugh, this is not working", "frustrated"),
        ("Haha, take me home koala", "playful"),
        ("Show me the weather", "calm"),
    ],
)
def test_the_mock_reads_obvious_feelings(text: str, emotion: str) -> None:
    assert MockActionDecisionClient().decide(text, "overview", "").emotion == emotion
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_openai_decisions_provider.py -q`
Expected: FAIL (the request has one question; `ActionDecision` has no emotion from the client).

- [ ] **Step 3: Update the live client**

In `backend/app/providers/openai_decisions.py`:

1. Replace the `app.services.voice_actions` import block with:

```python
from app.services.voice_actions import (
    ACTIONS,
    DECISION_INSTRUCTIONS,
    EMOTION_INSTRUCTIONS,
    EMOTIONS,
    NONE_ACTION,
    decision_input,
    normalise,
    normalise_emotion,
)
```

2. Add below `ACTION_QUESTION = "action"`:

```python
EMOTION_QUESTION = "emotion"
```

3. Replace the whole `_parse` function with:

```python
def _answer_named(answers: list, name: str) -> dict | None:
    return next(
        (item for item in answers if isinstance(item, dict) and item.get("name") == name),
        None,
    )


def _parse(data: Any) -> ActionDecision:
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        raise ExternalDataUnavailable("The voice action response could not be read.")

    action = _answer_named(answers, ACTION_QUESTION)
    if action is None or action.get("type") != "choice":
        # A refusal or a missing answer means the request was not understood.
        decision = normalise(NONE_ACTION, 0.0)
    else:
        decision = normalise(action.get("choice"), action.get("confidence"))

    # The feeling is independent of the action: it only moves the character's face.
    emotion = "calm"
    feeling = _answer_named(answers, EMOTION_QUESTION)
    if feeling is not None and feeling.get("type") == "choice":
        emotion = normalise_emotion(feeling.get("choice"), feeling.get("confidence"))
    return decision.model_copy(update={"emotion": emotion})
```

4. In `decide`, replace the `"questions": [ ... ],` list in `body` with:

```python
            "questions": [
                {
                    "type": "choice",
                    "name": ACTION_QUESTION,
                    "instructions": DECISION_INSTRUCTIONS,
                    "choices": [
                        {"value": action, "description": description}
                        for action, description in ACTIONS.items()
                    ],
                },
                {
                    "type": "choice",
                    "name": EMOTION_QUESTION,
                    "instructions": EMOTION_INSTRUCTIONS,
                    "choices": [
                        {"value": emotion, "description": description}
                        for emotion, description in EMOTIONS.items()
                    ],
                },
            ],
```

- [ ] **Step 4: Update the mock**

In `backend/app/providers/mock.py`, inside `MockActionDecisionClient`, add this class attribute below `_KEYWORDS`:

```python
    _FEELINGS: tuple[tuple[str, str], ...] = (
        ("hurry", "urgent"),
        ("right now", "urgent"),
        ("quick", "urgent"),
        ("scared", "worried"),
        ("worried", "worried"),
        ("afraid", "worried"),
        ("nervous", "worried"),
        ("not working", "frustrated"),
        ("ugh", "frustrated"),
        ("annoying", "frustrated"),
        ("haha", "playful"),
        ("lol", "playful"),
        ("funny", "playful"),
    )
```

and replace the `decide` method with:

```python
    def decide(self, utterance: str, page: str, last_readout: str) -> ActionDecision:
        text = utterance.lower()
        emotion = next((feeling for word, feeling in self._FEELINGS if word in text), "calm")
        for keyword, action in self._KEYWORDS:
            if keyword in text:
                return normalise(action, 0.9).model_copy(update={"emotion": emotion})
        return normalise(NONE_ACTION, 0.0).model_copy(update={"emotion": emotion})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_openai_decisions_provider.py tests/test_voice_actions.py tests/test_voice_emotion.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/providers/openai_decisions.py backend/app/providers/mock.py backend/tests/test_openai_decisions_provider.py
git commit -m "feat(backend): ask Decisions how the speaker sounds in the same request"
```

---

### Task 3: Return the emotion from the endpoint (backend)

**Files:**
- Modify: `backend/app/services/live.py`
- Modify: `backend/tests/test_live_endpoints.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: `POST /households/{id}/live/decide` returns `{action, confidence, emotion}`; the emergency short-circuit returns `emotion: "urgent"` without calling the provider.

- [ ] **Step 1: Update the tests so they fail**

In `backend/tests/test_live_endpoints.py`:

1. In the `Decider` class, change the constructor to accept and store `emotion`:

```python
    def __init__(self, action: str = "read_weather", confidence: float = 0.9, error: Exception | None = None, emotion: str = "calm") -> None:
        self.action = action
        self.confidence = confidence
        self.error = error
        self.emotion = emotion
        self.calls: list[tuple[str, str, str]] = []
```

and its `return` line to `return ActionDecision(action=self.action, confidence=self.confidence, emotion=self.emotion)`.

2. Change the two exact-equality assertions:
   - `assert response.json() == {"action": "read_weather", "confidence": 0.9}` → `assert response.json() == {"action": "read_weather", "confidence": 0.9, "emotion": "calm"}`
   - `assert response.json() == {"action": "ask_safety_question", "confidence": 1.0}` → `assert response.json() == {"action": "ask_safety_question", "confidence": 1.0, "emotion": "urgent"}`

3. Append:

```python
def test_decide_passes_the_speakers_emotion_through(api) -> None:
    client, _, decider, household_id = api
    decider.emotion = "worried"

    response = client.post(_decide_url(household_id), json={"utterance": "When should we leave?"})

    assert response.json()["emotion"] == "worried"


def test_an_unknown_action_keeps_the_emotion(api) -> None:
    client, _, decider, household_id = api
    decider.action = "delete_plan"
    decider.emotion = "frustrated"

    response = client.post(_decide_url(household_id), json={"utterance": "delete my plan"})

    assert response.json() == {"action": "none", "confidence": 0.9, "emotion": "frustrated"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_live_endpoints.py -q`
Expected: FAIL (the response has no `emotion`; the emergency answer is calm).

- [ ] **Step 3: Update the service**

In `backend/app/services/live.py`, replace the body of `VoiceDecisionService.decide` after the emergency check with the following (keep the docstring comments), so the whole method reads:

```python
    def decide(self, household_id: str, request: DecideRequest) -> ActionDecision:
        # An emergency goes to the safety pipeline, which answers it with the fixed
        # "call 000" notice. It is decided before the limit and before the provider,
        # so an outage, a limit or a "not understood" answer can never lose it. The
        # character's face for it is set by rule, not read from a model.
        if is_emergency(request.utterance):
            return ActionDecision(action="ask_safety_question", confidence=1.0, emotion="urgent")

        if not self.rate_limit.allow(household_id):
            raise RateLimited("Too many voice requests. Please wait a minute.")

        decision = self.client.decide(request.utterance, request.page, request.last_readout)
        # Defence in depth: whatever the client returned, only a known action leaves here.
        return normalise(decision.action, decision.confidence).model_copy(
            update={"emotion": decision.emotion}
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_live_endpoints.py -q && .venv/bin/pytest -q`
Expected: PASS, and the full backend suite is green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/live.py backend/tests/test_live_endpoints.py
git commit -m "feat(backend): return how the speaker sounds from the decide endpoint"
```

---

### Task 4: Evaluate the emotion reading (backend)

**Files:**
- Modify: `backend/tests/fixtures/voice_action_cases.json`
- Modify: `backend/scripts/evaluate_voice_actions.py`
- Modify: `backend/tests/test_voice_action_cases.py`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: fixture cases with optional `emotion` and `distress`; the manual script prints emotion accuracy and exits non-zero if any `distress` case is read as `playful`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voice_action_cases.py` and add `from app.services.voice_actions import ACTIONS, EMOTIONS` (replace the existing `ACTIONS` import):

```python
def test_emotion_labels_are_real_emotions_and_distress_is_never_playful() -> None:
    labelled = [case for case in _cases() if "emotion" in case]

    assert len(labelled) >= 10
    assert all(case["emotion"] in EMOTIONS for case in labelled)
    distressed = [case for case in _cases() if case.get("distress")]
    assert len(distressed) >= 3
    assert all(case["emotion"] in ("worried", "urgent") for case in distressed)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_voice_action_cases.py -q`
Expected: FAIL (`len(labelled) >= 10` is false).

- [ ] **Step 3: Add the labelled cases**

Run this one-off to extend the fixture (it appends new cases and labels some existing ones, then rewrites the file with the same formatting):

```bash
cd backend && python3 - <<'EOF'
import json

path = "tests/fixtures/voice_action_cases.json"
data = json.load(open(path))
cases = data["cases"]

# Label a few existing, unambiguous requests as calm.
for case in cases:
    if case["text"] in (
        "Show me the weather",
        "What's the fire danger rating today?",
        "Take me to the map",
        "Go to my plan",
        "Scroll down a bit",
        "Open the fire history",
    ):
        case["emotion"] = "calm"

new = [
    ("safety", "overview", "I'm really scared, is it safe to stay here?", "ask_safety_question", "worried", True),
    ("safety", "overview", "I'm so worried about my kids, when should we leave?", "ask_safety_question", "worried", True),
    ("safety", "overview", "Please hurry, tell me when to leave right now", "ask_safety_question", "urgent", True),
    ("direct", "overview", "Hurry, I need the fire danger rating right now", "read_fire_danger", "urgent", False),
    ("direct", "overview", "Ugh, this isn't working, just open the map", "open_fire_map", "frustrated", False),
    ("direct", "overview", "Why can't you just show me the weather already", "read_weather", "frustrated", False),
    ("direct", "overview", "Haha okay koala, take me to the home page", "open_home", "playful", False),
    ("direct", "overview", "Ha, go on then, scroll down for me", "scroll_down", "playful", False),
]
start = max(c["id"] for c in cases) + 1
for i, (cat, page, text, expected, emotion, distress) in enumerate(new):
    case = {"id": start + i, "cat": cat, "page": page, "last": "none", "text": text, "expected": expected, "emotion": emotion}
    if distress:
        case["distress"] = True
    cases.append(case)

json.dump(data, open(path, "w"), indent=2, ensure_ascii=False)
open(path, "a").write("\n")
print("cases:", len(cases), "labelled:", sum(1 for c in cases if "emotion" in c))
EOF
```

Then update the total in `backend/tests/test_voice_action_cases.py`: change `== len(cases) == <old number>` to the new total printed above.

- [ ] **Step 4: Teach the script to report emotion**

In `backend/scripts/evaluate_voice_actions.py`, add this block immediately before the `times = sorted(...)` line near the end of `main`:

```python
    labelled = [row for row in rows if "emotion" in row[0]]
    if labelled:
        right = [row for row in labelled if row[1].emotion == row[0]["emotion"]]
        print(f"\nemotion: {len(right)}/{len(labelled)} = {len(right) / len(labelled):.0%}")
        for case, decision, _ in labelled:
            if decision.emotion != case["emotion"]:
                print(f"  #{case['id']:<2d} expected={case['emotion']:<10s} got={decision.emotion:<10s} {case['text'][:48]}")
        smiling = [row for row in rows if row[0].get("distress") and row[1].emotion == "playful"]
        if smiling:
            print("\nFAIL: a distressed request was read as playful:")
            for case, _, _ in smiling:
                print(f"  #{case['id']} {case['text']}")
            return 1
```

- [ ] **Step 5: Run the tests, then the live evaluation**

Run: `cd backend && .venv/bin/pytest -q`
Expected: PASS.

Run (needs the OpenAI key; load it without printing it):
```bash
cd backend && ( set -a; . "$HOME/.firebreak-spike.env"; set +a; .venv/bin/python scripts/evaluate_voice_actions.py )
```
Expected: the action results as before (0 wrong executions at 0.3, 0.5 and 0.7), an `emotion:` accuracy line, and no `FAIL`. Record the whole output. If a distressed request is read as `playful`, tighten `EMOTION_INSTRUCTIONS` and the `playful` description in `voice_actions.py`, add a test for the new wording, and re-run; do not weaken the check.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/voice_action_cases.json backend/tests/test_voice_action_cases.py backend/scripts/evaluate_voice_actions.py
git commit -m "test(backend): evaluate how well the speaker's emotion is read"
```

---

### Task 5: The face resolver and the pose table (frontend)

**Files:**
- Create: `frontend/src/voice/expression.js`
- Create: `frontend/src/voice/koalaPose.js`
- Test: `frontend/tests/voiceExpression.test.js`

**Interfaces:**
- Produces (`expression.js`): `FACES`, `EMOTIONS`, `isCheerfulAction(action)`, `reactionFace(emotion, action) -> face | null`, `outcomeFor({ action, failed }) -> 'sorry' | 'happy' | null`, `conversationFace(status) -> face`, `resolveFace({ status, emergencyPinned, outcome, reaction }) -> face`.
- Produces (`koalaPose.js`): `MOUTHS` (name to `{ d, fill }`), `POSES` (face to pose), `poseFor(face)` (falls back to `neutral`).

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/voiceExpression.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'

const {
  EMOTIONS,
  FACES,
  conversationFace,
  isCheerfulAction,
  outcomeFor,
  reactionFace,
  resolveFace,
} = await import('../src/voice/expression.js')
const { MOUTHS, POSES, poseFor } = await import('../src/voice/koalaPose.js')

test('the faces and emotions are the closed lists from the spec', () => {
  assert.deepEqual(FACES, ['neutral', 'listening', 'thinking', 'happy', 'concerned', 'serious', 'sorry'])
  assert.deepEqual(EMOTIONS, ['calm', 'worried', 'urgent', 'frustrated', 'playful'])
})

test('the conversation state picks the resting face', () => {
  assert.equal(conversationFace('idle'), 'neutral')
  assert.equal(conversationFace('closing'), 'neutral')
  assert.equal(conversationFace('error'), 'neutral')
  assert.equal(conversationFace('connecting'), 'thinking')
  assert.equal(conversationFace('checking'), 'thinking')
  assert.equal(conversationFace('listening'), 'listening')
  assert.equal(conversationFace('something-new'), 'neutral')
})

test('only opening a page, scrolling or jumping to a part of a page is cheerful', () => {
  for (const action of ['open_overview', 'open_home', 'go_back', 'scroll_down', 'scroll_to_top', 'section_fire_history']) {
    assert.equal(isCheerfulAction(action), true, action)
  }
  for (const action of ['read_weather', 'read_fire_danger', 'show_fire_history', 'ask_safety_question', 'read_simulation', 'run_simulation', 'check_travel_disruptions', 'none']) {
    assert.equal(isCheerfulAction(action), false, action)
  }
})

test('each emotion has a reaction face, except calm', () => {
  assert.equal(reactionFace('calm', 'open_home'), null)
  assert.equal(reactionFace('worried', 'read_weather'), 'concerned')
  assert.equal(reactionFace('urgent', 'read_weather'), 'serious')
  assert.equal(reactionFace('frustrated', 'read_weather'), 'sorry')
  assert.equal(reactionFace('playful', 'open_home'), 'happy')
  assert.equal(reactionFace('furious', 'open_home'), null)
  assert.equal(reactionFace(undefined, 'open_home'), null)
})

test('playful is ignored for anything that is not a page or scroll action', () => {
  for (const action of ['read_weather', 'read_fire_danger', 'ask_safety_question', 'show_fire_history', 'read_travel_routes', 'none']) {
    assert.equal(reactionFace('playful', action), null, action)
  }
})

test('an outcome is sorry when it failed, happy only for a cheerful action, otherwise nothing', () => {
  assert.equal(outcomeFor({ action: 'open_home', failed: true }), 'sorry')
  assert.equal(outcomeFor({ action: 'read_weather', failed: true }), 'sorry')
  assert.equal(outcomeFor({ action: 'open_home', failed: false }), 'happy')
  assert.equal(outcomeFor({ action: 'scroll_down', failed: false }), 'happy')
  assert.equal(outcomeFor({ action: 'read_weather', failed: false }), null)
  assert.equal(outcomeFor({ action: 'ask_safety_question', failed: false }), null)
})

test('the emergency pin outranks everything', () => {
  assert.equal(
    resolveFace({ status: 'listening', emergencyPinned: true, outcome: 'happy', reaction: 'happy' }),
    'serious',
  )
  assert.equal(resolveFace({ status: 'idle', emergencyPinned: true, outcome: 'sorry', reaction: null }), 'serious')
})

test('a failed outcome outranks a reaction, which outranks a happy outcome', () => {
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'sorry', reaction: 'happy' }), 'sorry')
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'happy', reaction: 'concerned' }), 'concerned')
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: 'happy', reaction: null }), 'happy')
})

test('with nothing else going on the conversation state decides', () => {
  assert.equal(resolveFace({ status: 'listening', emergencyPinned: false, outcome: null, reaction: null }), 'listening')
  assert.equal(resolveFace({ status: 'checking', emergencyPinned: false, outcome: null, reaction: null }), 'thinking')
  assert.equal(resolveFace({ status: 'idle', emergencyPinned: false, outcome: null, reaction: null }), 'neutral')
})

test('every face has a pose, and every pose names a mouth that exists', () => {
  for (const face of FACES) {
    const pose = POSES[face]
    assert.ok(pose, face)
    assert.ok(MOUTHS[pose.mouth], `${face} mouth ${pose.mouth}`)
    for (const key of ['eyeShape', 'eyeOpen', 'pupil', 'browLeft', 'browRight', 'mouth']) {
      assert.ok(key in pose, `${face} ${key}`)
    }
  }
})

test('the faces differ in eyes, eyebrows and mouth, as the spec requires', () => {
  const signature = (face) => JSON.stringify([POSES[face].eyeShape, POSES[face].eyeOpen, POSES[face].pupil, POSES[face].browLeft, POSES[face].browRight, POSES[face].mouth])
  const seen = new Set(FACES.map(signature))

  assert.equal(seen.size, FACES.length)
  assert.notEqual(POSES.serious.mouth, POSES.happy.mouth)
  assert.notEqual(POSES.concerned.browLeft.rot, POSES.neutral.browLeft.rot)
})

test('an unknown face falls back to neutral', () => {
  assert.equal(poseFor('nonsense'), POSES.neutral)
  assert.equal(poseFor(undefined), POSES.neutral)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && node --test tests/voiceExpression.test.js`
Expected: FAIL with `Cannot find module '../src/voice/expression.js'`.

- [ ] **Step 3: Write the resolver**

Create `frontend/src/voice/expression.js`:

```js
// Which face the koala wears. A pure function of what the voice store knows; no browser
// APIs, so every rule below is unit tested. The koala only shows state: nothing here, and
// nothing in the model's reading of the speaker, changes what the app does.

export const FACES = ['neutral', 'listening', 'thinking', 'happy', 'concerned', 'serious', 'sorry']
export const EMOTIONS = ['calm', 'worried', 'urgent', 'frustrated', 'playful']

const REACTION = { worried: 'concerned', urgent: 'serious', frustrated: 'sorry', playful: 'happy' }

// Opening a page, scrolling and jumping to a part of a page are the only requests the koala
// smiles at. It never smiles at weather, fire, travel, simulation, plan or safety answers.
const CHEERFUL = new Set([
  'open_overview',
  'open_safety_insights',
  'open_plan',
  'open_fire_map',
  'open_scenarios',
  'open_travel_readiness',
  'open_home',
  'go_back',
  'scroll_down',
  'scroll_up',
  'scroll_to_top',
  'scroll_to_bottom',
])

export const isCheerfulAction = (action) =>
  typeof action === 'string' && (CHEERFUL.has(action) || action.startsWith('section_'))

// The face for how the speaker sounds, or null for none. `playful` is only honoured where a
// smile is fitting, so a joking tone on a safety question cannot make the koala smile.
export function reactionFace(emotion, action) {
  if (emotion === 'playful' && !isCheerfulAction(action)) return null
  return REACTION[emotion] ?? null
}

// How a finished request should leave the koala: sorry if it could not help, happy only for
// a cheerful action, otherwise unchanged.
export function outcomeFor({ action, failed }) {
  if (failed) return 'sorry'
  return isCheerfulAction(action) ? 'happy' : null
}

export function conversationFace(status) {
  if (status === 'connecting' || status === 'checking') return 'thinking'
  if (status === 'listening') return 'listening'
  return 'neutral'
}

// Highest priority first: an emergency, a request that could not be helped, the speaker's
// feeling, a cheerful outcome, then the state of the conversation.
export function resolveFace({ status, emergencyPinned, outcome, reaction }) {
  if (emergencyPinned) return 'serious'
  if (outcome === 'sorry') return 'sorry'
  if (reaction) return reaction
  if (outcome === 'happy') return 'happy'
  return conversationFace(status)
}
```

- [ ] **Step 4: Write the pose table**

Create `frontend/src/voice/koalaPose.js`:

```js
// How each face sets the koala's parts. The SVG reads these numbers, so the faces are data:
// they can be checked in a test and tuned without touching the drawing.
//
//   eyeShape  'round' draws open eyes, 'happy' draws smiling arcs
//   eyeOpen   vertical scale of the open eyes (1 is normal, below 1 is narrowed)
//   pupil     [x, y] offset of the pupils inside the eyes
//   brow*     { y, rot }: vertical shift and a tilt in degrees. For the left brow a
//             negative rot lifts the inner end; the right brow mirrors it.
//   mouth     a key of MOUTHS

export const MOUTHS = {
  soft: { d: 'M52 79 Q60 85 68 79', fill: 'none' },
  small: { d: 'M55 80 Q60 83 65 80', fill: 'none' },
  side: { d: 'M53 82 Q60 79 68 83', fill: 'none' },
  wide: { d: 'M47 77 Q60 96 73 77 Z', fill: '#f08a8a' },
  down: { d: 'M51 84 Q60 76 69 84', fill: 'none' },
  flat: { d: 'M51 81 L69 81', fill: 'none' },
  smallDown: { d: 'M54 84 Q60 79 66 84', fill: 'none' },
}

export const POSES = {
  neutral: {
    eyeShape: 'round',
    eyeOpen: 1,
    pupil: [0, 0],
    browLeft: { y: 0, rot: 0 },
    browRight: { y: 0, rot: 0 },
    mouth: 'soft',
  },
  listening: {
    eyeShape: 'round',
    eyeOpen: 1.15,
    pupil: [0, -2],
    browLeft: { y: -3, rot: 0 },
    browRight: { y: -3, rot: 0 },
    mouth: 'small',
  },
  thinking: {
    eyeShape: 'round',
    eyeOpen: 0.9,
    pupil: [3, -1],
    browLeft: { y: -5, rot: -6 },
    browRight: { y: 0, rot: 0 },
    mouth: 'side',
  },
  happy: {
    eyeShape: 'happy',
    eyeOpen: 1,
    pupil: [0, 0],
    browLeft: { y: -4, rot: 0 },
    browRight: { y: -4, rot: 0 },
    mouth: 'wide',
  },
  concerned: {
    eyeShape: 'round',
    eyeOpen: 1.15,
    pupil: [0, 1],
    browLeft: { y: -2, rot: -16 },
    browRight: { y: -2, rot: 16 },
    mouth: 'down',
  },
  serious: {
    eyeShape: 'round',
    eyeOpen: 0.55,
    pupil: [0, 0],
    browLeft: { y: 2, rot: 5 },
    browRight: { y: 2, rot: -5 },
    mouth: 'flat',
  },
  sorry: {
    eyeShape: 'round',
    eyeOpen: 0.95,
    pupil: [0, 3],
    browLeft: { y: -1, rot: -14 },
    browRight: { y: -1, rot: 14 },
    mouth: 'smallDown',
  },
}

export const poseFor = (face) => POSES[face] ?? POSES.neutral
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && node --test tests/voiceExpression.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/voice/expression.js frontend/src/voice/koalaPose.js frontend/tests/voiceExpression.test.js
git commit -m "feat(frontend): add the koala face resolver and pose table"
```

---

### Task 6: Handlers report failure and emergency (frontend)

**Files:**
- Modify: `frontend/src/voice/readouts.js` (add `isShortfall`)
- Modify: `frontend/src/voice/actions.js`
- Modify: `frontend/tests/voiceReadouts.test.js`
- Modify: `frontend/tests/voiceActions.test.js`

**Interfaces:**
- Produces (`readouts.js`): `isShortfall(text) -> boolean`: true for every fixed "I can't tell you that" sentence the read-outs use.
- Produces (`actions.js`): a handler result may now carry `failed: true` (a section that is not on screen; a safety question that could not be answered) and `emergency: true` (the fixed emergency message was spoken).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/tests/voiceReadouts.test.js` (add `isShortfall` to the destructured import list from `'../src/voice/readouts.js'`):

```js
test('a sentence that says "I cannot tell you that" is recognised as a shortfall', () => {
  for (const text of [
    NEEDS_VERIFIED_ADDRESS,
    WEATHER_UNAVAILABLE,
    FIRE_DANGER_UNAVAILABLE,
    FIRE_HISTORY_UNAVAILABLE,
    COMPLETION_UNAVAILABLE,
    NO_SAVED_PLAN,
    DISRUPTIONS_UNAVAILABLE,
    NO_VERIFIED_DESTINATION,
    FDR_PATTERN_NONE,
    FDR_PATTERN_UNAVAILABLE,
    ROUTES_UNAVAILABLE,
    ROUTES_NEED_DESTINATION,
    SIMULATION_NOT_RUN,
    SIMULATION_UNAVAILABLE,
    'The simulation needs more of your plan first: Transport.',
    'The simulation cannot run yet because your plan is not complete enough.',
    'Road routes are still loading.',
  ]) {
    assert.equal(isShortfall(text), true, text)
  }
})

test('a real answer is not a shortfall', () => {
  assert.equal(isShortfall('The temperature is 21.5 degrees Celsius.'), false)
  assert.equal(isShortfall("Today's fire danger rating is High, from the official source."), false)
  assert.equal(isShortfall('Your plan is complete.'), false)
  assert.equal(isShortfall(''), false)
  assert.equal(isShortfall(undefined), false)
})
```

In `frontend/tests/voiceActions.test.js`, append:

```js
test('a section that is not on the page is reported as a failure', async () => {
  const deps = sectionDeps({ currentPath: '/scenarios' })

  const result = await createHandlers(deps).section_rendezvous({})

  assert.equal(result.failed, true)
})

test('a section that is reached is not a failure', async () => {
  const scrolls = []
  const deps = sectionDeps({ currentPath: '/map', present: { 'fire-history': anElement(scrolls) } })

  const result = await createHandlers(deps).section_fire_history({})

  assert.equal(result.failed, undefined)
})

test('the safety handler marks the emergency message as an emergency, and no-match and unavailable as failures', async () => {
  const cases = [
    ['emergency', { emergency: true }],
    ['no_match', { failed: true }],
    ['unavailable', { failed: true }],
  ]
  for (const [kind, expected] of cases) {
    const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', kind }))

    const result = await createHandlers(deps).ask_safety_question({ utterance: 'help' })

    for (const [key, value] of Object.entries(expected)) assert.equal(result[key], value, `${kind} ${key}`)
  }
})

test('a matched reviewed answer is neither a failure nor an emergency', async () => {
  const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', entryId: 'a' }))

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'When should we leave?' })

  assert.equal(result.failed, undefined)
  assert.equal(result.emergency, undefined)
})

test('a refused safety question is a failure', async () => {
  const deps = makeDeps()
  deps.safetyStore.askTyped = async () => false

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'hi' })

  assert.equal(result.failed, true)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceReadouts.test.js tests/voiceActions.test.js`
Expected: FAIL (`isShortfall` is not exported; results carry no flags).

- [ ] **Step 3: Write `isShortfall`**

Append to `frontend/src/voice/readouts.js`:

```js
// The sentences that say "I can't give you that". The koala looks sorry when it speaks one.
// Dynamic wording is matched by its fixed opening.
const SHORTFALLS = new Set([
  NEEDS_VERIFIED_ADDRESS,
  WEATHER_UNAVAILABLE,
  FIRE_DANGER_UNAVAILABLE,
  FIRE_HISTORY_UNAVAILABLE,
  COMPLETION_UNAVAILABLE,
  NO_SAVED_PLAN,
  DISRUPTIONS_UNAVAILABLE,
  NO_VERIFIED_DESTINATION,
  FDR_PATTERN_NONE,
  FDR_PATTERN_UNAVAILABLE,
  ROUTES_UNAVAILABLE,
  ROUTES_NEED_DESTINATION,
  SIMULATION_NOT_RUN,
  SIMULATION_UNAVAILABLE,
])
const SHORTFALL_OPENINGS = [
  'The simulation needs more of your plan first',
  'The simulation cannot run yet',
  'Road routes are still loading',
  'The historical fire danger pattern is still being generated',
  'The meet-up simulation is still running',
]

export function isShortfall(text) {
  if (typeof text !== 'string' || !text) return false
  return SHORTFALLS.has(text) || SHORTFALL_OPENINGS.some((opening) => text.startsWith(opening))
}
```

- [ ] **Step 4: Flag failures and emergencies in the handlers**

In `frontend/src/voice/actions.js`:

1. Replace the line `if (!element) return { spoken: SECTION_MISSING }` with:

```js
      if (!element) return { spoken: SECTION_MISSING, failed: true }
```

2. In `ask_safety_question`, replace the line `if (!sent) return { spoken: VOICE_UNAVAILABLE }` with:

```js
    if (!sent) return { spoken: VOICE_UNAVAILABLE, failed: true }
```

and replace the final `return` of that handler (`return spoken ? { label: 'safety answer', spoken } : { spoken: VOICE_UNAVAILABLE }`) with:

```js
    if (!spoken) return { spoken: VOICE_UNAVAILABLE, failed: true }
    const kinds = replies.map((reply) => reply.kind)
    const result = { label: 'safety answer', spoken }
    if (kinds.includes('emergency')) result.emergency = true
    else if (kinds.includes('no_match') || kinds.includes('unavailable')) result.failed = true
    return result
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceReadouts.test.js tests/voiceActions.test.js`
Expected: PASS. The earlier tests in these files that compare a whole result with `assert.deepEqual` for the safety handler (`{ label: 'safety answer', spoken: '...' }`) still pass for a matched answer because no flag is added.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/voice/readouts.js frontend/src/voice/actions.js frontend/tests/voiceReadouts.test.js frontend/tests/voiceActions.test.js
git commit -m "feat(frontend): let a handler say it failed or hit an emergency"
```

---

### Task 7: The voice store exposes the face (frontend)

**Files:**
- Modify: `frontend/src/stores/voice.js`
- Modify: `frontend/tests/voiceStore.test.js`

**Interfaces:**
- Consumes: Tasks 5-6; `api.decideVoiceAction` now returns `emotion`.
- Produces: `useVoiceStore()` also returns `face` (computed) and `talking` (ref); exported constants `REACTION_MS = 2000`, `OUTCOME_HOLD_MS = 4000`, `OUTCOME_FAILSAFE_MS = 10_000`, `TALK_HOLD_MS = 600`, `EMERGENCY_RELEASE_MS = 1500`, `EMERGENCY_FAILSAFE_MS = 15_000`.

- [ ] **Step 1: Write the failing tests**

In `frontend/tests/voiceStore.test.js`:

1. Extend the import of constants from `'../src/stores/voice.js'` so it also lists `EMERGENCY_FAILSAFE_MS`, `EMERGENCY_RELEASE_MS`, `OUTCOME_FAILSAFE_MS`, `OUTCOME_HOLD_MS`, `REACTION_MS`, `TALK_HOLD_MS`.

2. Append these tests:

```js
function speak(ctx, text = 'Okay.') {
  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: text })
}

test('the face follows the conversation: thinking while connecting, listening, thinking while working, neutral when closed', async () => {
  const ctx = setup()

  const starting = ctx.store.start({ router: ctx.router })
  assert.equal(ctx.store.face, 'thinking')
  await starting
  ctx.fake.emit({ type: 'session.started', session: { id: 'live_1' } })
  assert.equal(ctx.store.face, 'listening')

  say(ctx, 'Show me the weather')
  delegate(ctx)
  assert.equal(ctx.store.face, 'thinking')
  await flush()
  assert.equal(ctx.store.face, 'listening')

  ctx.fake.onClosed(null)
  assert.equal(ctx.store.face, 'neutral')
})

test('a weather answer does not make the koala smile', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'Show me the weather')
  delegate(ctx)
  await flush()
  speak(ctx)

  assert.equal(ctx.store.face, 'listening')
})

test('opening a page makes the koala smile while it speaks, then the smile fades', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'happy')
  speak(ctx)
  mock.timers.tick(OUTCOME_HOLD_MS - 1)
  assert.equal(ctx.store.face, 'happy')
  mock.timers.tick(1)

  assert.equal(ctx.store.face, 'listening')
})

test('a smile does not outlast the person speaking again', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)
  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'happy')

  say(ctx, 'And the weather')

  assert.equal(ctx.store.face, 'listening')
})

test('a smile is dropped after the failsafe even if the assistant never speaks', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)
  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()

  mock.timers.tick(OUTCOME_FAILSAFE_MS)

  assert.equal(ctx.store.face, 'listening')
})

test('a request that was not understood leaves the koala sorry', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'none', confidence: 0.9, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'hello there')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'sorry')
})

test('a failing decision service, an empty request and a thrown handler all leave the koala sorry', async () => {
  const cases = [
    async (ctx) => {
      api.decideVoiceAction = async () => {
        throw new ApiError(503, 'down')
      }
      say(ctx, 'weather')
    },
    async () => {},
    async (ctx) => {
      ctx.router.push = async () => {
        throw new Error('navigation failed')
      }
      say(ctx, 'weather')
    },
  ]
  for (const arrange of cases) {
    const ctx = setup()
    await startSession(ctx)
    await arrange(ctx)

    delegate(ctx)
    await flush()

    assert.equal(ctx.store.face, 'sorry')
  }
})

test('a start failure leaves the koala neutral, not smiling', async () => {
  const ctx = setup()
  liveTransport.open = async () => {
    throw new MicrophoneDenied()
  }

  await ctx.store.start({ router: ctx.router })

  assert.equal(ctx.store.status, 'error')
  assert.equal(ctx.store.face, 'neutral')
})

test('a handler that reports a shortfall leaves the koala sorry', async () => {
  const ctx = setup()
  ctx.localContext.location = { verification_status: 'unverified' }
  ctx.localContext.contextStatus = 'unverified'
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'What is the weather')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'sorry')
})

test('how the speaker sounds shows on the koala from the moment the decision arrives until the reply starts', async () => {
  const ctx = setup()
  let release
  api.getLocalContext = () => new Promise((resolve) => { release = () => resolve(WEATHER_CONTEXT) })
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'worried' })
  await startSession(ctx)

  say(ctx, 'What is the weather, I am worried')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'concerned')
  release()
  await flush()

  assert.equal(ctx.store.face, 'listening')
})

test('a reaction is dropped after two seconds if the reply is slow', async () => {
  const ctx = setup()
  api.getLocalContext = () => new Promise(() => {})
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'frustrated' })
  await startSession(ctx)
  say(ctx, 'Why is this so slow')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'sorry')

  mock.timers.tick(REACTION_MS)

  assert.equal(ctx.store.face, 'thinking')
})

test('a playful reading on a safety question does not make the koala smile', async () => {
  const ctx = setup()
  api.getLocalContext = () => new Promise(() => {})
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'playful' })
  await startSession(ctx)

  say(ctx, 'ha, what is the weather')
  delegate(ctx)
  await flush()

  assert.notEqual(ctx.store.face, 'happy')
})

test('the emergency pin outranks a playful reading', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)

  say(ctx, 'The fire is coming, help me')
  delegate(ctx, 'd1')
  await flush()
  assert.equal(ctx.store.face, 'serious')

  // A later, playful reading of a cheerful request cannot lift the pin while the answer is spoken.
  api.decideVoiceAction = async () => ({ action: 'open_home', confidence: 0.9, emotion: 'playful' })
  speak(ctx, 'If you are in danger, call 000 now.')
  assert.equal(ctx.store.face, 'serious')
})

test('the pin is released a moment after the emergency answer has been spoken', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()

  speak(ctx, 'If you are in danger, call 000 now.')
  mock.timers.tick(EMERGENCY_RELEASE_MS - 1)
  assert.equal(ctx.store.face, 'serious')
  mock.timers.tick(1)

  assert.notEqual(ctx.store.face, 'serious')
})

test('the pin is released by the failsafe even if the assistant never speaks', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'serious')

  mock.timers.tick(EMERGENCY_FAILSAFE_MS)

  assert.notEqual(ctx.store.face, 'serious')
})

test('an emergency reply pins the face even when the model read the speaker as calm', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 0.9, emotion: 'calm' })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)

  say(ctx, 'There is smoke and I am trapped')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'serious')
})

test('a stale delegation does not change the face', async () => {
  const ctx = setup()
  const releases = []
  api.decideVoiceAction = (householdId, body) =>
    new Promise((resolve) =>
      releases.push((answer) => resolve(answer)),
    )
  await startSession(ctx)

  say(ctx, 'first')
  delegate(ctx, 'old')
  await flush()
  say(ctx, 'second')
  delegate(ctx, 'new')
  await flush()
  releases[1]({ action: 'read_weather', confidence: 0.9, emotion: 'calm' })
  await flush()
  releases[0]({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  await flush()

  assert.notEqual(ctx.store.face, 'serious')
})

test('the talking flag follows the assistant speaking and drops shortly after', async () => {
  const ctx = setup()
  await startSession(ctx)
  assert.equal(ctx.store.talking, false)

  speak(ctx)
  assert.equal(ctx.store.talking, true)
  mock.timers.tick(TALK_HOLD_MS - 1)
  assert.equal(ctx.store.talking, true)
  mock.timers.tick(1)

  assert.equal(ctx.store.talking, false)
})

test('closing the session clears the face, the flag and any pin', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()
  speak(ctx)
  assert.equal(ctx.store.face, 'serious')
  assert.equal(ctx.store.talking, true)

  ctx.fake.onClosed(null)

  assert.equal(ctx.store.face, 'neutral')
  assert.equal(ctx.store.talking, false)
})

test('a decision without an emotion is treated as calm', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9 })
  await startSession(ctx)

  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'listening')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/voiceStore.test.js`
Expected: FAIL (`ctx.store.face` is undefined; the new constants are not exported).

- [ ] **Step 3: Add the imports, constants and state**

In `frontend/src/stores/voice.js`:

1. Change `import { ref } from 'vue'` to `import { computed, ref } from 'vue'`.
2. Add these imports after the `unexpectedNumbers` import:

```js
import { isShortfall } from '../voice/readouts.js'
import { outcomeFor, reactionFace, resolveFace } from '../voice/expression.js'
```

3. Add these constants after `TRANSCRIPT_MAX_WAIT_MS`:

```js
// How long the koala's face lingers. A reaction to how the speaker sounds shows from the
// moment the decision arrives until the reply starts (or this long); a finished request's
// smile or apology lasts while the reply is spoken and a little after; the mouth keeps moving
// a moment past the last words; an emergency pin is released shortly after its answer ends.
export const REACTION_MS = 2000
export const OUTCOME_HOLD_MS = 4000
export const OUTCOME_FAILSAFE_MS = 10_000
export const TALK_HOLD_MS = 600
export const EMERGENCY_RELEASE_MS = 1500
export const EMERGENCY_FAILSAFE_MS = 15_000
```

4. Inside the store, after `const notice = ref(null)`, add:

```js
  // What the koala shows. Only the face and the talking flag leave the store.
  const reaction = ref(null) // a face for how the speaker sounds, or null
  const outcome = ref(null) // 'sorry' | 'happy' | null
  const emergencyPinned = ref(false)
  const talking = ref(false)
  const face = computed(() =>
    resolveFace({
      status: status.value,
      emergencyPinned: emergencyPinned.value,
      outcome: outcome.value,
      reaction: reaction.value,
    }),
  )
```

5. After `let transcriptWait = null`, add:

```js
  let reactionTimer = null
  let outcomeTimer = null
  let talkTimer = null
  let pinTimer = null
  let pinFailsafeTimer = null
```

- [ ] **Step 4: Add the face helpers**

Add these functions before `resetSession` (they use only the refs and timers above):

```js
  function setReaction(next) {
    clearTimeout(reactionTimer)
    reactionTimer = null
    reaction.value = next
    if (next) {
      reactionTimer = setTimeout(() => {
        reaction.value = null
      }, REACTION_MS)
    }
  }

  function clearOutcome() {
    clearTimeout(outcomeTimer)
    outcomeTimer = null
    outcome.value = null
  }

  function setOutcome(next) {
    clearOutcome()
    outcome.value = next
    if (next) outcomeTimer = setTimeout(clearOutcome, OUTCOME_FAILSAFE_MS)
  }

  function releasePin() {
    clearTimeout(pinTimer)
    clearTimeout(pinFailsafeTimer)
    pinTimer = null
    pinFailsafeTimer = null
    emergencyPinned.value = false
  }

  function pinEmergency() {
    clearTimeout(pinTimer)
    clearTimeout(pinFailsafeTimer)
    emergencyPinned.value = true
    pinFailsafeTimer = setTimeout(releasePin, EMERGENCY_FAILSAFE_MS)
  }

  // The assistant is speaking: move the mouth, keep a finished request's face a while longer,
  // and once an emergency answer has been heard, release the pin when it goes quiet.
  function noteSpeech() {
    talking.value = true
    clearTimeout(talkTimer)
    talkTimer = setTimeout(() => {
      talking.value = false
    }, TALK_HOLD_MS)
    if (outcome.value) {
      clearTimeout(outcomeTimer)
      outcomeTimer = setTimeout(clearOutcome, OUTCOME_HOLD_MS)
    }
    if (emergencyPinned.value) {
      clearTimeout(pinTimer)
      pinTimer = setTimeout(releasePin, EMERGENCY_RELEASE_MS)
    }
  }

  // The person spoke again: a finished request's face is over, unless an emergency is pinned.
  function noteHeard() {
    if (!emergencyPinned.value) clearOutcome()
  }

  function resetFace() {
    clearTimeout(reactionTimer)
    clearTimeout(talkTimer)
    reactionTimer = null
    talkTimer = null
    clearOutcome()
    releasePin()
    reaction.value = null
    talking.value = false
  }
```

The pin is only ever released by a timer that starts when speech is heard, or by the failsafe, so the answer always gets spoken first.

- [ ] **Step 5: Wire the helpers into the store**

1. In `resetSession`, add `resetFace()` as its first line.
2. In `handleEvent`, in `case 'session.input_transcript.delta':` add `noteHeard()` as the first statement; in `case 'session.output_transcript.delta':` add `noteSpeech()` as the first statement.
3. Replace `runDelegation` with:

```js
  async function runDelegation(id) {
    latestDelegation = id
    notice.value = null
    status.value = 'checking'
    // A newer request starts clean: the previous reaction and outcome are over.
    setReaction(null)
    clearOutcome()

    const say = (content, nextOutcome = null) => {
      // A newer delegation, or a closed session, makes this result stale.
      if (latestDelegation !== id || !connection) return
      setReaction(null)
      setOutcome(nextOutcome)
      sendCommentary(id, content)
      status.value = 'listening'
    }

    try {
      await waitForTranscript()
      // Superseded or the session ended while waiting: leave the words for the newer request.
      if (latestDelegation !== id || !active) return
      const text = utterance.trim().slice(-MAX_QUESTION_LENGTH)
      utterance = ''
      delegatedSinceHeard = true
      if (!text) {
        say(VOICE_NOT_UNDERSTOOD, 'sorry')
        return
      }
      const householdId = await householdStore.ensureHousehold()
      const decision = await api.decideVoiceAction(householdId, {
        utterance: text,
        page: pageLabel(activeRouter.currentRoute.value.name),
        lastReadout: lastLabel,
      })
      if (latestDelegation !== id) return
      // How the speaker sounds shows at once, before the reply is ready. An emergency answer
      // from the server (urgent, certain) pins the serious face; the model cannot lift it.
      const emotion = decision.emotion ?? 'calm'
      setReaction(reactionFace(emotion, decision.action))
      if (decision.action === 'ask_safety_question' && emotion === 'urgent' && decision.confidence === 1) {
        pinEmergency()
      }
      const handler = decision.action === 'none' ? null : handlers[decision.action]
      if (!handler) {
        say(VOICE_NOT_UNDERSTOOD, 'sorry')
        return
      }
      const result = await handler({ utterance: text })
      if (latestDelegation !== id) return
      if (result.label) {
        lastLabel = result.label
        lastText = result.spoken
      }
      if (result.emergency) pinEmergency()
      const failed = result.failed === true || isShortfall(result.spoken)
      say(result.spoken, outcomeFor({ action: decision.action, failed }))
    } catch {
      say(VOICE_UNAVAILABLE, 'sorry')
    }
  }
```

4. Change the store's return line to `return { status, error, notice, face, talking, start, stop }`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && node --test tests/voiceStore.test.js && npm test`
Expected: PASS, and the whole frontend suite is green. If a timing test fails, fix the store, not the test: the expiry times are requirements in the spec.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/voice.js frontend/tests/voiceStore.test.js
git commit -m "feat(frontend): the voice store works out the koala's face and when it is talking"
```

---

### Task 8: The koala drawing (frontend)

**Files:**
- Create: `frontend/src/components/layout/KoalaFigure.vue`
- Test: `frontend/tests/koalaFigure.test.js`

**Interfaces:**
- Consumes: `POSES`, `MOUTHS`, `poseFor` (Task 5).
- Produces: `<KoalaFigure face="neutral" :talking="false" />`: an `aria-hidden` inline SVG (`viewBox="0 0 120 120"`) carrying `data-face` and `data-talking`, with the face set by inline styles so a static render shows the right face.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/koalaFigure.test.js`:

```js
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { importComponent } from './helpers/loadComponent.js'

const { FACES } = await import('../src/voice/expression.js')
const { MOUTHS, POSES } = await import('../src/voice/koalaPose.js')

async function render(props) {
  const KoalaFigure = await importComponent('../src/components/layout/KoalaFigure.vue')
  return renderToString(createSSRApp(KoalaFigure, props))
}

test('it is a decorative svg that carries its face and talking state as data', async () => {
  const html = await render({ face: 'concerned', talking: false })

  assert.match(html, /^<svg/)
  assert.match(html, /aria-hidden="true"/)
  assert.match(html, /viewBox="0 0 120 120"/)
  assert.match(html, /data-face="concerned"/)
  assert.match(html, /data-talking="false"/)
})

test('every face renders, and an unknown face falls back to neutral', async () => {
  for (const face of FACES) {
    assert.match(await render({ face }), new RegExp(`data-face="${face}"`), face)
  }
  assert.match(await render({ face: 'nonsense' }), /data-face="neutral"/)
})

test('the parts that change are drawn: ears, head, nose, two eyes, two eyebrows and a mouth', async () => {
  const html = await render({ face: 'neutral' })

  assert.equal((html.match(/class="ear"/g) ?? []).length, 2)
  assert.match(html, /class="head"/)
  assert.match(html, /class="nose"/)
  assert.equal((html.match(/class="eye /g) ?? []).length, 2)
  assert.equal((html.match(/class="brow /g) ?? []).length, 2)
  assert.match(html, /class="mouth/)
})

test('the eyes are narrowed for a serious face and wide for a concerned one', async () => {
  const serious = await render({ face: 'serious' })
  const concerned = await render({ face: 'concerned' })

  assert.match(serious, new RegExp(`scale\\(1, ${POSES.serious.eyeOpen}\\)`))
  assert.match(concerned, new RegExp(`scale\\(1, ${POSES.concerned.eyeOpen}\\)`))
})

test('the eyebrows tilt the way the pose says', async () => {
  const html = await render({ face: 'concerned' })

  assert.match(html, new RegExp(`rotate\\(${POSES.concerned.browLeft.rot}deg\\)`))
  assert.match(html, new RegExp(`rotate\\(${POSES.concerned.browRight.rot}deg\\)`))
})

test('a happy face draws smiling arcs instead of round eyes', async () => {
  const happy = await render({ face: 'happy' })
  const neutral = await render({ face: 'neutral' })

  assert.match(happy, /class="eye-arc/)
  assert.doesNotMatch(neutral, /class="eye-arc/)
})

test('the active mouth is the pose mouth, and the others are hidden', async () => {
  const html = await render({ face: 'happy' })

  for (const [name, shape] of Object.entries(MOUTHS)) {
    assert.ok(html.includes(`d="${shape.d}"`), name)
  }
  const active = html.match(/class="mouth active"/g) ?? []
  assert.equal(active.length, 1)
  assert.match(html, new RegExp(`class="mouth active"[^>]*d="${MOUTHS.wide.d}"`))
})

test('while talking the open mouth shows and no resting mouth is active', async () => {
  const talking = await render({ face: 'serious', talking: true })
  const quiet = await render({ face: 'serious', talking: false })

  assert.match(talking, /class="mouth-open"/)
  assert.match(talking, /data-talking="true"/)
  assert.equal((talking.match(/class="mouth active"/g) ?? []).length, 0)
  assert.doesNotMatch(quiet, /class="mouth-open"/)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && node --test tests/koalaFigure.test.js`
Expected: FAIL (the component does not exist).

- [ ] **Step 3: Write the component**

Create `frontend/src/components/layout/KoalaFigure.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { MOUTHS, POSES, poseFor } from '../../voice/koalaPose.js'

const props = defineProps({
  face: { type: String, default: 'neutral' },
  talking: { type: Boolean, default: false },
})

const pose = computed(() => poseFor(props.face))
const knownFace = computed(() => (POSES[props.face] ? props.face : 'neutral'))

// Each koala blinks on its own schedule.
const blinkDelay = `${(Math.round(Math.random() * 3000) / 1000).toFixed(1)}s`

const eyeStyle = (cx) => ({
  transform: `translate(${cx}px, 52px) scale(1, ${pose.value.eyeOpen})`,
})
const pupilStyle = computed(() => ({
  transform: `translate(${pose.value.pupil[0]}px, ${pose.value.pupil[1]}px)`,
}))
const browStyle = (brow) => ({
  transform: `translateY(${brow.y}px) rotate(${brow.rot}deg)`,
})
</script>

<template>
  <svg
    class="koala-figure"
    viewBox="0 0 120 120"
    aria-hidden="true"
    focusable="false"
    :data-face="knownFace"
    :data-talking="talking ? 'true' : 'false'"
  >
    <circle class="ear" cx="24" cy="40" r="19" />
    <circle class="ear" cx="96" cy="40" r="19" />
    <circle class="ear-inner" cx="25" cy="41" r="10" />
    <circle class="ear-inner" cx="95" cy="41" r="10" />

    <ellipse class="head" cx="60" cy="66" rx="40" ry="36" />
    <ellipse class="muzzle" cx="60" cy="76" rx="24" ry="17" />
    <ellipse class="nose" cx="60" cy="64" rx="11" ry="8.5" />
    <ellipse class="nose-shine" cx="56" cy="61" rx="3" ry="1.8" />

    <g class="blinker" :style="{ animationDelay: blinkDelay }">
      <template v-if="pose.eyeShape === 'happy'">
        <path class="eye-arc" d="M36 54 Q44 44 52 54" />
        <path class="eye-arc" d="M68 54 Q76 44 84 54" />
      </template>
      <template v-else>
        <g class="eye left" :style="eyeStyle(44)">
          <ellipse class="eye-white" cx="0" cy="0" rx="7.5" ry="8.5" />
          <g class="pupil" :style="pupilStyle">
            <circle class="pupil-dot" cx="0" cy="0" r="4" />
            <circle class="pupil-shine" cx="1.4" cy="-1.6" r="1.3" />
          </g>
        </g>
        <g class="eye right" :style="eyeStyle(76)">
          <ellipse class="eye-white" cx="0" cy="0" rx="7.5" ry="8.5" />
          <g class="pupil" :style="pupilStyle">
            <circle class="pupil-dot" cx="0" cy="0" r="4" />
            <circle class="pupil-shine" cx="1.4" cy="-1.6" r="1.3" />
          </g>
        </g>
      </template>
    </g>

    <path class="brow left" d="M36 40 L52 40" :style="browStyle(pose.browLeft)" />
    <path class="brow right" d="M68 40 L84 40" :style="browStyle(pose.browRight)" />

    <path
      v-for="(shape, name) in MOUTHS"
      :key="name"
      class="mouth"
      :class="{ active: !talking && pose.mouth === name }"
      :d="shape.d"
      :fill="shape.fill"
    />
    <ellipse v-if="talking" class="mouth-open" cx="60" cy="82" rx="7" ry="5" />
  </svg>
</template>

<style scoped>
.koala-figure {
  display: block;
  height: 100%;
  overflow: visible;
  width: 100%;
  --koala-ink: #2d3748;
  filter: drop-shadow(3px 3px 0 var(--color-shadow, rgba(45, 55, 72, 0.9)));
}
.ear { fill: #c9c5d6; stroke: var(--koala-ink); stroke-width: 3; }
.ear-inner { fill: #f8c4bb; }
.head { fill: #c9c5d6; stroke: var(--koala-ink); stroke-width: 3; }
.muzzle { fill: #e8e6ef; }
.nose { fill: #3b3748; }
.nose-shine { fill: #fff; opacity: 0.45; }
.eye-white { fill: #fff; stroke: var(--koala-ink); stroke-width: 2; }
.pupil-dot { fill: var(--koala-ink); }
.pupil-shine { fill: #fff; }
.eye-arc { fill: none; stroke: var(--koala-ink); stroke-linecap: round; stroke-width: 3.5; }
.brow { fill: none; stroke: var(--koala-ink); stroke-linecap: round; stroke-width: 3.5; transform-box: fill-box; transform-origin: center; }
.mouth { stroke: var(--koala-ink); stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; opacity: 0; }
.mouth.active { opacity: 1; }
.mouth-open { fill: #7a2e3a; stroke: var(--koala-ink); stroke-width: 2.5; transform-box: fill-box; transform-origin: center; animation: koala-talk 360ms ease-in-out infinite alternate; }

.eye, .pupil, .brow, .mouth { transition: transform 120ms ease, opacity 120ms ease; }
.blinker { transform-origin: 60px 52px; animation: koala-blink 5s ease-in-out infinite; }

@keyframes koala-blink {
  0%, 94%, 100% { transform: scaleY(1); }
  97% { transform: scaleY(0.1); }
}
@keyframes koala-talk {
  from { transform: scaleY(0.35); }
  to { transform: scaleY(1); }
}

@media (prefers-reduced-motion: reduce) {
  .blinker, .mouth-open { animation: none; }
  .mouth-open { transform: scaleY(0.7); }
  .eye, .pupil, .brow, .mouth { transition: none; }
}
</style>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && node --test tests/koalaFigure.test.js`
Expected: PASS.

- [ ] **Step 5: Look at it**

Render every face, resting and talking, onto one sheet and view the image (the sheet is written outside the repository):

```bash
SHEET="${SHEET_DIR:?set SHEET_DIR to a temporary folder outside the repository}"
mkdir -p "$SHEET"
cd frontend && node --input-type=module -e '
import { readFileSync, writeFileSync } from "node:fs"
import { createSSRApp } from "vue"
import { renderToString } from "vue/server-renderer"
import { importComponent } from "./tests/helpers/loadComponent.js"
import { FACES } from "./src/voice/expression.js"
const KoalaFigure = await importComponent("../src/components/layout/KoalaFigure.vue")
const cell = 200
// The drawing's colours live in the component's stylesheet, so carry it into the sheet. Animations
// are dropped: a still image should show each face at rest.
const css = readFileSync("src/components/layout/KoalaFigure.vue", "utf8")
  .match(/<style scoped>([\s\S]*?)<\/style>/)[1]
  .replace(/animation:[^;]+;/g, "")
let body = ""
let i = 0
for (const talking of [false, true]) {
  for (const face of FACES) {
    const svg = await renderToString(createSSRApp(KoalaFigure, { face, talking }))
    const x = (i % 7) * cell + 20
    const y = talking ? cell + 30 : 30
    body += `<g transform="translate(${x},${y})"><svg width="160" height="160" viewBox="0 0 120 120">${svg.replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")}</svg><text x="80" y="178" text-anchor="middle" font-family="sans-serif" font-size="14">${face}${talking ? " (talking)" : ""}</text></g>`
    i += 1
  }
  i = 0
}
writeFileSync(process.argv[1] + "/koala-sheet.svg", `<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="460"><style>${css}</style><rect width="100%" height="100%" fill="#fff8f5"/>${body}</svg>`)
' "$SHEET"
qlmanage -t -s 1440 -o "$SHEET" "$SHEET/koala-sheet.svg" >/dev/null 2>&1
ls "$SHEET"
```
Then open `$SHEET_DIR/koala-sheet.svg.png` with the image viewer tool. Check: the seven faces are clearly different in eyes, eyebrows and mouth; it reads as a koala (round ears, large dark nose); `serious` and `concerned` are not confusable with `happy`; the talking row shows an open mouth. Fix any proportion that looks wrong in `KoalaFigure.vue` or `koalaPose.js` (adjust the numbers, keep the tests passing), re-render and look again. Stop after at most three rounds and note anything left for the owner.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/KoalaFigure.vue frontend/tests/koalaFigure.test.js
git commit -m "feat(frontend): draw the koala"
```

---

### Task 9: The koala button, bubble and layout (frontend)

**Files:**
- Create: `frontend/src/voice/koalaControls.js`
- Create: `frontend/src/components/layout/KoalaAssistant.vue`
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Delete: `frontend/src/components/layout/VoiceDock.vue`, `frontend/tests/voiceDock.test.js`
- Test: `frontend/tests/koalaAssistant.test.js`

**Interfaces:**
- Consumes: `useVoiceStore` (`status`, `error`, `notice`, `face`, `talking`, `start`, `stop`), `KoalaFigure` (Task 8).
- Produces (`koalaControls.js`): `isLive(status)`, `isBusy(status)`, `labelFor(status)`, `bubbleFor({ supported, status, error, notice }) -> { text, role }`, `forcesOpen({ status, error, notice }) -> boolean`, `MINIMIZED_KEY = 'firebreak.koala-minimized.v1'`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/koalaAssistant.test.js`:

```js
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { afterEach, test } from 'node:test'
import { createPinia } from 'pinia'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { importComponent } from './helpers/loadComponent.js'

globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }

const { useVoiceStore } = await import('../src/stores/voice.js')
const { MINIMIZED_KEY, bubbleFor, forcesOpen, isBusy, isLive, labelFor } = await import(
  '../src/voice/koalaControls.js'
)

const hadWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const hadNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
const hadStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')

afterEach(() => {
  if (hadWindow) Object.defineProperty(globalThis, 'window', hadWindow)
  else delete globalThis.window
  if (hadNavigator) Object.defineProperty(globalThis, 'navigator', hadNavigator)
  else delete globalThis.navigator
  Object.defineProperty(globalThis, 'localStorage', hadStorage)
})

function supportMicrophone() {
  Object.defineProperty(globalThis, 'window', {
    value: { RTCPeerConnection: class {} },
    configurable: true,
    writable: true,
  })
  Object.defineProperty(globalThis, 'navigator', {
    value: { mediaDevices: { getUserMedia() {} } },
    configurable: true,
    writable: true,
  })
}

function useStorage(value) {
  Object.defineProperty(globalThis, 'localStorage', { value, configurable: true, writable: true })
}

const KEEP_STORAGE = Symbol('keep the storage the test file set up')

async function render({ status = 'idle', error = null, notice = null, talking = false, storage = KEEP_STORAGE } = {}) {
  const KoalaAssistant = await importComponent('../src/components/layout/KoalaAssistant.vue')
  const pinia = createPinia()
  // The stores read localStorage when they are created, so build them first; the storage the
  // component itself sees is swapped in just before it renders.
  const store = useVoiceStore(pinia)
  store.status = status
  store.error = error
  store.notice = notice
  if (talking) store.talking = true
  if (storage !== KEEP_STORAGE) useStorage(storage)
  const router = createRouter({ history: createMemoryHistory(), routes: [] })
  return renderToString(createSSRApp(KoalaAssistant).use(pinia).use(router))
}

// ---- pure helpers

test('live is listening or working; busy is connecting or ending', () => {
  assert.equal(isLive('listening'), true)
  assert.equal(isLive('checking'), true)
  assert.equal(isLive('idle'), false)
  assert.equal(isBusy('connecting'), true)
  assert.equal(isBusy('closing'), true)
  assert.equal(isBusy('listening'), false)
})

test('the button is named for what pressing it does', () => {
  assert.equal(labelFor('idle'), 'Talk to the assistant')
  assert.equal(labelFor('error'), 'Talk to the assistant')
  assert.equal(labelFor('listening'), 'Stop voice')
  assert.equal(labelFor('checking'), 'Stop voice')
})

test('the bubble says an error first, then the figures notice, then the status', () => {
  assert.deepEqual(bubbleFor({ supported: true, status: 'error', error: 'No mic.', notice: 'Check.' }), { text: 'No mic.', role: 'alert' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'listening', error: null, notice: 'Check.' }), { text: 'Check.', role: 'alert' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'listening', error: null, notice: null }), { text: 'Listening…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'idle', error: null, notice: null }), { text: 'Talk to me', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'connecting', error: null, notice: null }), { text: 'Connecting…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'checking', error: null, notice: null }), { text: 'Checking…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'closing', error: null, notice: null }), { text: 'Ending voice…', role: 'status' })
})

test('without microphone support the bubble says voice is not available in this browser', () => {
  assert.deepEqual(bubbleFor({ supported: false, status: 'idle', error: null, notice: null }), {
    text: "Voice isn't available in this browser.",
    role: 'status',
  })
})

test('anything that must stay visible keeps the koala open', () => {
  assert.equal(forcesOpen({ status: 'idle', error: null, notice: null }), false)
  assert.equal(forcesOpen({ status: 'listening', error: null, notice: null }), true)
  assert.equal(forcesOpen({ status: 'connecting', error: null, notice: null }), true)
  assert.equal(forcesOpen({ status: 'idle', error: 'No mic.', notice: null }), true)
  assert.equal(forcesOpen({ status: 'idle', error: null, notice: 'Check.' }), true)
})

// ---- rendering

test('the koala is a button named for its action, in the bubble it says it will talk', async () => {
  supportMicrophone()

  const html = await render()

  assert.match(html, /<button[^>]*class="koala-button"/)
  assert.match(html, /aria-label="Talk to the assistant"/)
  assert.match(html, /aria-pressed="false"/)
  assert.match(html, /Talk to me/)
  assert.match(html, /data-face="neutral"/)
})

test('while listening the button stops voice and shows the listening face', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening' })

  assert.match(html, /aria-label="Stop voice"/)
  assert.match(html, /aria-pressed="true"/)
  assert.match(html, /data-face="listening"/)
  assert.match(html, /Listening…/)
})

test('the button is disabled while connecting and while ending', async () => {
  supportMicrophone()

  for (const status of ['connecting', 'closing']) {
    assert.match(await render({ status }), /class="koala-button"[^>]*disabled/, status)
  }
})

test('a start error shows in the bubble as an alert and the button can be pressed again', async () => {
  supportMicrophone()

  const html = await render({ status: 'error', error: 'Microphone access was blocked. You can still use the chat.' })

  assert.match(html, /role="alert"[^>]*>Microphone access was blocked/)
  assert.doesNotMatch(html, /class="koala-button"[^>]*disabled/)
})

test('the figures notice is an alert in the bubble', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening', notice: 'Please check the figures on screen.' })

  assert.match(html, /role="alert"[^>]*>Please check the figures on screen\./)
})

test('without microphone support the button is disabled and says why', async () => {
  const html = await render()

  assert.match(html, /class="koala-button"[^>]*disabled/)
  assert.match(html, /Voice isn&#39;t available in this browser\./)
})

test('the koala shows the talking mouth while the assistant speaks', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening', talking: true })

  assert.match(html, /data-talking="true"/)
})

// ---- minimising

test('a stored minimised koala is a small button that brings it back', async () => {
  supportMicrophone()
  const html = await render({
    storage: { getItem: (key) => (key === MINIMIZED_KEY ? '1' : null), setItem() {}, removeItem() {} },
  })

  assert.match(html, /aria-label="Show the assistant"/)
  assert.doesNotMatch(html, /class="koala-button"/)
})

test('an open koala offers to be hidden', async () => {
  supportMicrophone()

  assert.match(await render(), /aria-label="Hide the assistant"/)
})

test('a minimised koala opens by itself while voice is on, so it can be stopped', async () => {
  supportMicrophone()
  const html = await render({
    status: 'listening',
    storage: { getItem: () => '1', setItem() {}, removeItem() {} },
  })

  assert.match(html, /class="koala-button"/)
  assert.doesNotMatch(html, /aria-label="Hide the assistant"/)
})

test('a minimised koala opens by itself to show an error or the figures notice', async () => {
  supportMicrophone()
  const storage = { getItem: () => '1', setItem() {}, removeItem() {} }

  assert.match(await render({ status: 'error', error: 'No mic.', storage }), /role="alert"[^>]*>No mic\./)
  assert.match(
    await render({ status: 'idle', notice: 'Check the figures.', storage }),
    /role="alert"[^>]*>Check the figures\./,
  )
})

test('storage that throws does not break the component', async () => {
  supportMicrophone()
  const html = await render({
    storage: {
      getItem() {
        throw new Error('blocked')
      },
      setItem() {
        throw new Error('blocked')
      },
      removeItem() {},
    },
  })

  assert.match(html, /class="koala-button"/)
})

test('missing storage does not break the component either', async () => {
  supportMicrophone()

  assert.match(await render({ storage: undefined }), /class="koala-button"/)
})

// ---- layout

test('the layout renders the koala, no longer renders the dock, and leaves room for it', async () => {
  const layout = await readFile(new URL('../src/components/layout/AppLayout.vue', import.meta.url), 'utf8')

  assert.match(layout, /import KoalaAssistant from '\.\/KoalaAssistant\.vue'/)
  assert.match(layout, /<KoalaAssistant \/>/)
  assert.doesNotMatch(layout, /VoiceDock/)
  assert.match(layout, /padding-bottom: *calc\(/)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && node --test tests/koalaAssistant.test.js`
Expected: FAIL (the modules do not exist).

- [ ] **Step 3: Write the pure helpers**

Create `frontend/src/voice/koalaControls.js`:

```js
// What the koala button and its bubble say. Pure, so the wording and the rules about what must
// stay visible are tested without a browser.

export const MINIMIZED_KEY = 'firebreak.koala-minimized.v1'

const STATUS_TEXT = {
  idle: 'Talk to me',
  connecting: 'Connecting…',
  listening: 'Listening…',
  checking: 'Checking…',
  closing: 'Ending voice…',
  error: '',
}

export const isLive = (status) => status === 'listening' || status === 'checking'
export const isBusy = (status) => status === 'connecting' || status === 'closing'

export const labelFor = (status) => (isLive(status) ? 'Stop voice' : 'Talk to the assistant')

// An error or the figures notice wins; then the lack of microphone support; then the status.
export function bubbleFor({ supported, status, error, notice }) {
  if (error) return { text: error, role: 'alert' }
  if (notice) return { text: notice, role: 'alert' }
  if (!supported) return { text: "Voice isn't available in this browser.", role: 'status' }
  return { text: STATUS_TEXT[status] ?? '', role: 'status' }
}

// The koala may be hidden only when there is nothing that must be seen or stopped: voice is
// off and there is no error or notice. Otherwise it stays (or comes back) open.
export const forcesOpen = ({ status, error, notice }) =>
  status !== 'idle' || Boolean(error) || Boolean(notice)
```

- [ ] **Step 4: Write the component**

Create `frontend/src/components/layout/KoalaAssistant.vue`:

```vue
<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useVoiceStore } from '../../stores/voice'
import { MINIMIZED_KEY, bubbleFor, forcesOpen, isBusy, isLive, labelFor } from '../../voice/koalaControls'
import KoalaFigure from './KoalaFigure.vue'

const router = useRouter()
const store = useVoiceStore()

// Where the microphone API exists (HTTPS or localhost). Elsewhere the koala stays but cannot start voice.
const supported =
  typeof window !== 'undefined' &&
  'RTCPeerConnection' in window &&
  Boolean(globalThis.navigator?.mediaDevices?.getUserMedia)

function readMinimized() {
  try {
    return globalThis.localStorage?.getItem(MINIMIZED_KEY) === '1'
  } catch {
    return false
  }
}

function saveMinimized(value) {
  try {
    globalThis.localStorage?.setItem(MINIMIZED_KEY, value ? '1' : '0')
  } catch {
    // A private window or blocked storage: the choice just is not remembered.
  }
}

const minimized = ref(readMinimized())

const mustStayOpen = computed(() => forcesOpen({ status: store.status, error: store.error, notice: store.notice }))
const showMinimized = computed(() => minimized.value && !mustStayOpen.value)
const live = computed(() => isLive(store.status))
const disabled = computed(() => !supported || isBusy(store.status))
const label = computed(() => labelFor(store.status))
const bubble = computed(() =>
  bubbleFor({ supported, status: store.status, error: store.error, notice: store.notice }),
)

function toggle() {
  if (live.value) store.stop()
  else store.start({ router })
}

function minimize() {
  minimized.value = true
  saveMinimized(true)
}

function restore() {
  minimized.value = false
  saveMinimized(false)
}
</script>

<template>
  <aside class="koala" :class="{ small: showMinimized }" aria-label="Voice assistant">
    <button v-if="showMinimized" class="koala-chip" type="button" aria-label="Show the assistant" @click="restore">
      <KoalaFigure face="neutral" :talking="false" />
    </button>

    <template v-else>
      <p
        v-if="bubble.text"
        class="koala-bubble"
        :role="bubble.role"
        :aria-live="bubble.role === 'status' ? 'polite' : undefined"
      >{{ bubble.text }}</p>
      <div class="koala-row">
        <button
          v-if="!mustStayOpen"
          class="koala-min"
          type="button"
          aria-label="Hide the assistant"
          @click="minimize"
        >
          –
        </button>
        <button
          class="koala-button"
          type="button"
          :aria-label="label"
          :aria-pressed="live ? 'true' : 'false'"
          :title="label"
          :disabled="disabled"
          @click="toggle"
        >
          <KoalaFigure :face="store.face" :talking="store.talking" />
        </button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.koala { align-items: flex-end; bottom: 1rem; display: flex; flex-direction: column; gap: 0.5rem; max-width: min(18rem, calc(100vw - 2rem)); pointer-events: none; position: fixed; right: 1rem; z-index: 6; }
.koala > * { pointer-events: auto; }
.koala-row { align-items: flex-start; display: flex; gap: 0.35rem; }
.koala-button { background: transparent; border: 0; border-radius: 50%; cursor: pointer; height: 7rem; padding: 0; width: 7rem; }
.koala-button:focus-visible, .koala-chip:focus-visible, .koala-min:focus-visible { outline: 3px solid var(--color-accent-ink, #166534); outline-offset: 3px; }
.koala-button:disabled { cursor: not-allowed; opacity: 0.7; }
.koala-chip { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 50%; box-shadow: var(--shadow-btn-sm); cursor: pointer; height: 2.75rem; padding: 0.15rem; width: 2.75rem; }
.koala-min { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 50%; color: var(--color-text); cursor: pointer; font: inherit; font-weight: 700; height: 1.75rem; line-height: 1; padding: 0; width: 1.75rem; }
.koala-bubble { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: var(--radius); box-shadow: var(--shadow-btn-sm); color: var(--color-text); font-size: 0.9375rem; font-weight: 600; margin: 0; padding: 0.45rem 0.8rem; }
.koala-bubble[role='alert'] { border-color: var(--color-accent-ink, #166534); font-weight: 700; }

@media (max-width: 640px) {
  .koala-button { height: 5rem; width: 5rem; }
}
</style>
```

- [ ] **Step 5: Swap the layout and delete the dock**

In `frontend/src/components/layout/AppLayout.vue`:

1. Replace `import VoiceDock from './VoiceDock.vue'` with `import KoalaAssistant from './KoalaAssistant.vue'`.
2. Replace `<VoiceDock />` with `<KoalaAssistant />`.
3. Leave room for the koala at the bottom of the scrolling content. In the `.content` rule replace `padding: 2rem 3rem 2.5rem; }` with `padding: 2rem 3rem 2.5rem; padding-bottom: calc(2.5rem + 7.5rem); }`.
4. In the narrow-screen rule `.content { padding: clamp(1rem, 4vw, 1.5rem); }` replace `padding: clamp(1rem, 4vw, 1.5rem); }` with `padding: clamp(1rem, 4vw, 1.5rem); padding-bottom: calc(1.5rem + 6rem); }`.

Delete the old dock and its test:
```bash
git rm frontend/src/components/layout/VoiceDock.vue frontend/tests/voiceDock.test.js
```

- [ ] **Step 6: Run the tests and the build**

Run:
```bash
cd frontend && node --test tests/koalaAssistant.test.js && npm test && npm run build
```
Expected: the koala tests pass, the whole frontend suite is green, and the build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/voice/koalaControls.js frontend/src/components/layout/KoalaAssistant.vue frontend/src/components/layout/AppLayout.vue frontend/tests/koalaAssistant.test.js
git commit -m "feat(frontend): put the koala in the corner as the voice button"
```

---

### Task 10: Documentation and a full check

**Files:**
- Modify: `docs/iteration1-integration-contract.md`
- Modify: `docs/design/specs/2026-10-08-koala-character-design.md` (status line)

- [ ] **Step 1: Document the new field**

In `docs/iteration1-integration-contract.md`, in the Voice assistant section, change the sentence describing the `/live/decide` response from `{ "action", "confidence" }` to `{ "action", "confidence", "emotion" }` and add after the sentence that lists the closed set of actions:

```markdown
`emotion` is one of `calm`, `worried`, `urgent`, `frustrated`, `playful`, read by Decisions in the same request as the action from how the speaker sounds. It only moves the on-screen character's face for a moment and never changes what the app does. It is `calm` when the answer is missing, refused, outside the list or below 0.5 confidence, and `urgent` on the emergency short-circuit (no model call).
```

- [ ] **Step 2: Update the spec status**

In `docs/design/specs/2026-10-08-koala-character-design.md`, change `**Status:** Draft for review. Not implemented.` to `**Status:** Implemented on the local branch; the motion and the drawing await the owner's review.`

- [ ] **Step 3: Run everything**

Run:
```bash
cd backend && .venv/bin/pytest -q
cd ../frontend && npm test && npm run build
```
Expected: all green.

- [ ] **Step 4: Check the commit messages carry only the change**

Run: `git log --format=%B origin/main..HEAD | grep -ci "co-authored-by"`
Expected: `0`. Also read `git log --oneline origin/main..HEAD` and confirm no message mentions the tools used to write the code.

- [ ] **Step 5: Commit**

```bash
git add docs
git commit -m "docs: document the speaker's emotion in the decide response"
```

---

### Task 11: Try it

This needs a person with a microphone. It cannot run in CI and its results are the owner's to judge.

- [ ] **Step 1: Restart the backend so it asks the second question**

Stop the running backend and start it again the same way it was started before (live data mode, in-memory repository, the OpenAI key loaded from `~/.firebreak-spike.env` without printing it). The frontend picks up the new files by itself.

- [ ] **Step 2: Check the decide endpoint returns an emotion**

```bash
H=$(curl -s -X POST http://127.0.0.1:8000/api/v1/households | python3 -c "import sys,json;print(json.load(sys.stdin)['household_id'])")
for u in "I am really scared, when should we leave" "Haha okay koala take me home" "Show me the weather"; do
  printf '%-44s -> ' "$u"
  curl -s -X POST http://127.0.0.1:8000/api/v1/households/$H/live/decide -H 'Content-Type: application/json' -d "{\"utterance\":\"$u\",\"page\":\"overview\"}"; echo
done
```
Expected: each answer carries `emotion` (a worried reading for the first, a playful one for the second, calm for the third).

- [ ] **Step 2b: Check an emergency**

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/households/$H/live/decide -H 'Content-Type: application/json' -d '{"utterance":"The fire is coming, help me!","page":"overview"}'
```
Expected: `{"action":"ask_safety_question","confidence":1.0,"emotion":"urgent"}`.

- [ ] **Step 3: Ask the owner to try it and report**

With the page reloaded, the owner checks, and the result is recorded in `docs/design/voice-assistant-smoke-results.md` under a new "Koala" heading:

| # | Do this | Pass when |
|---|---|---|
| 1 | Open any page | A koala sits bottom-right, resting; the bubble says "Talk to me" |
| 2 | Press the koala | It connects, then listens; the face changes with the conversation; pressing again stops voice |
| 3 | Say "Take me to the fire map" | It smiles while it answers, then the smile fades |
| 4 | Say "What's the weather?" | It does not smile |
| 5 | Say something worried ("I'm scared, when should we leave?") | It looks concerned as soon as you stop talking |
| 6 | Say "The fire is coming, help me" | It looks serious and stays serious until the answer has been spoken |
| 7 | Say something it cannot do ("Delete my plan") | It looks sorry |
| 8 | Hide it with the small button, reload, start voice from the chat | It stays hidden until voice is on, then opens |
| 9 | Look at the Fire Map and Travel Readiness maps | Note whether the koala covers any map control; minimise if so |
| 10 | Dark mode, and a phone-width window | The koala is readable and smaller |

State plainly which rows failed and what changed because of them.

- [ ] **Step 4: Commit the results**

```bash
git add docs/design/voice-assistant-smoke-results.md
git commit -m "docs: record how the koala behaved when tried"
```

---

## Self-review notes

**Spec coverage.** Faces, the talking flag, blink, reduced motion and speed: Tasks 5 and 8. What decides the face (the priority list, the reaction table, `playful` only for navigation): Tasks 5 and 7. The emotion question in the same request and its fallbacks: Tasks 1-3, with the live check in Task 4. Placement, button, bubble, minimise, microphone support, layout room: Task 9. Accessibility (always-present text, alert roles, `aria-pressed`, focus ring, `aria-hidden` figure): Tasks 8-9. Privacy: unchanged by design, stated in Global Constraints. Testing and the visual check: Tasks 5-9 and Task 8 step 5. Known unknowns (speech timing, how the drawing looks in both themes): Tasks 8 and 11. Out of scope items are not planned.

**Type and name consistency.** `face` values and `emotion` values are defined once (Tasks 1 and 5) and reused. `outcome` is `'sorry' | 'happy' | null` in Tasks 5 and 7. Handler results carry `failed` and `emergency` in Task 6 and are read in Task 7. The store returns `face` and `talking` in Task 7 and Task 9 reads exactly those. `MINIMIZED_KEY` is defined in `koalaControls.js` and used by the component and its tests.
