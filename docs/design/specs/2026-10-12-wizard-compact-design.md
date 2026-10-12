# Compact Plan Wizard — Design

**Status:** Proposed. Not implemented.
**Branch:** `feature/wizard-compact` (from `main`)
**Date:** 2026-10-12
**Builds on:** `docs/design/specs/2026-10-07-plan-wizard-design.md` (the one-question-at-a-time wizard)

## Problem

The wizard asks one question per screen. A household with two people, one pet and two
vehicles passes through roughly forty screens, and the vehicle section alone is five or
six per vehicle (has a vehicle, type, other, name, drivers, another, first choice, then a
separate backup screen). Editing is also slow: **Edit** on the Review screen reopens a
section at its first question, so changing one vehicle name means pressing Next through
every question before it.

## What this changes

Each wizard screen becomes a compact **form for one part of the plan**, with repeatable
**cards** for people, animals, vehicles, places and jobs. The seven backend sections are
shown on **five screens**. **Edit** on the Review screen opens that screen directly, with
every answer visible and editable at once.

Nothing about the data changes. The wizard still fills the same `HouseholdPlan`
aggregate, saves it through `householdStore.savePlan`, and reads completion from
`GET /households/{id}/completion`. **No backend, API or schema change.**

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Screens | 5 form screens, grouped as below | 7 screens; about 4 screens; merge only vehicles |
| Edit from Review | Opens the screen's form directly | Per-question deep links |
| Implementation | One Vue component per screen, bound to the draft through the existing helpers | A new generic field-definition engine |
| Save | One **Save and continue** per screen (saves the whole draft, as today) | Autosave; save only at the end |
| Skipping | **Skip for now** per screen; blanks are allowed | Required fields |
| Progress bar | 5 segments; a segment is complete when all its backend sections are complete | Keep 7 segments |
| Backup choices | Appear on the same screen as their primary choice | Separate screens |

