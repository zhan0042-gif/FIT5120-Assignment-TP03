# Plan Wizard — Design

**Status:** Proposed. Not implemented.
**Branch:** `feature/wizard-plan-builder` (from `main`)
**Date:** 2026-10-07
**Builds on:** the five-step stepper in `frontend/src/views/PlanBuilderView.vue`

## Problem

`/plan` presents each of four screens as a full form: People alone asks for names,
relationships, support needs, daytime addresses and animals together. A stressed
household facing that much at once is overwhelmed, and the stepper lets them jump
anywhere, so nothing guides them to what is still missing.

## What this adds

The plan builder becomes a **strict wizard**: one question at a time, in a fixed order.
A progress bar shows how complete the profile is. After the last group a Review screen
lists every section, with an **Edit** button that reopens just that group.

Nothing about the data changes. The wizard fills the same `HouseholdPlan` aggregate,
saves it through the same `householdStore.savePlan`, and reads completion from the same
`GET /households/{id}/completion`. No backend, API or schema change.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Granularity | One question per screen, grouped into 7 sections | Four screens as today; seven grouped screens |
| Grouping | The 7 sections the backend already scores | A frontend-only grouping |
| When to save | Explicit **Save and continue** at the end of each section | Silent autosave; save only at the very end; save every answer |
| Progress bar source | `householdStore.completion` (backend, from the saved plan) | Recomputing completion from the draft in the browser |
| Skipping | Every question has **Skip for now** | Required questions; skip only whole sections |
| Architecture | Data-driven: a flow definition plus one shell | Hiding fields inside the old forms |

Why the backend for progress: `CLAUDE.md` makes completion a derived value, never
stored and never duplicated. Recomputing it in the browser would copy the rules and let
the bar disagree with Overview.

Why skipping is allowed: the product rule is that an incomplete plan is always
saveable. A hard wizard that blocks on a question would break it for someone who does
not know an answer. A skipped question simply leaves its section incomplete, which the
bar and the Review screen show.

## The seven sections

Order and "complete" rules mirror `PlanCompletionService` in `backend/app/services/plans.py`.

| # | Section id | Questions, one per screen | Complete when |
|---|---|---|---|
| 1 | `household_profile` | Name; relationship (and a description if "Other"); needs extra help to leave; "Add another person?". Then "Any animals?"; type (and description if "Other"); quantity; "Add another animal?" | At least one member, every member named, every animal has a type |
| 2 | `member_locations` | For each member in turn: where during the day (home, work, school, somewhere else); address when it is not skipped | Every member has a usual location |
| 3 | `transport` | "Do you have a vehicle you would leave in?"; vehicle type (and description if "Other"); vehicle name; who can drive it; "Add another vehicle?"; "Which is your main vehicle?" | Marked as having no private transport, or has vehicles and a main one is chosen |
| 4 | `backup_transport` | "If the main vehicle cannot be used, which would you use?" (pick an existing vehicle or add one) | Marked no private transport, or a backup arrangement has a transport |
| 5 | `primary_destination` | Destination name; address; meeting point if separated (optional) | The primary destination has a name |
| 6 | `backup_destination` | Destination name; address; "Add another backup place?" | A backup arrangement has a destination with a name |
| 7 | `responsibilities` | Task (a preset or typed); main person; backup person; "Add another task?" | At least one task, each with a task name and a main person |

Rules carried over from the existing forms and backend:

- "Other" for an animal or vehicle type requires a description.
- A task's main and backup person must differ.
- Sections 4 and 6 write into the same `arrangements.backup_arrangements` list; each
  entry holds `{ transport_id, destination }`. Section 4 sets `transport_id`, section 6
  sets `destination`, and "add another" in either appends an entry.
- Choosing "no private transport" in section 3 sets `has_private_transport = false`.
  Section 4 is then skipped automatically because the backend already counts it
  complete.
- Typed addresses stay unverified with null coordinates until the backend resolves them
  on save. Selecting a suggestion sends `selected_address`, exactly as today.

## Architecture

All paths are under `frontend/src`.

