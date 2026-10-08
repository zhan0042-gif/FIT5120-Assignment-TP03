# Koala Character — Design

**Status:** Implemented on the local branch; the drawing and the motion await the owner's review.
**Branch:** `feature/voice-assistant` (local, not pushed).
**Date:** 2026-10-08
**Builds on:** `2026-10-08-voice-assistant-design.md`

## Problem

The voice assistant is a microphone button inside the safety chat. It is easy to miss,
it exists only on the Safety Insights page, and nothing shows the person that the
assistant has heard them, is working, or could not help. A friendly animated character
that reacts as the conversation happens makes the assistant feel present and makes its
state visible without reading.

## What this adds

A koala in the bottom-right corner of every page.

- It is a button: pressing it starts or stops a voice conversation from any page.
- Its face changes instantly as the conversation moves: listening, thinking, talking,
  and the outcome of what it was asked (it did it, it could not).
- The OpenAI Decisions API reads the speaker's emotion in the same request that already
  chooses the action, so the koala reacts the moment the person stops talking.
- The status line and the "check the figures" notice that `VoiceDock` showed now sit in a
  speech bubble beside the koala. `VoiceDock` is removed.

The koala never decides what the app does. It only shows state.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Character | A koala drawn as inline SVG in the app's clay style | An animal chosen later; the user's own artwork; Lottie or Rive |
| Parts that change | Eyes, eyebrows, mouth (plus a blink and a talking mouth) | Whole-body animation, outfits |
| Where it lives | Fixed bottom-right on every page, one size down on small screens | Only during a voice session; only on Safety Insights |
| Role | A button that starts and stops voice | Decoration only |
| Emotion source | Decisions reads the speaker's emotion in the existing action request | A second Decisions call on the reply; rules only |
| Reply expression | Fixed rules from the outcome | Letting the model choose the reply's tone |
| Emergencies | The face is `serious` by rule and cannot be overridden by the model | Model-chosen |
| Dependencies | None | Any animation library |
| Persistence | Minimised or not, in `localStorage` with a try/catch | Server-side |

**Why the reply face is rule-based.** The reply is a fixed template or a reviewed
answer, so its outcome is already known the instant it is chosen. Asking a model what
tone a known outcome has would add delay and a way to be wrong for no benefit. The model
is used where code cannot know: how the person sounds.

**Why emergencies are never the model's call.** A smiling animal beside a "call 000"
message is the worst failure this feature can have. Emergency wording is detected by the
same deterministic check as the rest of the voice feature, and the face is forced to
`serious` by rule.

## Faces

A closed set. Every face differs in eyes, eyebrows and mouth.

| Face | Eyes | Eyebrows | Mouth | Used for |
|---|---|---|---|---|
| `neutral` | Round, centred | Level, relaxed | Small soft smile | Voice off; closing |
| `listening` | Slightly larger, looking up | Raised a little | Small, closed | Waiting for the person |
| `thinking` | Looking to one side | One raised, one level | Small, off to one side | Connecting; working on a request |
| `happy` | Curved up (smiling eyes) | Raised | Wide smile | A page was opened, the page scrolled or a part of a page was reached |
| `concerned` | Wide | Slanted up at the inside | Small downturn | The person sounds worried |
| `serious` | Narrowed | Level and firm | Flat line | Emergencies; the person sounds urgent |
| `sorry` | Soft, looking down | Slanted up at the inside | Small downturn, tilted | Could not understand, could not do it, no data |

**Talking** is a flag, not a face, so any face can talk: the mouth opens and closes
while the assistant is speaking. The koala can therefore read the 000 notice with a
`serious` face and a moving mouth.

**Blink.** When idle the eyes blink at a random interval of 3 to 6 seconds.

**Reduced motion.** With `prefers-reduced-motion: reduce` there is no blinking and no
mouth movement; faces still change, with no transition.

**Speed.** Features change with CSS transitions of about 120 ms.

## What decides the face

Highest priority first. The first rule that applies wins.

