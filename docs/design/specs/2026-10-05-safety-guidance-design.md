# Safety Guidance — Design

**Status:** superseded in part by `2026-10-05-safety-qa-design.md`. The selection rules, content validation, review gating and location handling below still apply; the card list and `cards` response were replaced by short Q&A entries and a chat panel.
**Branch:** `feature/safety-guidance`
**Date:** 2026-10-05

## Problem

FIREBREAK can tell a household what its plan is missing and, through the
rendezvous explanation, describe a simulated result in prose. It cannot tell a
household what the fire authority advises it to *do*: when to leave, what to
pack, how to include pets, how to plan around someone who needs extra support.

That advice already exists on CFA's website. The product should surface the
parts relevant to each household, with attribution, without inventing any of it.

## What this adds

A "Safety guidance" panel on `/overview`. It shows a short list of cards, chosen
from the saved plan, each summarising one CFA page and linking to it.

**The app never generates this advice.** Every card is written and reviewed by
the team from a named source page. Nothing is produced by a model at request
time. This is the same line the rest of the product holds: no fabricated data,
and nothing worded as prediction.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Source of advice | Team-written summaries of CFA pages | Model answering from its own knowledge; scraping pages into a retrieval index |
| Card text | Summarised in the team's words, with a link to the source | Verbatim copy (the pages carry "Copyright CFA" and no open licence) |
| Selection | Deterministic rules over the saved plan | Model-chosen cards |
| Conditions | Fields that already exist in the plan and location context | New plan fields (ages, stay-or-go decision) |
| Model involvement | None in this iteration | A generated introductory sentence (see Later) |
| Storage | A reviewed content file in the repo | A MySQL table |

**Why not retrieval.** A retrieval index would need an embedding model, a vector
store, a retriever provider, and a new class of output gate able to prove a
generated answer did not distort a retrieved passage. None of that is needed to
show seven reviewed cards. The reviewed card file can seed such an index later.

**Why not verbatim.** Both CFA pages read show "Copyright CFA (Country Fire
Authority)" and no licence. The CC BY 4.0 licence recorded in `data/README.md`
covers the fire district dataset, not these pages.

## Content file

`backend/app/content/safety_guidance.json`: a list of cards. It lives under
`backend/app/` because the backend Dockerfile copies that directory whole but
only a few modules from `data/`; a file under `data/` would be missing from the
production container.

| Field | Meaning |
|---|---|
| `id` | Stable slug, unique |
| `title` | Short heading, English (the UI is English) |
| `body` | Summary in the team's words |
| `source_name` | Publisher shown to the user, e.g. `CFA` |
| `source_url` | Page the summary was made from, required |
| `retrieved_on` | Date the team read the page, required |
| `reviewed_by` | Team member who checked the card against the source page; `null` until then |
| `applies_when` | Object of conditions; `{}` means every household |

Allowed condition keys, each a boolean that must be `true` for the card to show
(a card with several keys needs all of them):

| Key | Derived from |
|---|---|
| `has_dependants` | any `members[].is_dependant` |
| `has_mobility_support` | any `members[].mobility_support_required` |
| `has_pets` | any `animals[]` with `category == "pet"` |
| `has_livestock` | any `animals[]` with `category == "livestock"` |
| `no_private_transport` | `has_private_transport is False` |
| `in_bushfire_prone_area` | household location context `is_bushfire_prone_area` |

Only `has_mobility_support`, `has_pets` and `in_bushfire_prone_area` are used by
the first seven cards. The others are accepted so later cards need no code change.

### Validation

A Pydantic model validates the file when it is loaded. It rejects, and the app
fails to start on:

- an unknown condition key,
- a missing `source_url` or `retrieved_on`,
- a duplicate `id`.

A card whose `reviewed_by` is `null` loads but is **never served**. A summary of
safety advice that nobody has checked against its source must not reach a user.

## The first seven cards

| `id` | Condition | Source page (cfa.vic.gov.au/fire-safety/your-fire-plan/…) |
|---|---|---|
| `leave-early` | every household | `when-to-leave` |
| `leave-early-extra-support` | `has_mobility_support` | `when-to-leave` |
| `last-resort-options` | every household | `when-to-leave` |
| `emergency-kit` | every household | `what-to-take-with-you` |
| `pets-in-your-plan` | `has_pets` | `pets-and-bushfires` |
| `plan-with-extra-support` | `has_mobility_support` | `planning-with-people-who-need-extra-support` |
| `prepare-your-property` | `in_bushfire_prone_area` | `preparing-for-bushfire-season` |

Not covered yet, for lack of a source page: livestock, and households without
private transport. The conditions exist; the cards do not.

Content constraints, to be checked at review:

