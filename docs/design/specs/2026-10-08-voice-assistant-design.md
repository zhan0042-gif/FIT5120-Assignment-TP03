# Voice Assistant — Design

**Status:** Draft for review. Not implemented.
**Branch:** none yet (suggested: `feature/voice-assistant`, cut from `main` or from the branch that carries safety Q&A).
**Date:** 2026-10-08
**Builds on:** `2026-10-05-safety-guidance-design.md`, `2026-10-05-safety-qa-design.md`

## Problem

Safety guidance and the household's local context are reached by reading. In a
stressful moment, or for someone who finds reading slow, a spoken exchange is
easier: ask, hear the answer, and have the app open the right page without
hunting for it.

## What this adds

A microphone button in the existing safety chat. While it is on, the person talks
to a voice assistant that answers in real time. The assistant can do two things:

1. **Answer a safety question** from the reviewed CFA entries. The person hears a
   spoken answer; the reviewed text and its CFA source appear on screen.
2. **Operate the app, read-only.** "Open the fire history and read me the
   figures" navigates to the right place and reads the figures the app already
   holds.

The voice model (GPT-Live) holds the conversation. It never decides what the app
does and never supplies safety content. A separate decision step picks one action
from a fixed list; the app runs it and hands the result back to be spoken.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Voice model | GPT-Live with client delegation | Realtime API; chained speech-to-text and text-to-speech |
| Who chooses the action | OpenAI Decisions API (`gpt-6-luna`), one `choice` question over a closed list | Jev (TypeSafe); letting GPT-Live call tools itself; catalogue pasted into the prompt |
| Where the key lives | Server only; browser never sees it | Ephemeral browser key |
| Orchestration | Browser: it receives delegation events and runs handlers | Server-side sideband WebSocket |
| Safety content spoken | A reviewed entry, restated in GPT-Live's own words, with the reviewed text and source on screen | Verbatim reading (not offered by GPT-Live); free generation |
| Figures spoken | Built by code from a fixed template using store values; the same figures shown on screen | Letting the model compose figures |
| Actions | Navigate and read only | Any action that saves, edits or deletes |
| Language | English only | Vietnamese or bilingual |
| Placement | Mic button in the existing safety chat | Separate voice page; replacing the chat |
| Household data to OpenAI | None (utterance, page name, action names only) | Plan, address, member names |
| Retention | Transcripts in the browser for the visit; nothing stored server-side | Saved conversations |

**Why not Jev.** The spike (below) found both providers equally accurate on a
small set. Decisions has a documented integration with GPT-Live client
delegation and needs no second vendor, key or data path. Jev was faster by about
65 ms at p50 and reported high confidence even on an ambiguous request, which
makes its confidence less useful for deciding when to ask again.

**Why the line on safety content moves.** The existing safety Q&A never lets a
model write what the person reads. Here GPT-Live restates the reviewed entry
aloud, because its documentation says it paraphrases anything sent for it to
speak and offers no way to read text verbatim. The reviewed text stays on screen
beside the CFA source so the spoken version can always be checked against it.
This is a deliberate, accepted change from the earlier design, not an oversight.

## Evidence from the spike

A throwaway script ran 39 hand-written English requests (10 direct, 10
paraphrased, 5 safety, 5 context-dependent, 9 that must be refused) against both
providers, twice each, with the same 14-action list.

| | Decisions | Jev |
|---|---|---|
| Correct | 39/39 | 39/39 |
| Wrong executions at confidence 0.3, 0.5, 0.7 | 0 | 0 |
| Latency of the decision step, p50 / p95 | 357 / 491 ms | 291 / 410 ms |
| Confidence on "Open it" (should be refused) | 0.45 | 0.81–0.83 |

Limits: the cases were written by the same person who wrote the actions and were
easy; they are single-turn, typed rather than transcribed from speech, and
English. Latency covers the decision step only, not the full path from speech to
spoken answer. These numbers do not show the providers are equal, only that
neither failed on this set.

## Architecture