1. **Emergency pin.** From the moment an emergency is detected until its answer has
   finished being spoken or the session closes: `serious`. The pin is released only after the
   reply has been handed to the assistant and then heard; it is held for about 0.4 s a word
   of the reply (up to 20 s), and a failsafe releases it if the assistant never speaks.
   Asking the assistant to repeat an emergency answer pins it again.
   An emergency is detected when `/live/decide` answers with the emergency
   short-circuit (emotion `urgent`, confidence 1) or when the safety answer is the fixed
   emergency message. The model cannot change this.
2. **Outcome `sorry`.** While the reply to a request that could not be understood or
   done is being spoken, and for 4 s after it ends or until the person speaks again:
   `sorry`.
3. **Reaction.** From the moment `/live/decide` returns until the reply starts being spoken
   (10 s failsafe), the face for the speaker's emotion (table below).
4. **Outcome `ok`.** While a successful reply is being spoken and for 4 s after:
   `happy` if the request was to open a page, scroll or jump to a part of a page;
   otherwise (anything that reads data or gives safety guidance) the conversation
   face below. The koala never smiles at a weather, fire, travel, simulation or safety
   answer.
5. **Conversation state.**

| Conversation state | Face |
|---|---|
| Voice off, or closing | `neutral` |
| Connecting, or a request is being worked on | `thinking` |
| Listening | `listening` |

`talking` is true while speech text is arriving from the assistant and for 600 ms after
the last piece.

### Reaction to the speaker's emotion

| Emotion | Reaction face | Note |
|---|---|---|
| `calm` | none (stay on the conversation face) | Default; also used for anything unreadable |
| `worried` | `concerned` | |
| `urgent` | `serious` | Not pinned unless it came from the emergency short-circuit |
| `frustrated` | `sorry` | The koala looks apologetic |
| `playful` | `happy` | Only for navigation, scrolling and opening pages. For every other action it is treated as `calm`, so the koala never smiles at a safety, fire, weather or travel question |

## The emotion question

`/live/decide` already asks Decisions one `choice` question named `action`. It asks a
second `choice` question named `emotion` in the same request. The two are evaluated in
parallel on the same input, so the extra question adds no round trip.

The input is unchanged (the utterance, a page label and a read-out label): nothing new is
sent to OpenAI.

| Value | Meaning (as given to the model) |
|---|---|
| `calm` | Neutral, ordinary request |
| `worried` | Anxious, scared or uncertain |
| `urgent` | In a hurry or in danger |
| `frustrated` | Annoyed or impatient, including at the assistant |
| `playful` | Joking, friendly banter |

`/live/decide` returns `{action, confidence, emotion}`. `emotion` is `calm` when the
answer is missing, refused, outside the list or below 0.5 confidence, and `urgent` on the
emergency short-circuit (no model call).

## Placement and interaction

- `position: fixed`, bottom-right, about 112 px square (80 px at 640 px wide or less),
  above page content and below dialogs. The scrollable content area gets bottom padding
  equal to the koala's height so text is never hidden behind it.
- It is a `<button>`. Pressing it starts voice when voice is off or has failed, and stops
  it when listening or working. It is disabled while connecting or closing.
- A speech bubble beside it shows, in this order of priority: a start error from the
  voice store (as an alert), the figures notice (as an alert), then a short status line
  ("Talk to me", "Connecting…", "Listening…", "Checking…", "Ending voice…").
- An alert in the bubble has a dismiss control: it clears the error or notice (a failed start
  returns to idle; a live session keeps running). A failed start shows the `sorry` face.
- A small minimise control collapses it to a 44 px circular koala head, still pressable
  to restore. The choice is stored under `firebreak.koala-minimized.v1`.
- The Fire Map and Travel Readiness maps have zoom and attribution controls in their own
  bottom-right corner. The koala may sit over them on a short screen; minimising it
  resolves that. It does not move for them.
- The microphone control in the safety chat stays. Both use the same voice store.
- Where the browser cannot capture a microphone (no HTTPS, no `getUserMedia`) the koala
  still shows but the button is disabled and the bubble says voice is not available in
  this browser.

## Accessibility

- Meaning is never carried by animation alone: the status line is always present text
  (`role="status"`), errors and notices are `role="alert"`.