Why components instead of a field engine: the questions differ a great deal (repeating
cards, conditional fields, one field that depends on another screen's data). A generic
engine would need most of those cases as special rules, while a component per screen is
straightforward and testable. The shared logic that matters (record helpers, rules,
summaries) is already in plain functions.

## The five screens

| # | Screen | Backend sections it covers | Contents |
|---|---|---|---|
| 1 | Your household | `household_profile` | People cards; animals |
| 2 | Where everyone is by day | `member_locations` | One row per person |
| 3 | How you would leave | `transport`, `backup_transport` | Vehicle yes/no; vehicle cards; first choice; backup vehicles |
| 4 | Where you would go | `primary_destination`, `backup_destination` | Destination, address, meeting point; backup place cards |
| 5 | Who does what | `responsibilities` | Job cards |

### Screen 1: Your household

- **Person cards.** The first card is "You". Each card has: name; relationship (a select;
  hidden on the first card, which is `self`); a description field shown only when the
  relationship is "Other"; two tick boxes for extra help (a dependant; needs help moving);
  and a notes field shown only when either box is ticked. Every card after the first has
  **Remove this person**. **Add another person** appends a card and moves focus to it.
- **Animals.** A yes/no "Do any animals leave with you?". **Yes** shows animal cards (pet or
  livestock; kind, with a description field shown only for "Other"; quantity, a whole
  number of at least 1) and **Add another animal**. **No** clears the animals.

### Screen 2: Where everyone is by day

One row per person: a select (Home, Work, School, Somewhere else, Not sure) and, once a
place is chosen, an address field with suggestions. With no people, a notice points back to
screen 1.

### Screen 3: How you would leave

- A yes/no "Do you have a vehicle you would leave in?".
- **No** removes private vehicles, clears the first choice and hides the rest of the screen.
  The backend already counts both vehicle sections complete in that case.
- **Yes** shows vehicle cards: type (select), a description shown only for "Other", a
  name (optional), and "Who can drive it?" (tick boxes of the household, hidden with no
  people). **Add another vehicle** appends a card; **Remove this vehicle** removes one.
- **Which would you take first?** (select of the vehicles, plus "Not sure yet").
- **Backup vehicle.** Tick boxes of the vehicles other than the first choice. With none
  to offer, a note says a second vehicle is needed and **Add another vehicle** is offered.

### Screen 4: Where you would go

- Destination name, address (with suggestions), and an optional meeting point.
- **Backup places.** Cards with a name and an address, **Remove this place** and **Add
  another place**.

### Screen 5: Who does what

Job cards: the job (a preset or "Something else", with a text field shown only for
"Something else"), who does it (select of people), and who covers it if they cannot
(select of the other people). **Add another job**, **Remove this job**. With no people, a
notice points back to screen 1.

## Rules (carried over unchanged)

- An animal kind, vehicle type or job described as "Something else" needs a description. A
  relationship of "Other" keeps an optional description, as today.
- A job's main and backup person must differ; choosing the same person as the main person
  clears the backup person.
- Removing a person removes them from every driver list and job.
- Removing a vehicle clears it from the first choice and the backup vehicles.
- "No private vehicle" and private vehicle records are never saved together.
- Backup vehicles and backup places share `arrangements.backup_arrangements`; each entry is
  `{ transport_id, destination }`. Choosing backup vehicles fills `transport_id` of entries
  in order; places fill `destination` in order; an entry with neither is dropped.
- A typed address is unverified, with null coordinates, until the backend resolves it on
  save. Choosing a suggestion sends `selected_address`. Editing the text clears an earlier
  verification and selection.
- An incomplete plan is always saveable.

## Saving and validation

- **Save and continue** first drops any person, job, destination or backup-place card that was
  opened but never filled in (animal and vehicle cards hold default values and count as
  filled; use Remove), trims typed names, then validates, then saves, then goes to the next
  screen. If the person arrived from Review, it returns to Review instead.
- Validation only blocks the rules above (a missing description for "Other", an invalid
  animal quantity, a backup person equal to the main person). Each message appears next to
  its field, the first invalid field takes focus, and nothing is saved. Everything else may
  be blank.
- **Skip for now** moves on without validating or saving; the answers stay in the draft and
  the existing unsaved-changes warning still applies.
- **Back** returns to the previous screen without saving.
- A failed save keeps the draft and the person's answers and shows the error.

## Review screen

- Five rows, one per screen. A row is **Complete** only when all its backend sections are
  complete, otherwise **Needs information**. Its text joins the existing `describeSection`
  summaries of its sections.
- **Edit** opens that screen's form; **Save and return to review** brings the person back.
- The `?section=` URL parameter still works: any of the seven section ids (and the legacy
  `people` and `destinations`) opens the screen that contains it, and `review` opens
  Review. With no parameter the wizard opens on the first incomplete screen, or Review when
  everything is complete.

## Progress bar

Five segments, one per screen, taken from the same completion data. The current screen is
highlighted. Labels: Household, Daytime, Vehicles, Places, Jobs.

## Architecture

All paths are under `frontend/src`.

| Unit | Change |
|---|---|
| `wizard/flow.js` | `SCREENS` (id, title, short label, backend section ids) replaces the per-question builders. Pure helpers: `screenOfSection`, `screenStatus(completion, screenId)`, `nextScreen`, `previousScreen`, `firstIncompleteScreen`. |
| `wizard/navigation.js` | Screen-based navigation and `resolveSectionParam`, with the legacy names kept. |
| `wizard/validation.js` (new) | Pure `validateScreen(plan, screenId)` returning a list of `{ field, message }`, and `pruneBlankCards(plan, screenId)`. |
| `wizard/wizardDraft.js` | Keeps its helpers. Adds `setBackupTransports(plan, ids)` for the backup tick boxes. |
| `wizard/summaries.js` | Keeps `describeSection`; adds `describeScreen`. |
| `components/wizard/screens/*.vue` (new) | `HouseholdScreen`, `DaytimeScreen`, `VehiclesScreen`, `PlacesScreen`, `JobsScreen`. Each renders its form from the draft and emits nothing else; the view owns saving. |
| `components/wizard/ScreenShell.vue` (new) | Heading, the form slot, error summary, and Back / Skip for now / Save and continue. |
| `components/wizard/ReviewScreen.vue`, `ProgressBar.vue` | Five rows and five segments. |
| `views/PlanBuilderView.vue` | Holds the draft and the current screen; saves; handles `returnToReview`. |
| Removed | `wizard/sections/*`, `wizard/step.js`, `wizard/useWizard.js`, `components/wizard/WizardShell.vue`, `SectionSummary.vue`, and any question component or helper no longer used. |

Reused as they are: `questions/AddressQuestion.vue` and the other input components where
they fit, `options.js`, `labels.js` and the record helpers in `wizardDraft.js`.

## Accessibility and layout

- Each card is a `fieldset` with a `legend` ("Person 2", "Vehicle 1"); every field has a
  visible label. Errors are linked to their field and the summary is announced as an alert.
- **Add another** moves focus to the first field of the new card. **Remove** moves focus
  to the **Add another** button.
- One column on phone width; a card never causes horizontal scrolling.
- Existing colour tokens and button classes; no new dependency.

## Testing

Existing wizard tests that assert one-question steps are rewritten for screens. Node
built-in runner, server-side rendering through `tests/helpers/loadComponent.js`, no new
dependency.

- **Pure logic:** `flow.js` (screen mapping, status, order, first incomplete), `navigation`
  (parameter resolution incl. legacy names), `validation` (each rule, first invalid field),
  `pruneBlankCards`, `setBackupTransports` (fill order, dropping empty entries, keeping
  places), `describeScreen`. The existing draft-helper tests stay.
- **Rules:** removing a person clears drivers and jobs; "no vehicle" clears vehicles and
  first choice; same main and backup person is cleared; address edits reset verification.
- **Components:** each screen renders its fields and conditional fields for a given plan
  (empty plan; plan with several people, animals and vehicles; "Other" selections; no
  vehicle; no people), the Review rows and statuses, and the five-segment progress bar.
- **View:** opening with each `?section=` value lands on the right screen; Edit then Save
  returns to Review; a failed save keeps the draft; the unsaved-changes guard still works.

## Review Focus

These are the cases most likely to be wrong, each to be pinned by a test:

1. Switching vehicles to "No" with vehicles already saved removes them and clears the first
   choice and backup vehicles (no "no private transport" beside vehicle records).
2. A backup place and a backup vehicle on the same entry are not lost when either side is
   edited or removed.
3. Removing a person who is a driver or a job's main or backup person leaves no dangling id.
4. A person, job, destination or backup-place card left blank is not saved as an empty
   record, and opening a screen is not an unsaved change.
5. Editing from Review changes one field and saves without discarding other unsaved answers.

## Out of scope

- Any backend, API or schema change; changes to completion rules.
- Autosave, drag to reorder, or a clickable progress bar for jumping between screens.
- Changes to the voice assistant, which only ever opens `/plan`.
