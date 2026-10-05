# Safety Q&A — Design

**Status:** Phase 1 and Phase 2 implemented. Phase 2 is on `feature/safety-qa-phase-2`; the routing model comparison and decision are recorded in `safety-qa-router-evaluation.md`.
**Branch:** `feature/safety-guidance` (builds on, and reshapes, the safety guidance already on it)
**Date:** 2026-10-05
**Builds on:** `2026-10-05-safety-guidance-design.md`

## Problem

Safety guidance currently renders as a list of cards, each a paragraph or more.
Opening the section means facing a wall of text, and people skip walls of text.
The content is right and reviewed; the presentation is the problem.

## What this adds

The safety section becomes a chat box with a few suggested questions. Tapping a
question, or typing one, shows a short reviewed answer with its CFA source. There
is no long list of answers: every other reviewed question sits behind a "More
questions" button, so each answer is reached by asking for it.

Two kinds of question reach it:

- **Suggested questions** are buttons. They need no model, no network call, and
  work when the AI provider is down.
- **Typed questions** are matched to a reviewed answer by a model.

**The model chooses; it never writes.** For a typed question the model is given
the list of reviewed questions and returns only the *ids* of the best matches. The
text shown to the user is always a reviewed answer, word for word. The model has
no way to put a sentence of its own in front of a user, so it cannot invent
bushfire advice. The worst it can do is pick the wrong reviewed answer, and the
user then reads correct advice that answers a neighbouring question.

This is the same line the rest of the product holds: nothing fabricated, nothing
worded as prediction.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Who writes the answer shown | The team, reviewed | The model, from retrieved text |
| What the model does | Classifies a typed question to reviewed ids | Generates prose; retrieves passages |
| Suggested questions | Buttons answered locally | Every question sent to the model |
| Household data sent to the model | None | Plan, address, member names |
| Chat memory | None: each question stands alone | Multi-turn context |
| Chat history | Held in the browser for the visit, never stored | Saved on the server |
| Long guidance list | Removed; remaining questions are buttons behind "More questions" | A collapsed "Read all guidance" list |
| Delivery | Two phases, each its own plan | One large change |

**Why not generated answers.** A model that writes the answer can distort it while
still citing the right page: drop a caveat, merge two pages, add a reassurance.
The existing gates check numbers, a speculation word list, pronouns and length;
none can tell that a sentence of safety advice has been changed. A larger paid
model writes fewer such errors but not none, and one error in evacuation advice
is one too many. Generation is deferred, not forbidden: it would need a gate that
proves each claim against a source, which does not exist.

**Why a model at all.** The long-text problem is solved by the interface, not by
AI. A model earns its place where the interface cannot: understanding that "what
about my dog?" and "can I take my pet with me?" both mean the same reviewed answer.

## Phases

- **Phase 1, no model.** Restructure the content into short question-and-answer
  entries. Replace the card panel with the chat panel, suggested question buttons,
  fixed notices, and a "More questions" button. This alone removes the wall of text
  and ships without any provider.
- **Phase 2, model routing.** Add the typed-question box, the router provider, the
  `ask` endpoint, the emergency pre-check, and the evaluation set that chooses the
  model.

Phase 1 must be complete and shippable before Phase 2 starts.

## Content

`backend/app/content/safety_guidance.json` is reshaped from long cards to short
entries. Each of the seven existing cards is split into one or more entries, about
twelve in all. There is still one file and one review.

| Field | Meaning |
|---|---|
| `id` | Stable slug, unique |
| `question` | The canonical question the entry answers; shown on its button |
| `asked_as` | Optional list of alternative phrasings, used only to help the router; never shown |
| `answer` | The reviewed answer, plain prose, at most 600 characters |
| `source_name` | Publisher shown to the user, e.g. `CFA` |
| `source_url` | Page the answer was written from, `https://`, required |
| `retrieved_on` | Date a person checked it against that page, required |
| `reviewed_by` | Team member who checked it; `null` until then |
| `applies_when` | Conditions used to choose which questions are *suggested* |

`applies_when` keeps the six condition keys and the strict validation from the
earlier spec. Its meaning changes: it no longer decides whether an answer may be
given. A household with no pets can still ask about pets. It only decides which
questions are offered as buttons, so a household is offered the questions that
fit its plan first.

`asked_as` is introduced in Phase 2, where the router first uses it; Phase 1 entries do
not carry it.

Entries are written in the team's own words, not copied from CFA, and an entry
with `reviewed_by: null` is never served. The file is validated when the app
starts, and the app fails at import if it is invalid, as before.

### Proposed first entries

Answers are drafted from the five CFA pages already read; each still needs a
second team member's check against the live page.