- The button has an accessible name that matches its action ("Talk to the assistant",
  "Stop voice"), `aria-pressed`, and a visible focus ring.
- The SVG is `aria-hidden`; the button's label and the bubble carry the information.
- Colours come from the existing theme tokens, so dark mode works.

## Backend changes

- `ActionDecision` gains `emotion` (one of the five values, default `calm`).
- `voice_actions.py` holds the emotion list, its descriptions for the model, and a rule
  that turns anything unusable into `calm`.
- `OpenAIDecisionsClient` sends the second question and reads its answer. A missing or
  unreadable emotion answer is `calm`; an unreadable `action` answer behaves as today.
- `MockActionDecisionClient` answers `emotion` from a few keywords so tests and mock mode
  work.
- The emergency short-circuit in `VoiceDecisionService` returns `emotion: "urgent"`.
- The evaluation fixture gains an optional `emotion` and a `distress` flag; the manual
  script reports emotion accuracy and fails the run if any distressed utterance is
  labelled `playful`.

## Frontend changes

- `src/voice/expression.js`: a pure function `resolveFace({ ... })` implementing the
  priority list and the reaction table. No browser APIs, fully unit tested.
- `src/stores/voice.js`: tracks the emergency pin, the reaction, the outcome and the
  talking flag from the events it already receives, and exposes `face` and `talking`.
- `src/components/layout/KoalaFigure.vue`: the SVG, driven by `face` and `talking`.
- `src/components/layout/KoalaAssistant.vue`: the button, bubble and minimise control;
  replaces `VoiceDock.vue`, which is deleted with its tests.
- `AppLayout.vue` renders `KoalaAssistant` and reserves space for it.

## Privacy

Unchanged. The emotion question reads the same utterance already sent for the action.
No audio, transcript or emotion is stored; the emotion is used for the next few seconds
and dropped.

## Testing

- Backend: the emotion list is closed; unusable answers become `calm`; the request
  contains both questions; the parser reads both; the emergency path returns `urgent`
  without calling the provider; the mock; the evaluation fixture is valid.
- Frontend: `resolveFace` for every priority rule and every emotion, including the
  emergency pin outranking everything, `playful` ignored for non-navigation actions, and
  expiry of the reaction and the outcome; the voice store's `face` and `talking` through
  a full conversation, an emergency, a failure and a closed session; component rendering
  of every face (`data-face`) and of the talking state; the button's behaviour, labels
  and disabled states; minimise and restore; the layout renders the koala and no longer
  renders `VoiceDock`.
- Live: the evaluation against Decisions, including emotion accuracy and the rule that no
  distressed utterance is `playful`. The bar for the action is unchanged: 0 wrong
  executions at 0.5.
- Visual: every face is rendered to an image and checked by eye before it is shown.
  How the motion feels can only be judged by using it.

## Risks

- **The drawing.** A koala drawn in SVG by code may look plainer than an illustrator's.
  It is checked in rendered form and revised once on the owner's feedback.
- **Misread emotion.** A wrong emotion changes only the koala's reaction for about two
  seconds, never an action. Emergencies are by rule. A frightened person labelled
  `playful` cannot make the koala smile at a safety question.
- **Timing.** The talking flag follows the text of the assistant's speech, not its sound,
  so the mouth may lead or lag the voice by a few hundred milliseconds.
- **Covering controls.** The koala can sit over a map's corner controls on a short screen.
  Minimising is the remedy.
- **Unconfirmed voice fix.** The wait-for-transcript change in the voice store has not
  yet been confirmed by a retest with a real microphone, and the whole feature depends
  on voice working.

## Known unknowns to resolve while planning

- Whether the output-speech events arrive early enough relative to the audio for the
  talking flag to feel in step.
- The exact SVG proportions and colours that look right in both light and dark themes.

## Out of scope

- Lip-sync to the real audio level, sound effects, other characters or outfits.
- Lottie, Rive or any animation library.
- Letting the koala trigger actions other than starting and stopping voice.
- Translating the bubble text.
- Reading the emotion of the assistant's own replies with a model.