```text
Browser mic/speaker  <--WebRTC-->  GPT-Live
Browser <--data channel "oai-events"--> GPT-Live   (transcripts, delegation events)

Browser --POST /api/v1/households/{id}/live/sessions--> Backend --POST /v1/live/sessions--> OpenAI   (create session)
Browser --POST /api/v1/households/{id}/live/decide----> Backend --POST /v1/decisions------> OpenAI   (choose action)
Browser --POST /api/v1/households/{id}/safety-guidance/ask--> existing pipeline       (safety questions)
```

### Backend (new)

- `LiveSessionClient` Protocol in `providers/interfaces.py`, a live client, a mock
  and a disabled client, wired in both `build_external_providers` and
  `dependencies.py`. A missing key yields the disabled client; the app still
  starts and the mic button reports voice as unavailable.
- `POST /api/v1/households/{household_id}/live/sessions`: receives the browser's
  SDP offer, creates the session with configuration held only on the server
  (conversation prompt, `delegation.type: "client"`, English), returns the session
  id and SDP answer. Both live endpoints are scoped to an existing household, like
  the safety `ask` endpoint, because they spend a paid quota and there is no login.
- `ActionDecisionClient` Protocol with a Decisions client, mock and disabled
  client. `POST /api/v1/households/{household_id}/live/decide` takes the
  utterance, the current page label and the last read-out label, and returns
  `{action, confidence}`. Any value not in the closed list, any refusal and
  confidence below 0.5 becomes `none`. A provider failure is a 503, and the
  browser then speaks the fixed unavailable line.
- The action list and its descriptions live in one backend module. The browser
  keeps a handler registry keyed by action id and treats any id it has no handler
  for as `none`, so a mismatch between the two lists fails safe. A backend test
  pins the list, and a frontend test pins the registry to the same ids.

### Frontend (new)

- A voice store (Pinia, setup style) owning connection state, the current
  utterance and the current delegation id.
- A voice controller that opens the peer connection, joins
  `session.input_transcript.delta` events into the current utterance, and on
  `session.delegation.created` saves the id, calls `/live/decide`, runs the
  handler, and sends the outcome with `session.commentary.append`.
- A handler per action. A handler returns a structured result (`ok`,
  `unavailable`, `not_applicable`) and the text for GPT-Live to speak; it also
  pushes the matching message into the safety chat or navigates.
- A microphone button and state indicator in the safety chat panel.

### Data flow for one request

1. The person speaks; transcript deltas accumulate.
2. GPT-Live emits `session.delegation.created`. The event carries no text, only
   the delegation id; the utterance comes from the transcript.
3. The controller calls `/live/decide`. Below confidence 0.5 the action is
   treated as `none`.
4. The handler runs. For `ask_safety_question` it calls the existing `ask`
   endpoint, which performs the emergency check, routing, catalogue validation
   and rate limiting unchanged.
5. The result is sent with `session.commentary.append` (500 tokens at most);
   GPT-Live restates it aloud. The screen shows the reviewed text with its
   source, or the figures read out.
6. If a newer delegation has started, results for the older one are dropped.

## Actions

| Action | Effect |
|---|---|
| `open_overview`, `open_plan`, `open_fire_map`, `open_scenarios`, `open_travel_readiness` | Navigate to that page |
| `show_fire_history` | Go to the fire map and read the historical fire counts held by the fire map store |
| `read_weather` | Go to the overview and read current observations |
| `read_fire_danger` | Go to the overview and read today's official Fire Danger Rating |
| `read_plan_completion` | Go to the overview and read how complete the saved plan is |
| `check_travel_disruptions` | Go to Travel Readiness (where the disruptions panel is), run the road disruption check and read the outcome |
| `ask_safety_question` | Go to the overview and run the safety Q&A pipeline |

Every read action first navigates to the page that displays the same figures, so
what is spoken is also on screen.
| `repeat_last` | Say the last read-out again |
| `go_back` | Navigate back |
| `open_home` | Open the home page |
| `scroll_down`, `scroll_up` | Scroll the page by about four fifths of what is visible; say so at either end |
| `scroll_to_top`, `scroll_to_bottom` | Go to either end of the page |
| `section_<id>` (12) | Open the section's page and scroll to its named part (`backend/app/content/voice_sections.json`); say so if it is not on screen |
| `none` | Do nothing; GPT-Live asks the person to rephrase |

## Reading figures aloud

- Each read handler builds its sentence from a fixed template and the store's
  values, and states `unavailable` or `not_applicable` exactly as the app holds
  them (for example, fire history needs a verified household location).