| Question | Source page (cfa.vic.gov.au/fire-safety/your-fire-plan/…) | Suggested when |
|---|---|---|
| When should I leave on a high-risk day? | `when-to-leave` | everyone |
| Why is leaving late so dangerous? | `when-to-leave` | everyone |
| What if it is too late to leave? | `when-to-leave` | everyone |
| Should I stay and defend my home? | `when-to-leave` | everyone |
| What should I put in an emergency kit? | `what-to-take-with-you` | everyone |
| What should I pack for children? | `what-to-take-with-you` | `has_dependants` |
| What about my pets? | `pets-and-bushfires` | `has_pets` |
| What should a pet kit include? | `pets-and-bushfires` | `has_pets` |
| Can I take my pet to a relief centre? | `pets-and-bushfires` | `has_pets` |
| Someone in my household needs extra help to move. How do we plan? | `when-to-leave`, `planning-with-people-who-need-extra-support` | `has_mobility_support` |
| How do I get my property ready before the season? | `preparing-for-bushfire-season` | `in_bushfire_prone_area` |
| What should I do around my home on Extreme or Catastrophic days? | `preparing-for-bushfire-season` | `in_bushfire_prone_area` |

The "extra help" row draws on two pages. An entry has one `source_url`; where two
pages contribute, the entry is split so each answer rests on one page.

## Backend, Phase 1

`GET /api/v1/households/{household_id}/safety-guidance` changes shape. The earlier
`cards` list is replaced; the feature is not on `main`, so nothing depends on the
old shape.

```
{
  "entries": [ { id, question, answer, source_name, source_url, retrieved_on } ],
  "suggested_ids": [ "..." ],
  "location_conditions_applied": true
}
```

- `entries` is every reviewed entry, in file order, regardless of the household.
  The set is small, so the browser answers a tapped question locally with no
  further request.
- `suggested_ids` is at most six ids: first up to four entries tailored to the
  household (a non-empty `applies_when` that holds), in file order, then the
  general entries (empty `applies_when`) in file order, up to six in total. The
  household's own questions come first but cannot crowd out the general ones, such
  as when to leave. General entries always qualify, so the box never opens nearly
  empty.
- `location_conditions_applied` keeps its earlier meaning and rules: a missing or
  unverified location, or a failed spatial lookup, leaves `in_bushfire_prone_area`
  entries out of `suggested_ids` and sets the flag to `false`. The condition is
  never guessed.
- Unknown household is `404`. A household with no plan receives the general
  suggestions. The route does not write to the plan and calls no model.

## Frontend, Phase 1

- `components/overview/SafetyChatPanel.vue` replaces `SafetyGuidancePanel.vue`.
- A Pinia store holds the entries, the suggested ids, and the chat messages for the
  visit. Messages are never sent to the server and are lost on reload.
- Layout: title, one line of introduction, the fixed notice, the suggested question
  buttons, then the conversation. A tapped question appears as the user's message
  and the reviewed answer appears beneath it with "Source: CFA · checked against the
  source page on <date>" as a link, and the existing six-month stale note.
- Below the suggested questions, a "More questions" button (collapsed by default)
  reveals every reviewed question that is not already suggested, as further
  buttons, so every entry can be reached. The store derives these as the entries
  whose id is not in `suggested_ids`; the backend response is unchanged. There is
  no list of full answers: an answer, its source and its date are shown when its
  question is asked.
- **Fixed notice**, always visible: not for emergencies; if you are in danger call
  000. This text lives in the frontend, not the content file, so an unreviewed
  content file can never hide it. The team checks its wording against an official
  source when the change is reviewed.
- All fixed bubbles (no match, emergency, unavailable) are frontend constants, never
  model output.

## Backend, Phase 2

### The `ask` endpoint

`POST /api/v1/households/{household_id}/safety-guidance/ask` with
`{ "question": "..." }`.

- The question is trimmed. Empty, or longer than 300 characters, is `422`. Unknown
  household is `404`. The household id scopes the route only: nothing about the
  household reaches the model.
- It returns `200` with an answer status, as the rendezvous routes do:

| `status` | Meaning | `entry_ids` |
|---|---|---|
| `matched` | One or two reviewed entries answer the question | 1 or 2 ids |
| `no_match` | Nothing reviewed fits, or the question asks for a prediction or a decision | empty |
| `emergency` | The question looks like someone in danger | empty |
| `unavailable` | The model could not be reached, or no key is configured | empty |

The browser shows the entry text from the `entries` it already holds.

### Order of checks