- **`leave-early`** states the timing CFA gives for Extreme and Catastrophic days
  exactly as the page does. The reviewer confirms the figure against the page.
  It is advice, not a forecast, and the card never says a fire will occur.
- **`last-resort-options`** says plainly that these are options for when it is too
  late to leave and are not a plan. It is kept short and leans on the link.
- The CFA page also says CFA does not recommend staying to defend a property. The
  plan records no stay-or-go decision, so no card branches on one.

## Backend

Requests flow routes → service, like the rest of the backend.

- `app/schemas/safety_guidance.py`: `SafetyGuidanceCard` and `SafetyGuidance`.
- `app/services/safety_guidance.py`: loads and validates the content file once,
  then selects cards for a household. Pure functions over the plan and context;
  no I/O at request time apart from reading the saved plan and location context
  through the existing services.
- `GET /api/v1/households/{household_id}/safety-guidance`.

**Response.** The selected cards in file order, each with `id`, `title`, `body`,
`source_name`, `source_url`, `retrieved_on`. File order is the display order, so
the team controls priority by ordering the file.

**Status codes.** Unknown household is 404, like the other household routes. A
household with no saved plan is not an error: it receives the cards whose
`applies_when` is empty. The endpoint has no `unavailable` state, because the
content is local.

**Location condition.** `in_bushfire_prone_area` uses the existing cached location
context. If the household has no verified location or the context is
unavailable, cards that require it are left out. The condition is never guessed.
The response says so with `location_conditions_applied: false`, and the panel
tells the user that adding a verified address would show more guidance.

**What it does not do.** It does not write to the plan, call a model, or
persist anything of its own. It adds no database table and needs no migration.
The one outside read is the bushfire-prone-area flag: it goes through the
existing static-context resolver, which on a missing or stale cache calls the
spatial provider and stores the result in `household_location_context`, exactly
as `/local-context` already does.

## Frontend

- `api/client.js`: one method, `getSafetyGuidance(householdId)`.
- `stores/safetyGuidance.js`: Pinia setup store holding status and cards; the
  server stays authoritative.
- `components/overview/SafetyGuidancePanel.vue`: renders the cards. Each card
  shows the title, summary, and a "Source: CFA · checked against the source page
  on <date>" link opening the original page in a new tab. The date is
  `retrieved_on`, set by the reviewer and never refreshed automatically: showing
  today's date would claim a check nobody made. When that date is more than six
  calendar months old (or cannot be read), the card adds a note that it was last
  checked more than six months ago and points the reader to the linked page.
  `utils/guidanceFreshness.js` holds the rule so it is tested on its own.
- Mounted in `OverviewView.vue`.

Wording: the panel heading and copy never imply a prediction. The panel is
visually distinct from the "Generated summary" produced by the rendezvous
explanation, so a user can tell reviewed guidance from machine-written prose.

## Errors and edge cases

| Situation | Behaviour |
|---|---|
| Content file missing or invalid | App fails to start with a clear error; the content file is part of the build |
| Every matching card unreviewed | Empty list; the panel shows a short neutral message |
| No saved plan | General cards only |
| Location unverified | Location-conditioned cards omitted, flag set |
| Request fails | Panel shows a retryable error; the rest of `/overview` is unaffected |

## Testing

Backend, with `APP_DATA_MODE=mock` and the in-memory repository, as in the rest
of the suite:

- the content file itself loads and passes validation,
- each condition key selects and deselects correctly,
- multiple conditions on one card require all of them,
- unreviewed cards are never returned,
- no plan returns only general cards,
- unverified location omits location cards and sets the flag,
- unknown household returns 404,
- the route does not mutate the plan.

Frontend, with `node --test`, swapping methods on the exported `api` object and
restoring them in `afterEach`: store success, empty and error states.

## Documentation

Update `docs/iteration1-integration-contract.md` with the endpoint, response
shape and the rules above.

## Review process for content

1. Team member reads the source page and writes or edits the card.
2. A **different** member compares each card with the source page and sets
   `reviewed_by`.
3. Page dates seen while drafting came from summaries of the pages and are not
   verified. The reviewer records `retrieved_on` from the live page.
4. Cards are re-read before each fire season, or when CFA changes a source page.

## Later, not in this iteration

- **Introductory sentence from the model**, explaining why the shown cards apply
  to this household. It would need its own gate: the existing gates are tied to
  `RendezvousResult`, and the speculation gate rejects the word "fire". If it is
  rejected the cards still show, so it can be added or dropped without touching
  the rest.
- Cards for livestock and for households without private transport, once source
  pages are chosen.
- Optional condition fields such as children's ages or a stay-or-go decision.
  These change the plan schema, the form and the contract, so they are a
  separate piece of work.
- Retrieval over the reviewed cards for free-form questions.