- Nothing is rounded, estimated or described as a prediction. Context such as
  fire history is context only.
- The figures sent for speaking are shown on screen at the same time.
- After speaking, the app compares numbers in `session.output_transcript.delta`
  with the numbers it sent. On a mismatch it shows "Please check the figures on
  screen." This detects an error after it has been spoken; it cannot prevent one.

## Emergencies

The existing emergency check runs before routing for safety questions and is not
bypassed. It also runs first inside `/live/decide`: an utterance with emergency
wording is answered `ask_safety_question` with confidence 1 without calling
Decisions and without spending the `decide` limit, so an emergency is never lost
to a "not understood" answer, a provider outage or a rate limit. An emergency
utterance receives a fixed on-screen notice directing the
person to call 000 and a fixed sentence for GPT-Live to say. GPT-Live is
instructed to delegate every safety-related request and never to answer safety
content itself; how reliably it complies is an open risk (see Risks).

## Error handling

- Decisions slow or failing: the assistant says a fixed line ("I couldn't do that
  just now; the buttons still work") and the chat is unaffected.
- Session creation fails or microphone permission is denied: the mic button shows
  the reason; text chat keeps working.
- Interruption: only the newest delegation is acted on; stale results are dropped.
- Connection drops: the voice state resets to idle; chat history in the browser is
  kept.

## Limits, cost and configuration

- GPT-Live has no maximum-duration or idle setting, so the browser ends the
  session itself by sending `session.close` after 60 seconds without speech and at
  10 minutes in total. Voice is billed per second; Decisions input is $0.10 per
  million tokens with no output charge.
- Two new in-process limiters, separate from the safety `ask` limiter (each
  safety question already spends one `ask` unit after one `decide` unit): session
  creation allows 3 per household and 20 overall per minute and answers 429 when
  exceeded; `decide` allows 20 per household and 120 overall per minute and also
  answers 429.
- New environment variable `OPENAI_API_KEY`, passed through `docker-compose.yml`
  and documented in `.env.example` with a placeholder. `APP_DATA_MODE=mock`
  selects the mock clients; a missing key selects the disabled clients.

## Privacy

- Audio travels from the browser to OpenAI. The first time the mic is used the app
  says so.
- The backend never logs utterances; they can contain names or addresses.
- Decisions input is the utterance, a page name and a read-out label. No plan,
  address or member data is sent.
- Zero Data Retention is not assumed.

## Testing

- Backend: mock-provider tests for session creation and `/live/decide`; a test
  that any action outside the closed list becomes `none`; the existing safety
  tests stay unchanged.
- Frontend (`node --test`): store and controller tests using a fake data channel
  and a swapped `api` object, restored in `afterEach`, covering stale delegations,
  low confidence, unavailable data and number-mismatch warnings.
- Evaluation: the 39 spike cases move into the repository as a fixture and are run
  by hand against the live API. They are not part of CI.
- Manual, with a real microphone: an emergency phrase, an interruption mid-answer,
  a figure read-out checked against the screen, and a noisy-environment request.

## Risks

- **GPT-Live may answer a safety question itself without delegating.** Mitigation
  is prompt instruction plus measurement during the manual tests; there is no
  technical block.
- **Paraphrase may alter a figure or a caveat.** Mitigation is templated figures,
  on-screen text, and the after-the-fact number check.
- **Decisions is in public beta** and currently offers one model. Behaviour or
  pricing may change before general availability.
- **Real speech is harder than typed text.** The spike did not test transcription
  errors.

## Known unknowns to resolve while planning

- The exact session configuration fields for the conversation prompt, taken from
  the GPT-Live prompting and session guides, which have not yet been read.
- Whether GPT-Live exposes a reliable "speaking" signal and audio level, needed
  only if a character animation is added later.
- Whether the project's OpenAI account qualifies for Zero Data Retention.

## Out of scope

- An animated character with changing expressions (a separate feature, to be
  designed on its own).
- Any action that saves, edits or deletes household data.
- Vietnamese or other languages.
- Route-intersection analysis for road disruptions.
- Multi-turn context beyond the current utterance and the last read-out label.
- Replacing the typed-question router with Decisions.