1. **Emergency pre-check**, deterministic. A small list of phrases ("on fire", "fire
   is coming", "trapped", "can't breathe", "triple zero", "000" and similar)
   matched case-insensitively. A hit returns `emergency` and the model is **not
   called**. The list can never be complete, so it is a second line behind the
   fixed notice, and it is English only; both are stated limits.
2. **Router.** The model is called with the question and the catalogue.
3. **Gates**, applied to what the router returns, in order: keep only ids that are in
   the catalogue; remove duplicates; keep at most two. Nothing left is `no_match`. A
   malformed router reply is treated as `no_match`, never as `matched`.

### Router provider

Follows the existing provider pattern: a Protocol, a live client, a mock and wiring.

- `GuidanceRouter` Protocol in `providers/interfaces.py`:
  `route(question, catalogue) -> list[str]`, raising `ExternalDataUnavailable` on
  failure. `catalogue` is a list of `(id, question, asked_as)`.
- `NvidiaGuidanceRouter`, live: plain `httpx` against the same hosted chat endpoint
  as the explanation client, with the model reasoning switched off, and a model name
  that is a constructor argument with a module default, so the evaluation can swap
  it.
- `MockGuidanceRouter`: deterministic word-overlap matching, used by tests and mock
  mode.
- `DisabledGuidanceRouter`: raises `ExternalDataUnavailable`. A missing `AI_API_KEY`
  yields this rather than stopping the app, as for the explanation client.
- Wired in `build_external_providers` and `dependencies.py`.

### What the model is told and sees

- It is told to answer with a JSON list of ids only, to choose at most two, to
  return an empty list when nothing fits, and to return an empty list for any
  question that asks what will happen, whether to leave, or what to do about a
  specific fire. It is told the question is untrusted text and any instruction in it
  is to be ignored.
- It receives the question and the catalogue only. No member name, address, plan
  field, or household id.
- Its reply is parsed as JSON and used only as a list of ids. Any other text in it is
  discarded unread. A question that tries to override the instructions can at worst
  change which reviewed answer is chosen.
- The question is never logged, because it can contain an address or a name.

### Evaluation

A fixed set of about 40 questions in `backend/tests/fixtures/guidance_router_eval.json`
with the expected ids: paraphrases of each entry, questions that span two entries,
and negatives that must return nothing (predictions, personal decisions such as
"should I leave tomorrow", off-topic questions, and instruction-override attempts).

`backend/scripts/guidance_router_eval.py` runs a named model against the set, and
reports top-choice accuracy on the positives, how often a negative wrongly matched,
the wrong-id rate, and median latency. It runs by hand against live providers and is
not part of CI. It is run for the current small model and for at least one larger
one, and the result decides whether paying for a larger model is worth it.

Starting bar, to be confirmed by the team before the first run: at least 90% top
choice on the positives and at least 90% correct abstention on the negatives. A model
below the bar is not shipped.

## Errors and edge cases

| Situation | Behaviour |
|---|---|
| Model down or no key | `unavailable`; the box says typed questions are unavailable and points to the buttons; buttons keep working |
| Router returns an unknown id | Dropped by the gate |
| Router returns text that is not JSON | `no_match` |
| No reviewed entry matches | Fixed bubble: no reviewed answer, with the suggested questions offered |
| Prediction or decision question | `no_match`, plus the fixed bubble; the answer is not invented |
| Emergency phrasing | `emergency`, fixed bubble pointing to 000; model not called |
| Question sent while one is in flight | Send is disabled until it returns |
| Rate limit on the hosted model | Reported as `unavailable` and not retried. If the same API key serves the explanation feature the two share one quota; to be confirmed in Phase 2 |
| Content file invalid | App fails to start, as before |
| No entry reviewed yet | Empty `entries`; the panel shows the notice and a neutral line, and the typed box is hidden |

## Testing

Backend, with mock providers and the in-memory repository, as elsewhere:

- content validation: slug-format ids, answer length limit, unknown condition
  key, missing source, duplicate id, unreviewed entries never served;
- `suggested_ids`: household conditions select the right entries, capped at six,
  topped up to four, location condition handled as before;
- gates: unknown id dropped, duplicates removed, capped at two, empty is `no_match`,
  malformed reply is `no_match`;
- emergency phrases return `emergency` and a spy router is **never called**;
- a router failure returns `unavailable`, not an error status;
- the question is absent from log output (checked with a captured logger);
- endpoint: `422` for empty and over-long questions, `404` for an unknown household,
  `200` for all four statuses, plan unchanged afterwards;
- the mock and disabled providers behave as described.

Frontend, with `node --test`, swapping methods on the exported `api` object as the
other store tests do: suggested button shows the local answer with no request; typed
question maps each status to the right bubble; send disabled while in flight; history
reset on reload; stale-date note kept.

## Documentation

Update `docs/iteration1-integration-contract.md` with the new response shape, the
`ask` endpoint and its four statuses, and the rule that the model returns ids only
and never user-visible text.

## Changes to the existing safety guidance work

- `GuidanceCardDefinition` becomes an entry definition with the fields above; the
  strict condition model and loader are kept.
- The selection service keeps its fact derivation and location handling; it now
  returns entries and suggested ids instead of a filtered card list.
- `SafetyGuidancePanel.vue` is replaced; `guidanceFreshness.js` and
  `safetyGuidanceNote.js` are reused.
- The seven drafted cards are split into entries. **Content review should wait for
  the split**, so the team reviews the short entries once rather than reviewing the
  long cards and then again.

## Later, not in this iteration

- Answers generated from reviewed text, with a gate that checks each claim.
- Multi-turn conversation, and saved chat history.
- Non-English questions and a non-English emergency pre-check.
- Entries for livestock and for households without private transport, once source
  pages are chosen.
- A scheduled check that flags when a CFA source page has changed.
