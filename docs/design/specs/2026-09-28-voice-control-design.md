# Voice Control — Design

**Status:** approved design, not yet implemented
**Branch:** `experiment/sandbox`, off `main` at `1e4cf7f`. Local experiment first.
**Date:** 2026-09-28
**Epic:** Epic 8: Voice Control (US8.1–US8.7)

## Problem

Building a household plan means a long run of small form interactions: seven
sections, repeated member and animal rows, dropdowns, an address autocomplete.
For a user who finds a mouse and keyboard hard, or who simply has their hands
full, that is the barrier between intending to plan and having a plan.

## What this adds

One floating microphone button on every page. The user presses it, speaks, sees
the words appear as they talk, and the app performs the command: open a page, go
back, scroll, press a named button, choose a dropdown option, fill a field, enter
an address.

**The app only ever performs actions it has declared.** Nothing reads the page
and improvises. Every command resolves to one entry in a registry that the
current page publishes, and a judgement engine picks which entry the user meant.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| How commands are understood | Command registry: pages declare actions; a model picks one | A generic agent that reads the DOM and decides what to click; an LLM |
| Judgement engine | JEV | An LLM (slower, costs per output token, can write text we would have to police) |
| Speech-to-text | Chrome's Web Speech API behind an adapter | A paid streaming STT service, for now |
| Where JEV is called | Through the backend | Directly from the browser |
| Free-text values | Candidate spans picked by JEV, falling back to dictation | Dictation only; spans only |
| First version | Navigation, buttons, form filling, safety and errors | One utterance performing several actions; spoken questions about data |
| Logging | Every turn to a local JSONL file, personal content off by default | No logging; a MySQL table |

**Command registry over a DOM agent.** A registry is fast, predictable,
testable, and cannot be talked into doing something the page never offered. The
cost is that a command works only if someone declared it. That trade is the
point: in an evacuation-planning tool, a feature that does fewer things reliably
beats one that does everything plausibly.

**JEV.** JEV is a judgement engine, not a writer. It takes a structured `state`
and a batch of small typed questions — yes/no, pick one, score — and answers the
whole batch in one request in a few hundred milliseconds, with a probability for
each answer. Output costs nothing. It never produces text, so there is no prose
to validate: it can only choose among options we supplied. It does not do
speech-to-text.

**Web Speech API.** Free, keyless, and returns interim words almost instantly,
which is what makes the button feel live. It works well only in Chrome and Edge,
and Chrome sends the audio to Google's servers. Both are acceptable for a local
experiment; the adapter exists so production can choose differently without
touching anything else.

**Backend proxy.** JEV's credential must never reach the browser. The extra hop
costs nothing measurable on localhost, and it gives logging a natural home.