| Unit | Purpose |
|---|---|
| `wizard/flow.js` | The flow definition (sections and questions) plus pure functions: `visibleQuestions`, `nextPosition`, `previousPosition`, `firstIncompleteSection`, `sectionAnswers`. No Vue, no I/O. |
| `wizard/wizardDraft.js` | Pure helpers that read and write one question's answer in the plan aggregate (add a member, set a usual location, link a backup arrangement). They reuse `newId` and keep the existing verification-reset behaviour for addresses. |
| `components/wizard/WizardShell.vue` | Renders the current question, the progress bar, and the Back / Next / Skip controls. |
| `components/wizard/ProgressBar.vue` | The completion bar. |
| `components/wizard/SectionSummary.vue` | The short recap and **Save and continue** button shown at the end of a section. |
| `components/wizard/ReviewScreen.vue` | Seven rows with status, summary and **Edit**; below them the existing `PlanChecks` and the "Save & Review Plan" action. |
| `components/wizard/questions/*.vue` | Small inputs: text, single choice, multiple choice, address, yes/no, number. The address input reuses `common/AddressAutocompleteInput.vue`. |
| `views/PlanBuilderView.vue` | Rewritten to host the shell: holds the detached draft, the position, and the save call. |

A question in `flow.js` has: `id`, `section`, `kind`, `prompt`, optional `helper`,
`visible(draft, context)`, an optional `repeat` (the list it loops over), and the
`read` / `write` paths used by `wizardDraft.js`. Adding a question later is one entry.

The old `HouseholdMembersForm`, `TransportForm`, `ArrangementsForm` and
`ResponsibilitiesForm` are no longer used by the plan builder. They stay in the tree
for now so the change can be compared and reverted; removing them is a follow-up.

## State and saving

- The draft is still a detached deep copy of `householdStore.plan`, and "unsaved" still
  means the draft differs from the saved plan. The store, API client and backend are
  untouched.
- **Save and continue** calls `householdStore.savePlan(draft)`, then the store refreshes
  completion. On success the wizard moves to the next section; the draft is reset to the
  saved plan as it is today.
- On failure the wizard stays in the section, shows the error, and keeps every answer so
  the user can retry.
- Answering a question edits the draft only. Nothing reaches the server between saves.

## Progress bar

- Shows "N of 7 sections complete" and seven small markers, each labelled
  (complete, needs information, current). State is never colour alone.
- Reads `householdStore.completion.sections`. It changes after a save, not after an
  answer. Before the first save it shows 0 of 7.
- While completion is loading it shows the previous value rather than flickering to 0.

## Review screen

- Reached after section 7, or directly when all seven sections are complete.
- Each row: section name, Complete / Needs information, a one-line summary of what was
  entered, and **Edit**. Edit opens that section's first question. After saving it
  returns to Review rather than continuing through the later sections.
- Below the rows: the existing `PlanChecks` panel and the existing
  `saveAndReview` action ("Save & Review Plan").

## Resuming

- Opening `/plan` with a saved plan opens the first incomplete section, or Review when
  all seven are complete. A new household starts at section 1.
- `?section=<id>` from Overview keeps working. The four old ids (`people`, `transport`,
  `destinations`, `responsibilities`) map to the first section they covered.

## Validation and errors

- The rules listed under "Rules carried over" are checked on the question they belong
  to, shown beside the input, linked to it with `aria-describedby`, and announced.
- A failing question blocks **Next** but never **Skip for now**. A skipped or invalid
  answer is not written to the draft.
- The backend remains the final validator. A `PlanValidationError` on save is shown in
  the section summary.

## Interaction and accessibility

- One question per screen, large prompt, one input. Enter means Next.
- On each new question focus moves to its prompt and the change is announced.
- Controls are at least 44px tall. The transition between questions is a short fade and
  is removed under `prefers-reduced-motion`.
- Works at phone width. Styling uses the existing design tokens (`style.css`).
- A `beforeunload` warning appears while the current section has unsaved answers, and
  leaving the route asks for confirmation in the same case.

## Testing

Node's built-in runner, as everywhere else in `frontend/tests`.

- `wizardFlow.test.js`: visible questions and order, conditional questions ("Other"
  description, address only when a location kind is chosen), repeat loops, skipping,
  going back, automatic skip of section 4 with no private transport.
- `wizardDraft.test.js`: each write helper, the shared `backup_arrangements` list, the
  address verification reset, the main/backup person rule.
- `wizardResume.test.js`: `firstIncompleteSection` and the legacy `?section` mapping.
- Component tests in the existing style (render with a stub store) for the shell,
  progress bar and review rows.
- Existing tests that pin the old `PlanBuilderView` structure are updated to match; the
  suite must stay green.
- Manual check in a browser against the mock backend: every section, skip, back, a save
  failure, a refresh mid-section, and the Review edit round trip.

## Out of scope

- Removing the four old form components.
- Any backend, API, schema or contract change; the Overview page.
- Autosave in the background, or saving partial answers to the server.
- Changing what "complete" means.

## Open points

- The exact wording of each prompt is drafted during implementation and reviewed with
  the screens.
- Whether the old form components are deleted is decided after the wizard is accepted.