**Free-text values.** JEV can say *which* field the user meant but cannot write
"Minh" or "12 Smith Street". See [Free-text values](#free-text-values).

**Logging.** Requested explicitly, and it is also the only way to learn how
often JEV picks correctly and where the thresholds should sit. See
[Logging](#logging).

## Architecture

```
🎤 ─► STT adapter ─► final transcript ─► questions.js ─► POST /voice/judge ─► JEV
                                              ▲                                 │
                                              │ registry of the current page    ▼
       executor ◄──── decision ◄──── policy.js ◄──────── answers + probabilities
          │
          └─► POST /voice/log (fire and forget)
```

The registry lives in the **frontend**, because only the frontend knows which
fields, options and buttons the current page has. The backend does two things:
forward the question batch to JEV with the credential attached, and write the
log.

### Registry entries carry handlers

Each registered target carries the function that performs it. Forms already bind
through `defineModel` and mutate reactive objects directly
(`member.display_name`, `member.relationship`), so a handler is one line:

```js
useVoiceCommands(() => members.value.map((member, index) => textTarget({
  id: `member-${member.member_id}-name`,
  label: `Name (${member.display_name.trim() || `member ${index + 1}`})`,
  current: member.display_name,
  set: (value) => { member.display_name = value },
})))
```

The executor never touches the DOM to fill a field. It calls the target's
`run`. This keeps voice edits on exactly the same path as typed edits — the
detached draft, the dirty comparison against the saved plan, validation and
saving are all untouched — and it makes the executor testable without a DOM.

The registry is **read on demand, not kept reactive**. Components register a
getter; when a transcript is final, the store calls every getter once and gets a
fresh snapshot. Nothing re-renders because a label changed.

### Target kinds

| Kind | Command phrase offered to JEV | Examples |
|---|---|---|
| `page` | `go to <label>` | Home, My Plan, Overview, Fire Map, Test My Plan |
| `command` | `<label>` verbatim | go back, scroll down, scroll to the top, People section |
| `button` | `press <label>`, plus any aliases | Add another member, Continue (next step), Remove member Minh, Save plan |
| `select` | `set <label>` | Relationship to household (Minh), Primary transport |
| `text` | `fill in <label>` | Name (member 2), Vehicle name (transport 1) |
| `checkbox` | `tick or untick <label>` | Has limited mobility (Minh), Lan can drive (transport 1) |
| `address` | `enter the address for <label>` | Primary destination address |

Every target has `id`, `kind`, `label` and `run`. Buttons may carry
`confirm: true` and `disabled`. Selects carry `options`; text, select and
checkbox targets carry `current`; address targets add `suggestions()` and
`choose(index)`. Shared helpers in `voice/targets.js` build each kind, so a
select's option labels map back to their stored values in one place.

Labels name the row by the member's name when there is one ("Remove member
Minh"), falling back to position ("member 2"), because that is how people talk.
Duplicate phrases are disambiguated by appending a number.

`AppLayout` registers the global targets, present on every page: the five pages,
`go back`, and four scroll commands. The app scrolls inside `main.content`, not
the window — the layout fixes the page height and hides window overflow — so the
scroll commands hold a reference to that element.

Dropdown options come from the same constants the templates render, so the
options JEV chooses among can never drift from the options on screen.
`TransportForm` currently writes its type options inline; they move into a
constant for this reason.

### Only what the user can see is registered

`PlanBuilderView` renders all five sections at once and hides four with
`v-show`. A naive registry would let "name is Minh" fill a field on a hidden
section. A `VoiceScope` component wraps each section and provides whether it is
active; `useVoiceCommands` injects that and returns no targets while inactive.
Scopes nest, so a component inside an inactive scope is inactive however deep it
sits. Leaving a page unregisters its targets on unmount.

Page context travels the same way: `AppLayout` provides the route name and
`PlanBuilderView` the current step, through `useVoiceContext`.

### Frontend units

| File | Responsibility |
|---|---|
| `components/voice/VoiceButton.vue` | Floating button and the small panel: interim words, what was done, confirmation prompts, numbered address suggestions. Mounted once in `AppLayout`. |
| `stores/voice.js` | Session state machine: `idle → listening → judging → (confirming \| dictating \| choosing) → executing → listening` |
| `voice/stt.js` | Adapter: `start`, `stop`, `onInterim`, `onFinal`, `onError`. A Web Speech implementation and a fake for tests. |
| `voice/registry.js` | Register getters and read snapshots; `useVoiceCommands(getTargets)`, `useVoiceContext(getContext)`. |
| `voice/targets.js` | Pure. Builders for each target kind. |
| `components/voice/VoiceScope.vue` | Provides whether its section is active. |
| `voice/questions.js` | Pure. Registry snapshot + transcript + mode → catalogue of command phrases, `state` and question batch. |
| `voice/policy.js` | Pure. Answers → one decision. |
| `voice/executor.js` | Runs an action through the target's `run`, after re-checking the target is still registered and enabled. |
| `api/client.js` | `judgeVoiceCommand()` and `logVoiceTurn()`, through the existing `ApiError` normalisation. |

Components that register targets: `AppLayout`, `WelcomeView`, `PlanBuilderView`
and the four forms in `components/household/`, `AddressAutocompleteInput`,
`OverviewView`, `MapView`, `ScenarioTesterView`, `ScenarioList`,
`RendezvousPanel`, `TestResultPanel`. Each is independent work.

### Backend units

| File | Responsibility |
|---|---|
| `providers/interfaces.py` | `JudgementClient` Protocol: `judge(state, questions) -> list[Answer]` |
| `providers/jev_judgement.py` | `DisabledJudgementClient`: raises `ExternalDataUnavailable`, and the app still starts. The live JEV client joins it once JEV's documentation arrives, in a follow-up plan. Same layout as `nvidia_explanation.py`. |
| `providers/mock.py` | `MockJudgementClient`: deterministic word-overlap matching, so the whole feature runs keyless and offline |
| `schemas/voice.py` | Request, answer and log-record models, with size limits |
| `services/voice.py` | Call the judgement client; validate the answers against the questions asked |
| `services/voice_log.py` | Append one JSONL record per turn; redact per configuration |
| `api/routes/voice.py` | `POST /api/v1/voice/judge`, `POST /api/v1/voice/log` |

Selection follows the explanation client: a `_judgement_client()` helper in
`core/config.py`, a field on `ExternalProviders`, and `get_judgement_client` in
`core/dependencies.py`. `APP_DATA_MODE=mock` always uses the mock. In live data
mode a separate `APP_VOICE_MODE` chooses: `mock` or `off` (the default). This is
what lets the experiment run against live TomTom addresses with a mock judge
before JEV is connected; `jev` becomes a third value in the follow-up.

No new dependencies, frontend or backend.

## One turn

A **session** starts when the button is pressed and ends when it is pressed
again, when the user says "stop" or "cancel", or after 30 seconds of silence.
Ending a session always discards any held action.
Within a session each finished utterance is one **turn**.

1. STT emits interim words. The panel shows them. **Interim words never reach
   JEV.**
2. STT emits a final transcript. If it is exactly "stop" or "cancel", the
   session ends here, before any request.
3. `questions.js` builds the state and the question batch from the registry.
4. One `POST /voice/judge`. JEV answers the whole batch.
5. `policy.js` turns the answers into a decision.
6. The executor runs it, or the store enters a waiting mode.
7. One `POST /voice/log` with the complete turn record, not awaited.

### The question batch

For *"primary transport is a van"* on the arrangements section:

```js
state: {
  page: 'plan-builder',
  step: 'destinations',
  mode: 'normal',
  transcript: 'primary transport is a van',
  targets: [/* id, kind, label, current value — no handlers */],
}

questions: [
  { id: 'command', type: 'pick_one', options: ['go to Overview', 'go back', 'scroll down', 'set Primary transport', 'fill in Primary destination name', /* … */, 'none of these'] },
  { id: 'option:primary-transport', type: 'pick_one', options: ['Not set', 'Family car: Car / SUV', 'Van'] },
  { id: 'option:backup-1-transport', type: 'pick_one', options: [/* … */] },
  { id: 'span',    type: 'pick_one', options: ['primary', 'primary transport', 'a van', 'van', /* … */, '(none)'] },
  { id: 'checked', type: 'yes_no' },
  { id: 'stop',    type: 'yes_no' },
]
```

**One question picks the command.** Each registered target becomes one command
phrase (see [Target kinds](#target-kinds)), and `command` asks which phrase the
user meant, with `none of these` as the way out. Choosing the phrase chooses both
the kind of action and its target at once.

**Every dependent question is asked up front.** An `option:` question is asked
for every select on the step, although only the one `command` names will be used.
Output is free and the batch is one request, so asking speculatively costs almost
nothing — and it means **every command costs exactly one JEV call**, never two.
This is what keeps a turn under two seconds.

v1 uses `pick_one` and `yes_no` only. `score` has no use yet.

The batch depends on the mode:

| Mode | Questions |
|---|---|
| `normal` | `command`, one `option:<target id>` per select, `span`, `checked`, `stop` |
| `confirming` | `confirm` (yes/no), `stop` |
| `choosing` | `suggestion` (pick one of the numbered suggestions or `none`), `stop` |

Dictation sends nothing: the next utterance is the value.

### Decisions

A decision's confidence is the **lowest** probability among the answers it
depends on: `command`, and the value answer (`option:`, `span` or `checked`)
where there is one.

| Decision | When | What happens |
|---|---|---|
| `execute` | confidence ≥ 0.85, target not marked `confirm` | Perform it. Panel shows "✓ Set Primary transport to Van". |
| `confirm` | 0.5 ≤ confidence < 0.85, **or** target marked `confirm` (Remove, Save) at confidence ≥ 0.5, **or** a `text` value that would replace something already typed | Hold the action. Panel asks "Set Primary transport to Van? Say yes or no." The next turn is `confirming`. Yes at ≥ 0.85 performs it; no at ≥ 0.5 drops it; anything else asks once more, then drops it. |
| `dictate` | a `text` command whose `span` is `(none)` or below 0.85, with `command` ≥ 0.5; **always** for `address` | Panel asks "What should I enter for Name (member 2)?". The next transcript is written verbatim through `run`. No JEV call. |
| `choose` | after an address has been dictated | See [Addresses](#addresses) |
| `reject` | confidence < 0.5, or `command` is `none of these` | "I didn't catch that." Nothing changes. |
| `stop` | `stop` answered yes at ≥ 0.5 | The session ends. |

The overwrite rule exists because rows look alike. With members "Minh" and an
unnamed second member, "name is Lan" matches `fill in Name (Minh)` at least as
well as `fill in Name (member 2)`. Filling an empty field on a wrong guess costs a
retype; silently renaming Minh costs the plan.

The thresholds are starting values. The log exists to replace them with measured
ones.

### Free-text values

`questions.js` splits the transcript into every contiguous run of up to eight
words and offers them, plus `(none)`, as the `span` question. In "name is Minh"
JEV picks `Minh`. If it is unsure, or the value is not in the utterance at all
("fill in the name"), the turn falls through to dictation and the next utterance
is taken as the value, exactly as heard.

### Addresses

Addresses are always dictated, never extracted: they are long, and one misheard
word sends the user to a different street.

1. "Primary destination" → `dictate`.
2. The user says the address. `run` puts it in the field exactly as heard,
   which triggers the component's existing suggestion lookup.
3. The store waits up to 3 seconds for suggestions. The panel lists them,
   numbered, and asks "Say a number, or none". Each option reads like
   `1 first: 12 Smith St, Ballarat VIC 3350`, so "the first one" and "number
   one" both have words to match.
4. The next turn is `choosing`. A `suggestion` answer at ≥ 0.85 goes to
   `choose`, which calls the component's own `select`, so coordinates and
   verification follow the normal path. Anything less asks once more.

JEV decides only **which number the user said**. It never judges which address is
right. "None", or no suggestions within 3 seconds, leaves the text as entered and
the location unverified — the same outcome as typing an address and not picking a
suggestion. Nothing is invented.

### Stop always wins

"Stop" and "cancel" are matched on the exact transcript in the browser before any
request, so they work even when JEV is down. Every batch also carries the `stop`
yes/no for other phrasings ("never mind", "forget it"). Pressing the button always
ends the session and discards any held action.

### Timing

- One turn is in flight at a time. A transcript arriving meanwhile is queued, and
  only the newest is kept. A stop phrase is never queued; it acts immediately.
- The executor re-checks that the target is still registered before acting,
  because the user may have clicked elsewhere while JEV answered. If it is gone:
  "That's no longer on this page."
- From the end of speech to the action, expect roughly 1–1.5 s. Most of it is the
  STT deciding the user has finished, not JEV.

## Errors

A voice failure must never break the rest of the app, and an action is never
performed in part.

| Layer | Failure | Handling |
|---|---|---|
| Browser | No Web Speech support | Button disabled with "Voice control needs Chrome or Edge" |
| | Microphone blocked | "Microphone blocked — allow it in your browser settings"; session ends |
| STT | `no-speech` | Restart silently within the session |
| | `network` | Message; session ends |
| Backend | Voice judging switched off (`APP_VOICE_MODE=off`) | `DisabledJudgementClient` → 503 → "Voice commands are unavailable right now" |
| | JEV timeout (2 s) or HTTP error (follow-up plan) | `ExternalDataUnavailable` → 503 |
| | Malformed answers: missing ids, unknown options, probability outside 0–1 | 503. Nothing executes. |
| | Transcript over 500 characters, over 100 questions, over 100 options in one question | 422 |
| Session | Two failed turns in a row | Session ends |
| Executor | Target gone, option not offered, button disabled | Nothing happens; the reason is shown; logged as `fail` |
| Logging | `/voice/log` fails, or the file cannot be written | Ignored. The user never sees it. |

The backend validates JEV's answers against the questions it was sent. An answer
naming an option that was not offered is treated as malformed, not trusted.

## Logging

One record per turn, appended to a JSONL file on the backend:

```json
{"ts": "2026-09-28T10:14:03Z", "turn_id": "vt_…", "page": "plan-builder", "step": "destinations",
 "mode": "normal", "transcript": "primary transport is a van",
 "answers": [{"id": "command", "answer": "primary-transport", "probability": 0.94},
             {"id": "option:primary-transport", "answer": "Van", "probability": 0.97}],
 "decision": "execute", "action": {"kind": "select", "target": "primary-transport", "value": "Van"},
 "outcome": "ok", "latency_ms": {"judge": 240, "turn": 310}}
```

The browser writes the `command` answer and `action.target` as the **target
id**, not the spoken phrase, because phrases can contain member names ("Remove
member Minh") while ids cannot.

Transcripts contain member names and home addresses. This repository treats that
as data it does not write down: the explanation feature never logs its passages,
and `docs/security/privacy-requirements.md` describes the same stance. The user
has asked for logging anyway, and the log is the only route to measuring
accuracy, so both apply:

| Setting | Default | Effect |
|---|---|---|
| `VOICE_LOG_PATH` | `logs/voice-turns.jsonl` (gitignored) | Where records go |
| `VOICE_LOG_CONTENT` | `false` | When false, `transcript` and `action.value` are removed, and every answer other than `command`, `checked`, `confirm` and `stop` keeps its probability but loses its text |

Redaction happens **on the backend**, so a browser cannot opt itself out of it.
For local experimenting, set `VOICE_LOG_CONTENT=true` in `.env`. The standard
application logger and error messages never include request bodies, so an
ordinary exception cannot leak an address.

## API

```
POST /api/v1/voice/judge
body:     { state, questions }
200:      { answers: [{ id, answer, probability }] }
422:      oversized or invalid batch
503:      JEV disabled, unreachable, or answered malformed

POST /api/v1/voice/log
body:     one turn record
202:      { accepted: true }, including when the write fails
```

The log endpoint answers `202` with a small JSON body rather than `204`, because
the frontend's single HTTP boundary parses every successful response as JSON.

Neither endpoint is household-scoped, reads the plan, or stores anything besides
the log line. The plan changes only through the page's own save.

## Testing

`node --test` for the frontend and `pytest` for the backend, as now. No new test
tooling.

**Frontend**

| File | Covers |
|---|---|
| `voiceRegistry.test.js` | Register and unregister; snapshots call getters fresh; inactive scopes contribute nothing; context merges |
| `voiceTargets.test.js` | Each builder; select labels map back to values; duplicate option labels are numbered |
| `voiceQuestions.test.js` | One command phrase per target, duplicates numbered; an `option:` question for every select; spans up to eight words plus `(none)`; `stop` always present; confirming and choosing batches; handlers never appear in `state` |
| `voicePolicy.test.js` | Exactly 0.85 executes, exactly 0.5 confirms; `confirm` targets confirm at 0.99; low span dictates; addresses always dictate; a missing answer rejects; confidence is the minimum of the answers used |
| `voiceExecutor.test.js` | Calls the right `run` with the right value; refuses a target that is gone, disabled, or given an option it does not offer |
| `voiceStt.test.js` | With a fake recognition class: interim and final results; silent restart on `no-speech` and when Chrome ends the session; `not-allowed` reported |
| `voiceStore.test.js` | With fake STT and swapped `api` methods: stop pre-empts; the queue keeps only the newest; yes/no confirmation; dictation writes verbatim; address choose and `none`; two failures end the session; exactly one log per turn |

Handlers are plain functions, so none of this needs a DOM. The components'
registrations and the real browser are checked by hand.

**Backend**

| File | Covers |
|---|---|
| `test_voice_judgement.py` | Mock client: deterministic, picks the option sharing the most words, probabilities within 0–1; provider selection by `APP_DATA_MODE` and `APP_VOICE_MODE` |
| `test_voice_endpoint.py` | Mock answers pass through; 422 on each size limit; 503 when disabled; 503 on an answer naming an option not offered, a missing answer, or an out-of-range probability |
| `test_voice_log.py` | Writes one JSONL line; redacts content when `VOICE_LOG_CONTENT=false`; a failed write does not raise; the endpoint answers 202 |

The live JEV client's tests arrive with it, using `httpx.MockTransport` like
`test_tomtom_routing_provider.py`.

**By hand.** A checklist with one line per scenario in US8.1–US8.6, run in Chrome
on localhost.

**Accuracy.** Once JEV is connected: replay logged transcripts, measure how often
the chosen target and value were right per page and per kind, and move the
thresholds accordingly.

## Documentation changes

- `docs/iteration1-integration-contract.md`: the two voice endpoints.
- `docs/security/privacy-requirements.md`: audio sent to Google by Web Speech;
  transcripts sent to JEV; the log and its redaction setting.
- `.env.example`: `APP_VOICE_MODE`, `VOICE_LOG_PATH`, `VOICE_LOG_CONTENT`. JEV's
  own settings arrive with the live client.
- `.gitignore`: `logs/`, so turn logs are never committed.

## Open until JEV's documentation arrives

Everything above can be built and tested today against `MockJudgementClient`.
These depend on JEV's actual interface and belong only in `jev_judgement.py`:

- Endpoint, authentication, and environment variable names.
- Exact request shape for `state` and typed questions.
- Whether `pick_one` returns a probability for every option or only the top one.
  v1 needs only the top one.
- Batch and option-count limits, which may tighten the 422 limits above.

## Out of scope

- One utterance performing several actions ("add Lan, my mother, at work during
  the day").
- Spoken questions about data ("what's the fire danger today?").
- Speaking responses aloud. The mic is open during a session, so the app's own
  voice would be transcribed as a command. Prompts appear in the panel instead.
- Map gestures on the Fire Map (pan, zoom). The page itself can be opened and
  scrolled.
- The home-address editor on Overview (`LocalContextCard`). The rest of Overview
  is covered.
- STT outside Chrome and Edge, and languages other than English.
- Deployment. This is a local experiment on `experiment/sandbox`.
