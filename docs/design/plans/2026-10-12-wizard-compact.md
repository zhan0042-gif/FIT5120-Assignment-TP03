# Compact Plan Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-question-per-screen plan wizard with five compact form screens (cards for people, animals, vehicles, places and jobs), and make **Edit** on the Review screen open the relevant form directly.

**Architecture:** Pure modules hold the rules (screen map and navigation, form actions, validation and blank-card clean-up, summaries); one Vue component per screen renders a form bound to the existing detached draft; `PlanBuilderView.vue` owns the draft, saving and Review. Old per-question modules are deleted last, once the new view is green. No backend, API or schema change.

**Tech Stack:** Vue 3 (script setup, plain JavaScript), Pinia, vue-router, Node built-in test runner with server-side rendering through `tests/helpers/loadComponent.js`. No new dependencies.

**Spec:** `docs/design/specs/2026-10-12-wizard-compact-design.md` (builds on `2026-10-07-plan-wizard-design.md`)

## Global Constraints

- All work is under `frontend/`. Run commands from `frontend/`: single file `node --test tests/<file>.test.js`; suite `npm test`; build `npm run build`.
- No change to `backend/`, `docs/iteration1-integration-contract.md`, the API client, the household store, or `PlanCompletionService` rules.
- The wizard still edits a detached JSON-clone of `householdStore.plan` and saves only through `householdStore.savePlan(draft.value)` (one call site in the view).
- Public ids are generated client-side by `newId` (existing helpers in `wizard/wizardDraft.js`); never invent ids elsewhere.
- Backend section order stays `household_profile, member_locations, transport, backup_transport, primary_destination, backup_destination, responsibilities`. Screens: `household`, `daytime`, `vehicles`, `places`, `jobs`.
- An incomplete plan is always saveable. Validation blocks only: missing description for an "Other" animal, vehicle or "Something else" job; animal quantity not a whole number of at least 1; a job's backup person equal to its main person.
- "No private vehicle" and private vehicle records are never saved together.
- Copy rules (existing): plain English, no exclamation marks, no prediction wording.
- Conventional commits with scope, e.g. `feat(frontend): …`. No attribution lines in commit messages.
- Voice assistant files (`src/voice/**`, `stores/voice.js`) are not touched.

## Rulings made while planning (the spec yields to these)

1. **Relationship description stays optional**, as in the current wizard. The spec said "Other" always needs a description; the existing code and backend only require it for animal, vehicle and job. Task 12 corrects the spec text.
2. **Animal and vehicle cards created by "Add another" hold default values** (a pet dog, quantity 1; a car), so they count as filled and are not pruned. Only person, job, destination and backup-place cards can be blank. Remove deletes the others. Task 12 corrects the spec.
3. **"Something else" job is marked by a single space** in `task_name` until the person types. Save validates it (error "Please describe the task.") and trims typed names. This avoids a new field on the plan.
4. **Dirty check and save use `finalisePlan`** (prune blanks, trim names) on a clone, so opening a screen that shows an empty first card never triggers the unsaved-changes warning.
5. **Back while editing from Review returns to Review**; otherwise it goes to the previous screen.

## Review Focus

Failure modes the spec implies; each has a test in the task named.

1. Answering "No" to the vehicle question with vehicles saved removes them and clears first choice and backup vehicles (Task 2).
2. Backup vehicles and backup places share entries; editing one never loses the other (Task 1).
3. Removing a person leaves no dangling driver or job id (existing helper, re-tested in Task 2).
4. A person, job, destination or backup-place card left blank is not saved as an empty record, and opening a screen is not an unsaved change (Task 3).
5. Editing one field from Review saves without discarding other unsaved answers, and Back returns to Review (Task 10).

## File Structure (new and changed)

| File | Responsibility |
|---|---|
| `src/wizard/screens.js` (new) | `SCREENS`, `screenOfSection`, `screenComplete`, `firstIncompleteScreen`, `nextScreen`, `previousScreen`, `resolveScreenParam` |
| `src/wizard/formActions.js` (new) | Pure actions the screens call: add/set/clear helpers |
| `src/wizard/validation.js` (new) | `validateScreen`, `finalisePlan` |
| `src/wizard/wizardDraft.js` | Adds `setBackupTransports`, `backupTransportIds` |
| `src/wizard/summaries.js` | Adds `describeScreen` |
| `src/components/wizard/fields/*.vue` (new) | `FormField`, `TextField`, `NumberField`, `SelectField`, `CheckField` |
| `src/components/wizard/screens/*.vue` (new) | `HouseholdScreen`, `DaytimeScreen`, `VehiclesScreen`, `PlacesScreen`, `JobsScreen` |
| `src/components/wizard/ScreenShell.vue` (new) | Heading, error summary, Back / Skip for now / Save and continue |
| `src/components/wizard/ProgressBar.vue`, `ReviewScreen.vue` | Five segments / five rows |
| `src/views/PlanBuilderView.vue` | Draft, current screen, saving, Review |
| Deleted (Task 11) | `wizard/flow.js`, `navigation.js`, `useWizard.js`, `step.js`, `pick.js`, `sections/*`, `components/wizard/WizardShell.vue`, `SectionSummary.vue`, `questions/ChoiceQuestion.vue`, `MultiQuestion.vue`, `TextQuestion.vue`, `NumberQuestion.vue`, and their tests |
| Kept | `wizard/options.js`, `labels.js`, `components/wizard/questions/AddressQuestion.vue`, `YesNoQuestion.vue` |

---

### Task 1: Backup vehicle helpers

**Files:**
- Modify: `src/wizard/wizardDraft.js` (append)
- Test: `tests/wizardDraft.test.js` (append)

**Interfaces:**
- Produces: `setBackupTransports(plan, ids: string[]): void` and `backupTransportIds(plan): string[]` exported from `wizardDraft.js`.

- [ ] **Step 1: Write the failing tests** (append to `tests/wizardDraft.test.js`; reuse its existing imports of `createEmptyHouseholdPlan` and `node:test`/`assert`, adding `setBackupTransports, backupTransportIds, backupDestination` to the `wizardDraft.js` import list)

```js
test('backup vehicles fill the backup entries in order and are read back', () => {
  const plan = createEmptyHouseholdPlan()
  setBackupTransports(plan, ['t_a', 't_b'])
  assert.deepEqual(backupTransportIds(plan), ['t_a', 't_b'])
  assert.equal(plan.arrangements.backup_arrangements.length, 2)
})

test('changing the backup vehicles keeps backup places and drops entries with neither', () => {
  const plan = createEmptyHouseholdPlan()
  setBackupTransports(plan, ['t_a', 't_b'])
  backupDestination(plan, 0).display_name = 'Hall'

  setBackupTransports(plan, [])

  assert.deepEqual(backupTransportIds(plan), [])
  assert.equal(plan.arrangements.backup_arrangements.length, 1)
  assert.equal(plan.arrangements.backup_arrangements[0].destination.display_name, 'Hall')
})

test('backup vehicles do not disturb a place that sits on a later entry', () => {
  const plan = createEmptyHouseholdPlan()
  backupDestination(plan, 1).display_name = 'Library'

  setBackupTransports(plan, ['t_a'])

  assert.deepEqual(backupTransportIds(plan), ['t_a'])
  const names = plan.arrangements.backup_arrangements.map((entry) => entry.destination?.display_name ?? null)
  assert.ok(names.includes('Library'))
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardDraft.test.js`
Expected: FAIL (`setBackupTransports is not a function` or import error).

- [ ] **Step 3: Implement** (append to `src/wizard/wizardDraft.js`)

```js
export function backupTransportIds(plan) {
  return (plan.arrangements?.backup_arrangements ?? []).map((entry) => entry.transport_id).filter(Boolean)
}

// Backup vehicles and backup places share `backup_arrangements` entries. This
// rewrites only the vehicle side: ids fill the entries in order, and an entry
// left with neither a vehicle nor a place is dropped.
export function setBackupTransports(plan, ids) {
  plan.arrangements ??= {}
  const list = (plan.arrangements.backup_arrangements ??= [])
  for (const entry of list) entry.transport_id = null
  ids.forEach((id, index) => {
    itemAt(list, index, newBackupArrangement).transport_id = id
  })
  plan.arrangements.backup_arrangements = list.filter((entry) => entry.transport_id || entry.destination)
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardDraft.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/wizardDraft.js frontend/tests/wizardDraft.test.js
git commit -m "feat(frontend): helpers for backup vehicle choices"
```

---

### Task 2: Form actions

**Files:**
- Create: `src/wizard/formActions.js`
- Test: `tests/wizardFormActions.test.js`

**Interfaces:**
- Consumes: helpers from `wizardDraft.js` (`memberAt`, `animalAt`, `transportAt`, `responsibilityAt`, `backupAt`, `removePrivateTransports`, `removeTransport`, `removeMember`, `backupDestination`, `primaryDestination`) and `TASK_PRESETS`, `ANIMAL_TYPES` from `options.js`.
- Produces (all pure, all mutate the plan or item given):
  - `HELP_OPTIONS`, `memberHelpValues(member): string[]`, `setMemberHelp(member, values)`
  - `addMember(plan)`, `setMemberRelationship(member, value)`
  - `setAnimalsAny(plan, yes)`, `addAnimal(plan)`, `setAnimalCategory(animal, value)`, `setAnimalType(animal, value)`
  - `setHasVehicle(plan, yes)`, `addVehicle(plan)`, `setVehicleType(vehicle, value)`, `setFirstVehicle(plan, id)`
  - `addBackupPlace(plan)`
  - `addJob(plan)`, `taskChoice(item): string`, `setTaskChoice(item, value)`, `setJobMain(item, memberId)`

- [ ] **Step 1: Write the failing tests** (`tests/wizardFormActions.test.js`)

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import {
  addJob, addMember, addVehicle, memberHelpValues, setAnimalCategory, setAnimalsAny, setAnimalType,
  setFirstVehicle, setHasVehicle, setJobMain, setMemberHelp, setMemberRelationship, setTaskChoice,
  setVehicleType, taskChoice,
} from '../src/wizard/formActions.js'
import { removeMember } from '../src/wizard/wizardDraft.js'

test('the first person added is "self"; later people are not', () => {
  const plan = createEmptyHouseholdPlan()
  assert.equal(addMember(plan).relationship, 'self')
  assert.equal(addMember(plan).relationship, null)
})

test('help ticks map to the two member flags and back', () => {
  const plan = createEmptyHouseholdPlan()
  const member = addMember(plan)
  setMemberHelp(member, ['dependant'])
  assert.deepEqual([member.is_dependant, member.mobility_support_required], [true, false])
  assert.deepEqual(memberHelpValues(member), ['dependant'])
  setMemberHelp(member, [])
  assert.deepEqual(memberHelpValues(member), [])
})

test('choosing a relationship other than "other" clears its description', () => {
  const plan = createEmptyHouseholdPlan()
  const member = addMember(plan)
  setMemberRelationship(member, 'other')
  member.relationship_other = 'Neighbour'
  setMemberRelationship(member, 'friend_or_housemate')
  assert.equal(member.relationship_other, null)
})

test('answering yes to animals adds one; no clears them', () => {
  const plan = createEmptyHouseholdPlan()
  setAnimalsAny(plan, true)
  assert.equal(plan.animals.length, 1)
  setAnimalsAny(plan, false)
  assert.equal(plan.animals.length, 0)
})

test('changing an animal category resets its kind; the same category keeps it', () => {
  const plan = createEmptyHouseholdPlan()
  setAnimalsAny(plan, true)
  const animal = plan.animals[0]
  setAnimalType(animal, 'cat')
  setAnimalCategory(animal, 'pet')
  assert.equal(animal.animal_type, 'cat')
  setAnimalCategory(animal, 'livestock')
  assert.equal(animal.animal_type, 'horse')
  setAnimalType(animal, 'other')
  animal.animal_type_other = 'Llama'
  setAnimalType(animal, 'sheep')
  assert.equal(animal.animal_type_other, null)
})

test('answering no to a vehicle removes vehicles and clears the first choice and backups', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, true)
  addVehicle(plan)
  setFirstVehicle(plan, plan.transports[0].transport_id)
  plan.arrangements.backup_arrangements.push({ transport_id: plan.transports[1].transport_id, destination: null })

  setHasVehicle(plan, false)

  assert.equal(plan.has_private_transport, false)
  assert.equal(plan.transports.length, 0)
  assert.equal(plan.arrangements.primary_transport_id, null)
  assert.deepEqual(plan.arrangements.backup_arrangements.map((entry) => entry.transport_id), [null])
})

test('answering yes to a vehicle ensures there is one card', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, true)
  setHasVehicle(plan, true)
  assert.equal(plan.has_private_transport, true)
  assert.equal(plan.transports.length, 1)
})

test('changing a vehicle type away from "other" clears its description', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, true)
  const vehicle = plan.transports[0]
  setVehicleType(vehicle, 'other')
  vehicle.transport_type_other = 'Tractor'
  setVehicleType(vehicle, 'ute')
  assert.equal(vehicle.transport_type_other, null)
})

test('job choice: preset, "something else" (a single space), blank', () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan)
  const job = addJob(plan)
  assert.equal(taskChoice(job), '')
  setTaskChoice(job, 'Drive the household')
  assert.equal(taskChoice(job), 'Drive the household')
  setTaskChoice(job, 'other')
  assert.equal(job.task_name, ' ')
  assert.equal(taskChoice(job), 'other')
  job.task_name = 'Feed the chickens'
  assert.equal(taskChoice(job), 'other')
  setTaskChoice(job, 'other')
  assert.equal(job.task_name, 'Feed the chickens')
})

test('choosing the main person as the backup person clears the backup', () => {
  const plan = createEmptyHouseholdPlan()
  const a = addMember(plan)
  const job = addJob(plan)
  job.backup_member_id = a.member_id
  setJobMain(job, a.member_id)
  assert.equal(job.primary_member_id, a.member_id)
  assert.equal(job.backup_member_id, null)
})

test('removing a person leaves no dangling driver or job id', () => {
  const plan = createEmptyHouseholdPlan()
  const a = addMember(plan)
  const b = addMember(plan)
  setHasVehicle(plan, true)
  plan.transports[0].driver_member_ids = [a.member_id, b.member_id]
  const job = addJob(plan)
  job.primary_member_id = b.member_id
  job.backup_member_id = a.member_id

  removeMember(plan, b.member_id)

  assert.deepEqual(plan.transports[0].driver_member_ids, [a.member_id])
  assert.equal(job.primary_member_id, null)
  assert.equal(job.backup_member_id, a.member_id)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardFormActions.test.js`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement** (`src/wizard/formActions.js`)

```js
import { ANIMAL_TYPES, TASK_PRESETS } from './options.js'
import {
  animalAt, backupAt, memberAt, removePrivateTransports, responsibilityAt, transportAt,
} from './wizardDraft.js'

export const HELP_OPTIONS = [
  ['dependant', 'Depends on someone else to leave, such as a young child'],
  ['mobility', 'Needs help moving or getting into a vehicle'],
]

export const memberHelpValues = (member) =>
  [member.is_dependant && 'dependant', member.mobility_support_required && 'mobility'].filter(Boolean)

export function setMemberHelp(member, values) {
  member.is_dependant = values.includes('dependant')
  member.mobility_support_required = values.includes('mobility')
}

export function addMember(plan) {
  const member = memberAt(plan, plan.members.length)
  if (plan.members.length === 1 && member.relationship === null) member.relationship = 'self'
  return member
}

export function setMemberRelationship(member, value) {
  member.relationship = value || null
  if (value !== 'other') member.relationship_other = null
}

export function setAnimalsAny(plan, yes) {
  if (yes) {
    if (!plan.animals.length) animalAt(plan, 0)
  } else {
    plan.animals.splice(0)
  }
}

export const addAnimal = (plan) => animalAt(plan, plan.animals.length)

export function setAnimalCategory(animal, value) {
  // The same category again must keep the kind already chosen.
  if (animal.category === value) return
  animal.category = value
  animal.animal_type = ANIMAL_TYPES[value][0][0]
  animal.animal_type_other = null
}

export function setAnimalType(animal, value) {
  animal.animal_type = value
  if (value !== 'other') animal.animal_type_other = null
}

export function setHasVehicle(plan, yes) {
  plan.has_private_transport = yes
  if (yes) {
    if (!plan.transports.length) transportAt(plan, 0)
    return
  }
  // The backend rejects "no private transport" beside private vehicle records,
  // and only counts it complete while no first vehicle is set.
  removePrivateTransports(plan)
  plan.arrangements ??= {}
  plan.arrangements.primary_transport_id = null
}

export const addVehicle = (plan) => transportAt(plan, plan.transports.length)

export function setVehicleType(vehicle, value) {
  vehicle.transport_type = value
  if (value !== 'other') vehicle.transport_type_other = null
}

export function setFirstVehicle(plan, id) {
  plan.arrangements ??= {}
  plan.arrangements.primary_transport_id = id || null
}

export function addBackupPlace(plan) {
  const entries = plan.arrangements?.backup_arrangements ?? []
  const target = entries.findIndex((entry) => !entry.destination)
  return backupAt(plan, target === -1 ? entries.length : target)
}

export const addJob = (plan) => responsibilityAt(plan, plan.responsibilities.length)

// '' = nothing chosen, a preset name, or 'other'. A single space in `task_name`
// means "Something else" was chosen but nothing is typed yet.
export function taskChoice(item) {
  const name = item.task_name ?? ''
  if (name === '') return ''
  return TASK_PRESETS.includes(name) ? name : 'other'
}

export function setTaskChoice(item, value) {
  if (value === 'other') {
    if (TASK_PRESETS.includes(item.task_name) || !item.task_name) item.task_name = ' '
  } else {
    item.task_name = value
  }
}

export function setJobMain(item, memberId) {
  item.primary_member_id = memberId || null
  // The backend rejects a backup person who is also the main person.
  if (item.backup_member_id && item.backup_member_id === item.primary_member_id) item.backup_member_id = null
}
```

`addBackupPlace` returns the entry that will hold the new place; the Places screen creates its destination through `backupDestination(plan, index)` (Task 7).

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardFormActions.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/formActions.js frontend/tests/wizardFormActions.test.js
git commit -m "feat(frontend): pure form actions for the compact wizard"
```

---

### Task 3: Screens, validation and finalising

**Files:**
- Create: `src/wizard/screens.js`, `src/wizard/validation.js`
- Modify: `src/wizard/summaries.js` (append `describeScreen`)
- Test: `tests/wizardScreens.test.js`, `tests/wizardValidation.test.js`

**Interfaces:**
- Produces from `screens.js`: `SCREENS: {id,title,short,sections}[]`, `screenOfSection(sectionId)`, `screenComplete(completion, screenId): boolean`, `firstIncompleteScreen(completion): string|null`, `nextScreen(id): string` (a screen id or `'review'`), `previousScreen(id): string|null`, `resolveScreenParam(value): string|null` (a screen id, `'review'`, or null).
- Produces from `validation.js`: `validateScreen(plan, screenId): {field,message}[]`, `finalisePlan(plan): plan` (mutates and returns), `finalisedClone(plan): plan`.
- Produces from `summaries.js`: `describeScreen(plan, screenId): string`.

- [ ] **Step 1: Write the failing tests**

`tests/wizardScreens.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  SCREENS, firstIncompleteScreen, nextScreen, previousScreen, resolveScreenParam, screenComplete, screenOfSection,
} from '../src/wizard/screens.js'

const completion = (statuses) => ({
  sections: Object.entries(statuses).map(([section, status]) => ({ section, status })),
})
const ALL = {
  household_profile: 'complete', member_locations: 'complete', transport: 'complete',
  backup_transport: 'complete', primary_destination: 'complete', backup_destination: 'complete',
  responsibilities: 'complete',
}

test('five screens cover the seven backend sections in order', () => {
  assert.deepEqual(SCREENS.map((screen) => screen.id), ['household', 'daytime', 'vehicles', 'places', 'jobs'])
  assert.deepEqual(SCREENS.flatMap((screen) => screen.sections), [
    'household_profile', 'member_locations', 'transport', 'backup_transport',
    'primary_destination', 'backup_destination', 'responsibilities',
  ])
})

test('a section maps to the screen that holds it', () => {
  assert.equal(screenOfSection('backup_transport'), 'vehicles')
  assert.equal(screenOfSection('backup_destination'), 'places')
  assert.equal(screenOfSection('nope'), null)
})

test('a screen is complete only when every one of its sections is', () => {
  assert.equal(screenComplete(completion(ALL), 'vehicles'), true)
  assert.equal(screenComplete(completion({ ...ALL, backup_transport: 'needs_information' }), 'vehicles'), false)
  assert.equal(screenComplete(null, 'household'), false)
})

test('first incomplete screen, or null when all are complete', () => {
  assert.equal(firstIncompleteScreen(completion({ ...ALL, primary_destination: 'needs_information' })), 'places')
  assert.equal(firstIncompleteScreen(completion(ALL)), null)
})

test('next and previous screens; review follows the last', () => {
  assert.equal(nextScreen('household'), 'daytime')
  assert.equal(nextScreen('jobs'), 'review')
  assert.equal(previousScreen('daytime'), 'household')
  assert.equal(previousScreen('household'), null)
})

test('the section parameter accepts screens, sections, legacy names and review', () => {
  assert.equal(resolveScreenParam('review'), 'review')
  assert.equal(resolveScreenParam('vehicles'), 'vehicles')
  assert.equal(resolveScreenParam('backup_transport'), 'vehicles')
  assert.equal(resolveScreenParam('responsibilities'), 'jobs')
  assert.equal(resolveScreenParam('people'), 'household')
  assert.equal(resolveScreenParam('destinations'), 'places')
  assert.equal(resolveScreenParam('bogus'), null)
  assert.equal(resolveScreenParam(['x']), null)
})
```

`tests/wizardValidation.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { describeScreen } from '../src/wizard/summaries.js'
import { finalisePlan, finalisedClone, validateScreen } from '../src/wizard/validation.js'
import { addAnimal, addJob, addMember, addVehicle, setAnimalType, setHasVehicle, setVehicleType } from '../src/wizard/formActions.js'
import { backupDestination, primaryDestination } from '../src/wizard/wizardDraft.js'

test('an empty plan has nothing to fix on any screen', () => {
  const plan = createEmptyHouseholdPlan()
  for (const id of ['household', 'daytime', 'vehicles', 'places', 'jobs']) assert.deepEqual(validateScreen(plan, id), [])
})

test('an "Other" animal or vehicle needs a description', () => {
  const plan = createEmptyHouseholdPlan()
  addAnimal(plan)
  setAnimalType(plan.animals[0], 'other')
  setHasVehicle(plan, true)
  setVehicleType(plan.transports[0], 'other')

  assert.deepEqual(validateScreen(plan, 'household').map((e) => e.field), ['animal:0:type_other'])
  assert.deepEqual(validateScreen(plan, 'vehicles').map((e) => e.field), ['vehicle:0:type_other'])

  plan.animals[0].animal_type_other = 'Ferret'
  plan.transports[0].transport_type_other = 'Tractor'
  assert.deepEqual(validateScreen(plan, 'household'), [])
  assert.deepEqual(validateScreen(plan, 'vehicles'), [])
})

test('an animal quantity must be a whole number of at least 1', () => {
  const plan = createEmptyHouseholdPlan()
  addAnimal(plan)
  for (const bad of [0, -1, 1.5, '']) {
    plan.animals[0].quantity = bad
    assert.deepEqual(validateScreen(plan, 'household').map((e) => e.field), ['animal:0:quantity'])
  }
  plan.animals[0].quantity = 3
  assert.deepEqual(validateScreen(plan, 'household'), [])
})

test('a job needs a description once "Something else" is chosen, and a different backup person', () => {
  const plan = createEmptyHouseholdPlan()
  const a = addMember(plan)
  const job = addJob(plan)
  job.task_name = ' '
  job.primary_member_id = a.member_id
  job.backup_member_id = a.member_id

  assert.deepEqual(validateScreen(plan, 'jobs').map((e) => e.field), ['resp:0:task_custom', 'resp:0:backup'])
})

test('the first problem is reported first, in screen order', () => {
  const plan = createEmptyHouseholdPlan()
  addAnimal(plan)
  addAnimal(plan)
  plan.animals[1].quantity = 0
  setAnimalType(plan.animals[0], 'other')
  assert.deepEqual(validateScreen(plan, 'household').map((e) => e.field), ['animal:0:type_other', 'animal:1:quantity'])
})

test('finalising drops blank cards and trims names; filled cards stay', () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan) // blank first card
  const b = addMember(plan)
  b.display_name = '  Sam  '
  addJob(plan) // blank job
  const job = addJob(plan)
  job.task_name = ' Feed the chickens '
  primaryDestination(plan) // blank destination
  backupDestination(plan, 0) // blank backup place

  finalisePlan(plan)

  assert.deepEqual(plan.members.map((m) => m.display_name), ['Sam'])
  assert.deepEqual(plan.responsibilities.map((r) => r.task_name), ['Feed the chickens'])
  assert.equal(plan.arrangements.primary_destination, null)
  assert.deepEqual(plan.arrangements.backup_arrangements, [])
})

test('a vehicle or animal card with default values is kept', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, true)
  addAnimal(plan)
  finalisePlan(plan)
  assert.equal(plan.transports.length, 1)
  assert.equal(plan.animals.length, 1)
})

test('finalising a clone leaves the original untouched, so a blank first card is not a change', () => {
  const stored = createEmptyHouseholdPlan()
  const draft = JSON.parse(JSON.stringify(stored))
  addMember(draft)
  primaryDestination(draft)
  assert.equal(JSON.stringify(finalisedClone(draft)), JSON.stringify(finalisedClone(stored)))
  assert.equal(draft.members.length, 1)
})

test('a screen summary joins its sections, and is short without a vehicle', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, false)
  assert.equal(describeScreen(plan, 'vehicles'), 'No private vehicle')
  const empty = createEmptyHouseholdPlan()
  assert.match(describeScreen(empty, 'places'), /No destination yet/)
  assert.match(describeScreen(empty, 'places'), /No backup place yet/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardScreens.test.js tests/wizardValidation.test.js`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement**

`src/wizard/screens.js`:

```js
// Five form screens over the seven backend sections. The order of the sections
// matches PlanCompletionService.SECTION_ORDER in the backend.
export const SCREENS = [
  { id: 'household', title: 'Your household', short: 'Household', sections: ['household_profile'] },
  { id: 'daytime', title: 'Where everyone is by day', short: 'Daytime', sections: ['member_locations'] },
  { id: 'vehicles', title: 'How you would leave', short: 'Vehicles', sections: ['transport', 'backup_transport'] },
  { id: 'places', title: 'Where you would go', short: 'Places', sections: ['primary_destination', 'backup_destination'] },
  { id: 'jobs', title: 'Who does what', short: 'Jobs', sections: ['responsibilities'] },
]

const LEGACY = { people: 'household', destinations: 'places' }

export const screenOfSection = (sectionId) => SCREENS.find((screen) => screen.sections.includes(sectionId))?.id ?? null

export function screenComplete(completion, screenId) {
  const screen = SCREENS.find((item) => item.id === screenId)
  if (!screen) return false
  return screen.sections.every(
    (id) => completion?.sections?.find((item) => item.section === id)?.status === 'complete',
  )
}

export const firstIncompleteScreen = (completion) =>
  SCREENS.find((screen) => !screenComplete(completion, screen.id))?.id ?? null

export function nextScreen(screenId) {
  const index = SCREENS.findIndex((screen) => screen.id === screenId)
  return SCREENS[index + 1]?.id ?? 'review'
}

export function previousScreen(screenId) {
  const index = SCREENS.findIndex((screen) => screen.id === screenId)
  return index > 0 ? SCREENS[index - 1].id : null
}

export function resolveScreenParam(value) {
  if (typeof value !== 'string') return null
  if (value === 'review') return 'review'
  if (SCREENS.some((screen) => screen.id === value)) return value
  return screenOfSection(value) ?? LEGACY[value] ?? null
}
```

`src/wizard/validation.js`:

```js
const blankText = (value) => !String(value ?? '').trim()

function memberIsBlank(member) {
  return blankText(member.display_name) && !member.is_dependant && !member.mobility_support_required
    && blankText(member.support_notes) && blankText(member.relationship_other) && !member.usual_location
    && (member.relationship === null || member.relationship === 'self')
}

const destinationIsBlank = (place) => !place || (blankText(place.display_name) && blankText(place.address))

const jobIsBlank = (job) =>
  blankText(job.task_name) && !job.primary_member_id && !job.backup_member_id

// Drops cards that were opened but never filled in, and trims typed names. Only
// people, jobs, the destination and backup places can be blank: an animal or a
// vehicle card holds default values and counts as filled.
export function finalisePlan(plan) {
  plan.members = plan.members.filter((member) => !memberIsBlank(member))
  for (const member of plan.members) member.display_name = (member.display_name ?? '').trim()
  for (const vehicle of plan.transports) vehicle.display_name = (vehicle.display_name ?? '').trim()
  plan.responsibilities = plan.responsibilities.filter((job) => !jobIsBlank(job))
  for (const job of plan.responsibilities) {
    if (!blankText(job.task_name)) job.task_name = job.task_name.trim()
  }
  const arrangements = (plan.arrangements ??= {})
  if (destinationIsBlank(arrangements.primary_destination)) arrangements.primary_destination = null
  else arrangements.primary_destination.display_name = (arrangements.primary_destination.display_name ?? '').trim()
  const backups = arrangements.backup_arrangements ?? []
  for (const entry of backups) {
    if (destinationIsBlank(entry.destination)) entry.destination = null
    else entry.destination.display_name = (entry.destination.display_name ?? '').trim()
  }
  arrangements.backup_arrangements = backups.filter((entry) => entry.transport_id || entry.destination)
  return plan
}

export const finalisedClone = (plan) => finalisePlan(JSON.parse(JSON.stringify(plan)))

// What blocks a save. Everything else may be left blank: an incomplete plan is
// always saveable. Each item is { field, message }; `field` is the id of the
// control to focus.
export function validateScreen(plan, screenId) {
  const errors = []
  const add = (field, message) => errors.push({ field, message })

  if (screenId === 'household') {
    plan.animals.forEach((animal, i) => {
      if (animal.animal_type === 'other' && blankText(animal.animal_type_other)) {
        add(`animal:${i}:type_other`, 'Please describe the animal.')
      }
      const quantity = Number(animal.quantity)
      if (!Number.isInteger(quantity) || quantity < 1) {
        add(`animal:${i}:quantity`, 'Enter a whole number of at least 1.')
      }
    })
  }

  if (screenId === 'vehicles') {
    plan.transports.forEach((vehicle, i) => {
      if (vehicle.transport_type === 'other' && blankText(vehicle.transport_type_other)) {
        add(`vehicle:${i}:type_other`, 'Please describe the vehicle.')
      }
    })
  }

  if (screenId === 'jobs') {
    plan.responsibilities.forEach((job, i) => {
      const name = job.task_name ?? ''
      if (name !== '' && blankText(name)) add(`resp:${i}:task_custom`, 'Please describe the task.')
      if (job.backup_member_id && job.backup_member_id === job.primary_member_id) {
        add(`resp:${i}:backup`, 'Choose someone other than the main person.')
      }
    })
  }

  return errors
}

```

Append to `src/wizard/summaries.js`:

```js
import { SCREENS } from './screens.js'

export function describeScreen(plan, screenId) {
  const screen = SCREENS.find((item) => item.id === screenId)
  if (!screen) return ''
  if (screenId === 'vehicles' && plan.has_private_transport === false) return 'No private vehicle'
  return screen.sections.map((id) => describeSection(plan, id)).join(' · ')
}
```

(Place the import with the other imports at the top of the file.)

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardScreens.test.js tests/wizardValidation.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/screens.js frontend/src/wizard/validation.js frontend/src/wizard/summaries.js frontend/tests/wizardScreens.test.js frontend/tests/wizardValidation.test.js
git commit -m "feat(frontend): screen map, validation and blank-card clean-up"
```

---

### Task 4: Field components

**Files:**
- Create: `src/components/wizard/fields/FormField.vue`, `TextField.vue`, `NumberField.vue`, `SelectField.vue`, `CheckField.vue`
- Test: `tests/wizardFields.test.js`

**Interfaces:**
- All: `id` (string), `label` (string), `error` (string, default `''`), `helper` (string, default `''`). The control gets `:id="id"`, and when there is an error `aria-invalid="true"` and `aria-describedby="<id>-error"`; the error paragraph has `id="<id>-error"`.
- `TextField`: `v-model` string; `placeholder`, `maxLength` (default 200).
- `NumberField`: `v-model` number; `min` (default 0).
- `SelectField`: `v-model` string; `options` array of `[value, label]`.
- `CheckField`: `v-model` array of values; `options` array of `[value, label]`; renders a `fieldset` with `legend` = label, `id` on the fieldset.

- [ ] **Step 1: Write the failing test** (`tests/wizardFields.test.js`)

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { importComponent } from './helpers/loadComponent.js'

const render = async (name, props) =>
  renderToString(createSSRApp(await importComponent(`../src/components/wizard/fields/${name}.vue`), props))

test('a text field has a visible label tied to its input and no error by default', async () => {
  const html = await render('TextField', { id: 'f1', label: 'Name', modelValue: 'Maya' })
  assert.match(html, /<label[^>]*for="f1"[^>]*>Name<\/label>/)
  assert.match(html, /<input[^>]*id="f1"/)
  assert.match(html, /value="Maya"/)
  assert.doesNotMatch(html, /aria-invalid/)
})

test('an error is linked to the control and shown beside it', async () => {
  const html = await render('TextField', { id: 'f1', label: 'Name', modelValue: '', error: 'Please describe it.' })
  assert.match(html, /aria-invalid="true"/)
  assert.match(html, /aria-describedby="f1-error"/)
  assert.match(html, /id="f1-error"[^>]*>Please describe it\./)
})

test('a number field keeps its minimum', async () => {
  const html = await render('NumberField', { id: 'n1', label: 'How many?', modelValue: 2, min: 1 })
  assert.match(html, /type="number"/)
  assert.match(html, /min="1"/)
})

test('a select lists its options and marks the chosen one', async () => {
  const html = await render('SelectField', { id: 's1', label: 'Kind', modelValue: 'ute', options: [['car', 'Car'], ['ute', 'Ute']] })
  assert.match(html, /<option value="car">Car<\/option>/)
  assert.match(html, /<option value="ute" selected[^>]*>Ute<\/option>/)
})

test('a check group is a fieldset with a legend and checked boxes', async () => {
  const html = await render('CheckField', { id: 'c1', label: 'Who can drive it?', modelValue: ['a'], options: [['a', 'Maya'], ['b', 'Sam']] })
  assert.match(html, /<fieldset[^>]*id="c1"/)
  assert.match(html, /<legend[^>]*>Who can drive it\?<\/legend>/)
  assert.match(html, /value="a"[^>]*checked/)
  assert.doesNotMatch(html, /value="b"[^>]*checked/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardFields.test.js`
Expected: FAIL (cannot find components).

- [ ] **Step 3: Implement the components**

`FormField.vue` (wrapper; the other fields use it so label and error markup live in one place):

```vue
<script setup>
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
})
</script>

<template>
  <div class="field">
    <label class="label" :for="id">{{ label }}</label>
    <p v-if="helper" class="helper">{{ helper }}</p>
    <slot />
    <p v-if="error" :id="`${id}-error`" class="field-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.field { display: grid; gap: 0.35rem; }
.label { font-weight: 700; }
.helper { color: var(--color-text-muted); font-size: 0.9375rem; margin: 0; }
</style>
```

`TextField.vue`:

```vue
<script setup>
import FormField from './FormField.vue'

defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  maxLength: { type: Number, default: 200 },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <FormField :id="id" :label="label" :helper="helper" :error="error">
    <input
      :id="id"
      v-model="model"
      class="control"
      type="text"
      autocomplete="off"
      :placeholder="placeholder"
      :maxlength="maxLength"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
    />
  </FormField>
</template>

<style scoped>
.control { background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; color: var(--color-text); font-size: 1.0625rem; min-height: 3rem; padding: 0.6rem 0.8rem; width: 100%; }
</style>
```

`NumberField.vue`: same shape with `type="number" inputmode="numeric" step="1" :min="min"`, `v-model.number`, `max-width: 10rem`, default model 1.

`SelectField.vue`:

```vue
<script setup>
import FormField from './FormField.vue'

defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  options: { type: Array, required: true },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <FormField :id="id" :label="label" :helper="helper" :error="error">
    <select
      :id="id"
      v-model="model"
      class="control"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? `${id}-error` : undefined"
    >
      <option v-for="[value, text] in options" :key="value" :value="value">{{ text }}</option>
    </select>
  </FormField>
</template>

<style scoped>
.control { background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; color: var(--color-text); font-size: 1.0625rem; min-height: 3rem; padding: 0.6rem 0.8rem; width: 100%; }
</style>
```

`CheckField.vue`:

```vue
<script setup>
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  helper: { type: String, default: '' },
  error: { type: String, default: '' },
  options: { type: Array, required: true },
})
const model = defineModel({ type: Array, default: () => [] })

function toggle(value) {
  model.value = model.value.includes(value) ? model.value.filter((item) => item !== value) : [...model.value, value]
}
</script>

<template>
  <fieldset :id="id" class="group" :aria-describedby="error ? `${id}-error` : undefined">
    <legend class="label">{{ label }}</legend>
    <p v-if="helper" class="helper">{{ helper }}</p>
    <label v-for="[value, text] in options" :key="value" class="check" :class="{ 'is-selected': model.includes(value) }">
      <input type="checkbox" :value="value" :checked="model.includes(value)" @change="toggle(value)" />
      <span>{{ text }}</span>
    </label>
    <p v-if="error" :id="`${id}-error`" class="field-error">{{ error }}</p>
  </fieldset>
</template>

<style scoped>
.group { border: 0; display: grid; gap: 0.5rem; margin: 0; min-width: 0; padding: 0; }
.label { font-weight: 700; padding: 0; }
.helper { color: var(--color-text-muted); font-size: 0.9375rem; margin: 0; }
.check { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 12px; cursor: pointer; display: flex; gap: 0.7rem; min-height: 3rem; padding: 0.5rem 0.9rem; }
.check.is-selected { background: var(--color-accent-soft); border-color: var(--color-accent-ink); font-weight: 700; }
.check input { flex: none; height: 1.2rem; width: 1.2rem; }
.check:focus-within { outline: 3px solid var(--color-focus); outline-offset: 2px; }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardFields.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/fields frontend/tests/wizardFields.test.js
git commit -m "feat(frontend): labelled form fields for the compact wizard"
```

---

### Task 5: Household screen

**Files:**
- Create: `src/components/wizard/screens/HouseholdScreen.vue`
- Test: `tests/wizardScreenComponents.test.js` (create; later tasks append)

**Interfaces:**
- Props: `plan` (the draft aggregate, mutated in place), `errors` (object `field -> message`, default `{}`).
- Field ids follow `member:<i>:<field>` and `animal:<i>:<field>`: `name`, `relationship`, `relationship_other`, `help`, `support_notes`; `category`, `type`, `type_other`, `quantity`. Buttons: "Add another person", "Remove this person", "Add another animal", "Remove this animal".
- The screen is only shown with at least one person card: the view calls `ensureFirstCards(plan, screenId)` (Task 10) so an empty plan opens with one blank first card.

- [ ] **Step 1: Write the failing tests** (`tests/wizardScreenComponents.test.js`)

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { addAnimal, addJob, addMember, addVehicle, setAnimalType, setHasVehicle, setMemberHelp, setMemberRelationship, setVehicleType } from '../src/wizard/formActions.js'
import { importComponent } from './helpers/loadComponent.js'

const screen = async (name, plan, errors = {}) =>
  renderToString(createSSRApp(await importComponent(`../src/components/wizard/screens/${name}.vue`), { plan, errors }))

const planWith = (build) => {
  const plan = createEmptyHouseholdPlan()
  build(plan)
  return plan
}

test('household: the first card is "You" without a relationship field; later cards have one', async () => {
  const plan = planWith((p) => { addMember(p).display_name = 'Maya'; addMember(p).display_name = 'Sam' })
  const html = await screen('HouseholdScreen', plan)
  assert.match(html, /Person 1/)
  assert.match(html, /Person 2/)
  assert.equal((html.match(/How is this person related to you\?/g) ?? []).length, 1)
  assert.match(html, /Add another person/)
  assert.match(html, /Remove this person/)
})

test('household: the relationship description and support notes show only when needed', async () => {
  const plain = await screen('HouseholdScreen', planWith((p) => { addMember(p); addMember(p) }))
  assert.doesNotMatch(plain, /How would you describe/)
  assert.doesNotMatch(plain, /anything else we should know/i)

  const full = await screen('HouseholdScreen', planWith((p) => {
    addMember(p)
    const b = addMember(p)
    setMemberRelationship(b, 'other')
    setMemberHelp(b, ['mobility'])
  }))
  assert.match(full, /How would you describe/)
  assert.match(full, /anything else we should know/i)
})

test('household: animals ask yes or no, then show cards with their own conditional fields', async () => {
  const none = await screen('HouseholdScreen', planWith((p) => addMember(p)))
  assert.match(none, /Do any animals leave with you\?/)
  assert.doesNotMatch(none, /How many\?/)

  const some = await screen('HouseholdScreen', planWith((p) => {
    addMember(p)
    addAnimal(p)
    setAnimalType(p.animals[0], 'other')
  }))
  assert.match(some, /How many\?/)
  assert.match(some, /What kind of animal\?/)
  assert.match(some, /Add another animal/)
  assert.match(some, /Remove this animal/)
})

test('household: errors appear beside their fields', async () => {
  const plan = planWith((p) => { addMember(p); addAnimal(p) })
  const html = await screen('HouseholdScreen', plan, { 'animal:0:quantity': 'Enter a whole number of at least 1.' })
  assert.match(html, /id="animal:0:quantity-error"[^>]*>Enter a whole number of at least 1\./)
})
```

(`addJob`, `addVehicle`, `setHasVehicle`, `setVehicleType` are imported for later tasks' tests appended to this file.)

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardScreenComponents.test.js`
Expected: FAIL (component missing).

- [ ] **Step 3: Implement** (`src/components/wizard/screens/HouseholdScreen.vue`)

```vue
<script setup>
import { ANIMAL_CATEGORIES, ANIMAL_TYPES, RELATIONSHIPS } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import {
  HELP_OPTIONS, addAnimal, addMember, memberHelpValues, setAnimalCategory, setAnimalType,
  setAnimalsAny, setMemberHelp, setMemberRelationship,
} from '../../../wizard/formActions.js'
import { removeAnimal, removeMember } from '../../../wizard/wizardDraft.js'
import YesNoQuestion from '../questions/YesNoQuestion.vue'
import CheckField from '../fields/CheckField.vue'
import NumberField from '../fields/NumberField.vue'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})

const err = (field) => props.errors[field] ?? ''
const RELATIONSHIP_OPTIONS = [['', 'Prefer not to say'], ...RELATIONSHIPS.filter(([value]) => value !== 'self')]
const animalsAnswer = () => (props.plan.animals.length > 0 ? true : null)
</script>

<template>
  <div class="screen">
    <fieldset v-for="(member, i) in plan.members" :key="member.member_id" class="card-box">
      <legend>{{ memberTitle(plan, i) }}</legend>
      <TextField
        :id="`member:${i}:name`"
        v-model="member.display_name"
        :label="i === 0 ? 'What is your name?' : 'What is their name?'"
        placeholder="e.g. Maya"
        :max-length="100"
        :error="err(`member:${i}:name`)"
      />
      <SelectField
        v-if="i > 0"
        :id="`member:${i}:relationship`"
        :label="`How is ${member.display_name?.trim() || 'this person'} related to you?`"
        :model-value="member.relationship ?? ''"
        :options="RELATIONSHIP_OPTIONS"
        @update:model-value="setMemberRelationship(member, $event)"
      />
      <TextField
        v-if="member.relationship === 'other'"
        :id="`member:${i}:relationship_other`"
        v-model="member.relationship_other"
        :label="`How would you describe ${member.display_name?.trim() || 'this person'}?`"
        placeholder="e.g. Neighbour"
        :max-length="100"
      />
      <CheckField
        :id="`member:${i}:help`"
        :label="i === 0 ? 'Do you need any extra help to leave?' : 'Do they need any extra help to leave?'"
        helper="Tick any that apply."
        :model-value="memberHelpValues(member)"
        :options="HELP_OPTIONS"
        @update:model-value="setMemberHelp(member, $event)"
      />
      <TextField
        v-if="member.is_dependant || member.mobility_support_required"
        :id="`member:${i}:support_notes`"
        v-model="member.support_notes"
        label="Is there anything else we should know?"
        placeholder="e.g. Needs medication prepared"
      />
      <button v-if="i > 0" type="button" class="btn btn-danger btn-sm" @click="removeMember(plan, member.member_id)">Remove this person</button>
    </fieldset>
    <button type="button" class="btn btn-ghost" @click="addMember(plan)">Add another person</button>

    <section class="animals" aria-labelledby="animals-title">
      <h3 id="animals-title" class="group-title">Do any animals leave with you?</h3>
      <p class="helper">Pets or livestock. Choose No if you have none.</p>
      <YesNoQuestion :current="animalsAnswer()" @answer="setAnimalsAny(plan, $event)" />

      <fieldset v-for="(animal, i) in plan.animals" :key="animal.animal_id" class="card-box">
        <legend>Animal {{ i + 1 }}</legend>
        <SelectField
          :id="`animal:${i}:category`"
          label="Is this a pet or livestock?"
          :model-value="animal.category"
          :options="ANIMAL_CATEGORIES"
          @update:model-value="setAnimalCategory(animal, $event)"
        />
        <SelectField
          :id="`animal:${i}:type`"
          label="What kind of animal is it?"
          :model-value="animal.animal_type"
          :options="ANIMAL_TYPES[animal.category] ?? ANIMAL_TYPES.pet"
          @update:model-value="setAnimalType(animal, $event)"
        />
        <TextField
          v-if="animal.animal_type === 'other'"
          :id="`animal:${i}:type_other`"
          v-model="animal.animal_type_other"
          label="What kind of animal?"
          placeholder="e.g. Ferret"
          :max-length="100"
          :error="err(`animal:${i}:type_other`)"
        />
        <NumberField :id="`animal:${i}:quantity`" v-model="animal.quantity" label="How many?" :min="1" :error="err(`animal:${i}:quantity`)" />
        <button type="button" class="btn btn-danger btn-sm" @click="removeAnimal(plan, i)">Remove this animal</button>
      </fieldset>
      <button v-if="plan.animals.length" type="button" class="btn btn-ghost" @click="addAnimal(plan)">Add another animal</button>
    </section>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
.group-title { font-size: 1.125rem; margin: 0.5rem 0 0; }
.helper { color: var(--color-text-muted); margin: 0.2rem 0 0.6rem; }
.animals { display: grid; gap: 0.9rem; }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardScreenComponents.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/screens/HouseholdScreen.vue frontend/tests/wizardScreenComponents.test.js
git commit -m "feat(frontend): household form screen"
```

---

### Task 6: Daytime and Jobs screens

**Files:**
- Create: `src/components/wizard/screens/DaytimeScreen.vue`, `JobsScreen.vue`
- Test: `tests/wizardScreenComponents.test.js` (append)

**Interfaces:**
- Both: props `plan`, `errors` as in Task 5.
- Daytime ids: `location:<i>:kind`, `location:<i>:address`. With no people it shows the text "Add the people in your household first".
- Jobs ids: `resp:<i>:task`, `resp:<i>:task_custom`, `resp:<i>:primary`, `resp:<i>:backup`. Buttons "Add another job", "Remove this job". With no people it shows "Add the people in your household first".

- [ ] **Step 1: Append the failing tests**

```js
test('daytime: one row per person, with an address field only once a place is chosen', async () => {
  const empty = await screen('DaytimeScreen', createEmptyHouseholdPlan())
  assert.match(empty, /Add the people in your household first/)

  const plan = planWith((p) => { addMember(p).display_name = 'Maya'; addMember(p).display_name = 'Sam' })
  plan.members[0].usual_location = { kind: 'work', address: '1 Main St', latitude: null, longitude: null, verification_status: 'unverified' }
  const html = await screen('DaytimeScreen', plan)
  assert.match(html, /Where are you during the day\?/)
  assert.match(html, /Where is Sam during the day\?/)
  assert.equal((html.match(/Start typing a Victorian street address/g) ?? []).length, 1)
})

test('jobs: a job shows its custom field only for "Something else"; backup excludes the main person', async () => {
  const empty = await screen('JobsScreen', createEmptyHouseholdPlan())
  assert.match(empty, /Add the people in your household first/)

  const plan = planWith((p) => {
    const a = addMember(p); a.display_name = 'Maya'
    const b = addMember(p); b.display_name = 'Sam'
    const job = addJob(p)
    job.task_name = ' '
    job.primary_member_id = a.member_id
  })
  const html = await screen('JobsScreen', plan, { 'resp:0:task_custom': 'Please describe the task.' })
  assert.match(html, /What is the job\?/)
  assert.match(html, /id="resp:0:task_custom-error"[^>]*>Please describe the task\./)
  const backup = html.slice(html.indexOf('Who covers it'))
  assert.match(backup, /Sam/)
  assert.doesNotMatch(backup, />Maya</)
  assert.match(html, /Add another job/)
  assert.match(html, /Remove this job/)

  const preset = planWith((p) => { addMember(p); addJob(p).task_name = 'Drive the household' })
  assert.doesNotMatch(await screen('JobsScreen', preset), /What is the job\?/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardScreenComponents.test.js`
Expected: FAIL (components missing).

- [ ] **Step 3: Implement**

`DaytimeScreen.vue`:

```vue
<script setup>
import { USUAL_LOCATION_KINDS } from '../../../wizard/options.js'
import { memberLabel, memberTitle } from '../../../wizard/labels.js'
import { selectUsualAddress, setUsualAddress, setUsualKind } from '../../../wizard/wizardDraft.js'
import AddressQuestion from '../questions/AddressQuestion.vue'
import SelectField from '../fields/SelectField.vue'

defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const KIND_OPTIONS = [['', 'Not sure'], ...USUAL_LOCATION_KINDS]
</script>

<template>
  <div class="screen">
    <p v-if="!plan.members.length" class="notice">Add the people in your household first. Then come back here to say where each person is during the day.</p>
    <fieldset v-for="(member, i) in plan.members" :key="member.member_id" class="card-box">
      <legend>{{ memberTitle(plan, i) }}</legend>
      <SelectField
        :id="`location:${i}:kind`"
        :label="i === 0 ? 'Where are you during the day?' : `Where is ${memberLabel(plan, i)} during the day?`"
        :model-value="member.usual_location?.kind ?? ''"
        :options="KIND_OPTIONS"
        @update:model-value="setUsualKind(member, $event)"
      />
      <AddressQuestion
        v-if="member.usual_location"
        :id="`location:${i}:address`"
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="member.usual_location.address ?? ''"
        @update:model-value="setUsualAddress(member, $event)"
        @select="selectUsualAddress(member, $event)"
      />
    </fieldset>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>
```

Note: the `Start typing a Victorian street address` placeholder in the Task 6 test comes from `AddressQuestion.vue` (it passes that placeholder to `AddressAutocompleteInput`); if the SSR output does not contain it, assert on the `What is the address?` label instead and adjust the test line.

`JobsScreen.vue`:

```vue
<script setup>
import { TASK_PRESETS } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import { addJob, setJobMain, setTaskChoice, taskChoice } from '../../../wizard/formActions.js'
import { removeResponsibility } from '../../../wizard/wizardDraft.js'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const err = (field) => props.errors[field] ?? ''
const TASK_OPTIONS = [['', 'Choose a job'], ...TASK_PRESETS.map((task) => [task, task]), ['other', 'Something else']]
const people = () => props.plan.members.map((member, index) => [member.member_id, memberTitle(props.plan, index)])
const backupOptions = (job) => [['', 'No one yet'], ...people().filter(([id]) => id !== job.primary_member_id)]
</script>

<template>
  <div class="screen">
    <p v-if="!plan.members.length" class="notice">Add the people in your household first. Then come back here to say who does what.</p>
    <template v-else>
      <fieldset v-for="(job, i) in plan.responsibilities" :key="job.responsibility_id" class="card-box">
        <legend>Job {{ i + 1 }}</legend>
        <SelectField
          :id="`resp:${i}:task`"
          label="What is one job that has to happen?"
          :model-value="taskChoice(job)"
          :options="TASK_OPTIONS"
          @update:model-value="setTaskChoice(job, $event)"
        />
        <TextField
          v-if="taskChoice(job) === 'other'"
          :id="`resp:${i}:task_custom`"
          :model-value="job.task_name.trim() ? job.task_name : ''"
          label="What is the job?"
          placeholder="e.g. Feed the chickens"
          :max-length="100"
          :error="err(`resp:${i}:task_custom`)"
          @update:model-value="job.task_name = $event === '' ? ' ' : $event"
        />
        <SelectField
          :id="`resp:${i}:primary`"
          label="Who does it?"
          :model-value="job.primary_member_id ?? ''"
          :options="[['', 'Not decided yet'], ...people()]"
          @update:model-value="setJobMain(job, $event)"
        />
        <SelectField
          :id="`resp:${i}:backup`"
          label="Who covers it if they cannot?"
          :model-value="job.backup_member_id ?? ''"
          :options="backupOptions(job)"
          :error="err(`resp:${i}:backup`)"
          @update:model-value="job.backup_member_id = $event || null"
        />
        <button type="button" class="btn btn-danger btn-sm" @click="removeResponsibility(plan, i)">Remove this job</button>
      </fieldset>
      <button type="button" class="btn btn-ghost" @click="addJob(plan)">Add another job</button>
    </template>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardScreenComponents.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/screens/DaytimeScreen.vue frontend/src/components/wizard/screens/JobsScreen.vue frontend/tests/wizardScreenComponents.test.js
git commit -m "feat(frontend): daytime and jobs form screens"
```

---

### Task 7: Vehicles and Places screens

**Files:**
- Create: `src/components/wizard/screens/VehiclesScreen.vue`, `PlacesScreen.vue`
- Test: `tests/wizardScreenComponents.test.js` (append)

**Interfaces:**
- Props as before.
- Vehicles ids: `vehicle:<i>:type`, `vehicle:<i>:type_other`, `vehicle:<i>:name`, `vehicle:<i>:drivers`, `transport:primary`, `backup:vehicles`. Question text "Do you have a vehicle you would leave in?". Buttons "Add another vehicle", "Remove this vehicle". The backup group is a `CheckField` of vehicles other than the first choice; with none it shows "Add a second vehicle to choose a backup." and an **Add another vehicle** button.
- Places ids: `place:name`, `place:address`, `place:meeting`, `backupplace:<i>:name`, `backupplace:<i>:address`. Buttons "Add another place", "Remove this place".

- [ ] **Step 1: Append the failing tests**

```js
test('vehicles: nothing but the question until the person says yes', async () => {
  const html = await screen('VehiclesScreen', createEmptyHouseholdPlan())
  assert.match(html, /Do you have a vehicle you would leave in\?/)
  assert.doesNotMatch(html, /What kind of vehicle/)
  assert.doesNotMatch(html, /Which one would you take first\?/)
})

test('vehicles: "no" hides the vehicle and backup parts', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, false)))
  assert.doesNotMatch(html, /What kind of vehicle/)
  assert.doesNotMatch(html, /backup/i)
})

test('vehicles: cards, drivers, first choice and backup on one screen', async () => {
  const plan = planWith((p) => {
    addMember(p).display_name = 'Maya'
    setHasVehicle(p, true)
    addVehicle(p)
    setVehicleType(p.transports[1], 'other')
  })
  const html = await screen('VehiclesScreen', plan, { 'vehicle:1:type_other': 'Please describe the vehicle.' })
  assert.equal((html.match(/What kind of vehicle is it\?/g) ?? []).length, 2)
  assert.match(html, /Who can drive it\?/)
  assert.match(html, /id="vehicle:1:type_other-error"[^>]*>Please describe the vehicle\./)
  assert.match(html, /Which one would you take first\?/)
  assert.match(html, /Add another vehicle/)
  assert.match(html, /Remove this vehicle/)
  assert.match(html, /If your first vehicle cannot be used/)
})

test('vehicles: with one vehicle there is nothing to back it up, and the screen says so', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, true)))
  assert.match(html, /Add a second vehicle to choose a backup\./)
})

test('vehicles: drivers are hidden when there is no one in the household', async () => {
  const html = await screen('VehiclesScreen', planWith((p) => setHasVehicle(p, true)))
  assert.doesNotMatch(html, /Who can drive it\?/)
})

test('places: destination, address and meeting point, then backup places', async () => {
  const plan = planWith((p) => {
    p.arrangements.primary_destination = { destination_id: 'd1', display_name: "Nan's house", address: null }
    p.arrangements.backup_arrangements = [{ transport_id: null, destination: { destination_id: 'd2', display_name: 'Hall', address: null } }]
  })
  const html = await screen('PlacesScreen', plan)
  assert.match(html, /Where would you go\?/)
  assert.match(html, /If your household is separated, where would you meet\?/)
  assert.match(html, /Where would you go instead\?/)
  assert.match(html, /Add another place/)
  assert.match(html, /Remove this place/)
})

test('places: a plan with no places still shows the destination fields and an add button', async () => {
  const html = await screen('PlacesScreen', createEmptyHouseholdPlan())
  assert.match(html, /Where would you go\?/)
  assert.match(html, /Add another place/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardScreenComponents.test.js`
Expected: FAIL (components missing).

- [ ] **Step 3: Implement**

`VehiclesScreen.vue`:

```vue
<script setup>
import { TRANSPORT_TYPES, transportLabel } from '../../../wizard/options.js'
import { memberTitle } from '../../../wizard/labels.js'
import { addVehicle, setFirstVehicle, setHasVehicle, setVehicleType } from '../../../wizard/formActions.js'
import { backupTransportIds, removeTransport, setBackupTransports } from '../../../wizard/wizardDraft.js'
import YesNoQuestion from '../questions/YesNoQuestion.vue'
import CheckField from '../fields/CheckField.vue'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const err = (field) => props.errors[field] ?? ''
const driverOptions = () => props.plan.members.map((member, index) => [member.member_id, memberTitle(props.plan, index)])
const firstOptions = () => [['', 'Not sure yet'], ...props.plan.transports.map((t) => [t.transport_id, transportLabel(t)])]
const firstId = () => props.plan.arrangements?.primary_transport_id ?? ''
const backupCandidates = () =>
  props.plan.transports.filter((t) => t.transport_id !== firstId()).map((t) => [t.transport_id, transportLabel(t)])
</script>

<template>
  <div class="screen">
    <section aria-labelledby="has-vehicle">
      <h3 id="has-vehicle" class="group-title">Do you have a vehicle you would leave in?</h3>
      <YesNoQuestion :current="plan.has_private_transport ?? null" @answer="setHasVehicle(plan, $event)" />
    </section>

    <template v-if="plan.has_private_transport === true">
      <fieldset v-for="(vehicle, i) in plan.transports" :key="vehicle.transport_id" class="card-box">
        <legend>Vehicle {{ i + 1 }}</legend>
        <SelectField
          :id="`vehicle:${i}:type`"
          label="What kind of vehicle is it?"
          :model-value="vehicle.transport_type"
          :options="TRANSPORT_TYPES"
          @update:model-value="setVehicleType(vehicle, $event)"
        />
        <TextField
          v-if="vehicle.transport_type === 'other'"
          :id="`vehicle:${i}:type_other`"
          v-model="vehicle.transport_type_other"
          label="What kind of vehicle?"
          placeholder="e.g. Tractor"
          :max-length="100"
          :error="err(`vehicle:${i}:type_other`)"
        />
        <TextField
          :id="`vehicle:${i}:name`"
          v-model="vehicle.display_name"
          label="What do you call it?"
          helper="For example Dad's ute. Optional."
          placeholder="Optional"
          :max-length="100"
        />
        <CheckField
          v-if="plan.members.length"
          :id="`vehicle:${i}:drivers`"
          label="Who can drive it?"
          helper="Tick everyone who could drive it."
          v-model="vehicle.driver_member_ids"
          :options="driverOptions()"
        />
        <button type="button" class="btn btn-danger btn-sm" @click="removeTransport(plan, vehicle.transport_id)">Remove this vehicle</button>
      </fieldset>
      <button type="button" class="btn btn-ghost" @click="addVehicle(plan)">Add another vehicle</button>

      <SelectField
        v-if="plan.transports.length"
        id="transport:primary"
        label="Which one would you take first?"
        :model-value="firstId()"
        :options="firstOptions()"
        @update:model-value="setFirstVehicle(plan, $event)"
      />

      <CheckField
        v-if="backupCandidates().length"
        id="backup:vehicles"
        label="If your first vehicle cannot be used, which others could you take?"
        :model-value="backupTransportIds(plan)"
        :options="backupCandidates()"
        @update:model-value="setBackupTransports(plan, $event)"
      />
      <p v-else-if="plan.transports.length" class="notice">Add a second vehicle to choose a backup.</p>
    </template>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.group-title { font-size: 1.125rem; margin: 0 0 0.6rem; }
.notice { color: var(--color-text-muted); }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>
```

When the first vehicle is chosen, a vehicle selected as backup should not also be first: in the screen the `backupCandidates()` list excludes it, and `setFirstVehicle` is followed by the view's finalise step which drops nothing. To keep data clean, change `setFirstVehicle` in `formActions.js` (Task 2) so that it also removes the chosen id from the backup vehicle choices:

```js
export function setFirstVehicle(plan, id) {
  plan.arrangements ??= {}
  plan.arrangements.primary_transport_id = id || null
  if (id) setBackupTransports(plan, backupTransportIds(plan).filter((backup) => backup !== id))
}
```

(add `backupTransportIds, setBackupTransports` to the `wizardDraft.js` import in `formActions.js`; add a test to `tests/wizardFormActions.test.js`: choosing a vehicle as first removes it from the backups.)

`PlacesScreen.vue`:

```vue
<script setup>
import { addBackupPlace } from '../../../wizard/formActions.js'
import {
  backupDestination, primaryDestination, removeBackupPlace, selectDestinationAddress, setDestinationAddress,
} from '../../../wizard/wizardDraft.js'
import AddressQuestion from '../questions/AddressQuestion.vue'
import TextField from '../fields/TextField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
})
const primary = () => props.plan.arrangements?.primary_destination ?? null
const backups = () => (props.plan.arrangements?.backup_arrangements ?? [])
  .map((entry, index) => ({ entry, index }))
  .filter(({ entry }) => entry.destination)

function setPrimaryName(value) {
  primaryDestination(props.plan).display_name = value
}
function setMeeting(value) {
  props.plan.arrangements ??= {}
  props.plan.arrangements.meeting_point = value || null
}
function addPlace() {
  const entry = addBackupPlace(props.plan)
  backupDestination(props.plan, props.plan.arrangements.backup_arrangements.indexOf(entry))
}
</script>

<template>
  <div class="screen">
    <fieldset class="card-box">
      <legend>Where you would go</legend>
      <TextField
        id="place:name"
        :model-value="primary()?.display_name ?? ''"
        label="Where would you go?"
        helper="A name you would recognise, such as Nan's house."
        placeholder="e.g. Relative's house"
        :max-length="100"
        @update:model-value="setPrimaryName"
      />
      <AddressQuestion
        v-if="primary()"
        id="place:address"
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="primary().address ?? ''"
        @update:model-value="setDestinationAddress(primary(), $event)"
        @select="selectDestinationAddress(primary(), $event)"
      />
      <TextField
        id="place:meeting"
        :model-value="plan.arrangements?.meeting_point ?? ''"
        label="If your household is separated, where would you meet?"
        helper="Optional."
        placeholder="e.g. Front gate"
        :max-length="200"
        @update:model-value="setMeeting"
      />
    </fieldset>

    <fieldset v-for="({ entry, index }, n) in backups()" :key="entry.destination.destination_id" class="card-box">
      <legend>Backup place {{ n + 1 }}</legend>
      <TextField
        :id="`backupplace:${index}:name`"
        v-model="entry.destination.display_name"
        :label="n === 0 ? 'If you could not go there, where would you go instead?' : 'Where else could you go?'"
        placeholder="e.g. Community centre"
        :max-length="100"
      />
      <AddressQuestion
        :id="`backupplace:${index}:address`"
        label="What is the address?"
        helper="Pick a suggestion, or type it in if it is not listed."
        :model-value="entry.destination.address ?? ''"
        @update:model-value="setDestinationAddress(entry.destination, $event)"
        @select="selectDestinationAddress(entry.destination, $event)"
      />
      <button type="button" class="btn btn-danger btn-sm" @click="removeBackupPlace(plan, index)">Remove this place</button>
    </fieldset>
    <button type="button" class="btn btn-ghost" @click="addPlace">Add another place</button>
  </div>
</template>

<style scoped>
.screen { display: grid; gap: 1.1rem; }
.card-box { border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.9rem; margin: 0; min-width: 0; padding: 1rem; }
.card-box legend { font-weight: 800; padding: 0 0.4rem; }
</style>
```

The test above expects the text "Where would you go instead?"; the screen's first backup label is "If you could not go there, where would you go instead?", which contains it. Adjust the test regexp to `/where would you go instead\?/i` if the capital W fails.

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardScreenComponents.test.js tests/wizardFormActions.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/screens frontend/src/wizard/formActions.js frontend/tests/wizardScreenComponents.test.js frontend/tests/wizardFormActions.test.js
git commit -m "feat(frontend): vehicles and places form screens"
```

---

### Task 8: Screen shell

**Files:**
- Create: `src/components/wizard/ScreenShell.vue`
- Test: `tests/wizardShell.test.js`

**Interfaces:**
- Props: `screen` (a `SCREENS` item), `position` (number, 1-based), `total` (number), `errors` (array of `{field,message}`), `saveError` (string|null), `saving` (boolean), `isEdit` (boolean), `canGoBack` (boolean).
- Emits: `save`, `skip`, `back`.
- Renders: a "Part N of M" line, the screen title as `h2` with `id="wizard-prompt"`, the default slot, an error summary (`role="alert"`, with links to the first and each invalid field), and the buttons Back (when `canGoBack`), Skip for now, and **Save and continue** (or **Save and return to review** when `isEdit`, **Saving…** while saving).

- [ ] **Step 1: Write the failing test** (`tests/wizardShell.test.js`)

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { SCREENS } from '../src/wizard/screens.js'
import { importComponent } from './helpers/loadComponent.js'

const render = async (props) => {
  const Shell = await importComponent('../src/components/wizard/ScreenShell.vue')
  return renderToString(createSSRApp({ render: () => h(Shell, { screen: SCREENS[2], position: 3, total: 5, errors: [], saveError: null, saving: false, isEdit: false, canGoBack: true, ...props }, { default: () => h('p', 'FORM') }) }))
}

test('the shell shows the part, the title and the form', async () => {
  const html = await render()
  assert.match(html, /Part 3 of 5/)
  assert.match(html, /<h2[^>]*id="wizard-prompt"[^>]*>How you would leave<\/h2>/)
  assert.match(html, /FORM/)
  assert.match(html, /Save and continue/)
  assert.match(html, /Skip for now/)
  assert.match(html, />Back</)
})

test('editing from review changes the save label; saving disables it', async () => {
  assert.match(await render({ isEdit: true }), /Save and return to review/)
  const saving = await render({ saving: true })
  assert.match(saving, /Saving…/)
  assert.match(saving, /disabled/)
})

test('the first screen has no Back button', async () => {
  assert.doesNotMatch(await render({ canGoBack: false }), />Back</)
})

test('validation errors are summarised as an alert with links to their fields', async () => {
  const html = await render({ errors: [{ field: 'vehicle:1:type_other', message: 'Please describe the vehicle.' }] })
  assert.match(html, /role="alert"/)
  assert.match(html, /href="#vehicle:1:type_other"[^>]*>Please describe the vehicle\./)
})

test('a failed save is shown as an alert', async () => {
  assert.match(await render({ saveError: 'Your plan could not be saved.' }), /role="alert"[^>]*>Your plan could not be saved\./)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardShell.test.js`
Expected: FAIL (component missing).

- [ ] **Step 3: Implement** (`src/components/wizard/ScreenShell.vue`)

```vue
<script setup>
defineProps({
  screen: { type: Object, required: true },
  position: { type: Number, required: true },
  total: { type: Number, required: true },
  errors: { type: Array, default: () => [] },
  saveError: { type: String, default: null },
  saving: { type: Boolean, default: false },
  isEdit: { type: Boolean, default: false },
  canGoBack: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'skip', 'back'])
</script>

<template>
  <section class="shell" aria-labelledby="wizard-prompt">
    <p class="where">Part {{ position }} of {{ total }}</p>
    <h2 id="wizard-prompt" class="title" tabindex="-1">{{ screen.title }}</h2>

    <form class="body" novalidate @submit.prevent="emit('save')">
      <slot />

      <div v-if="errors.length" class="summary" role="alert">
        <p class="summary-title">Please fix this before saving:</p>
        <ul>
          <li v-for="item in errors" :key="item.field"><a :href="`#${item.field}`">{{ item.message }}</a></li>
        </ul>
      </div>
      <p v-if="saveError" class="field-error" role="alert">{{ saveError }}</p>

      <div class="controls">
        <button v-if="canGoBack" type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
        <span class="spacer"></span>
        <button type="button" class="btn btn-ghost" @click="emit('skip')">Skip for now</button>
        <button type="submit" class="btn btn-accent" :disabled="saving">
          {{ saving ? 'Saving…' : isEdit ? 'Save and return to review' : 'Save and continue' }}
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.shell { display: grid; gap: 1rem; }
.where { color: var(--color-text-muted); font-size: 0.875rem; font-weight: 700; margin: 0; }
.title { font-size: clamp(1.5rem, 4vw, 2.1rem); margin: 0; }
.body { display: grid; gap: 1.1rem; }
.summary { background: var(--color-bg-card-muted); border: 2px solid var(--color-border-strong); border-radius: 12px; padding: 0.8rem 1rem; }
.summary-title { font-weight: 800; margin: 0 0 0.3rem; }
.summary ul { margin: 0; padding-left: 1.2rem; }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.spacer { flex: 1 1 0; }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardShell.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/ScreenShell.vue frontend/tests/wizardShell.test.js
git commit -m "feat(frontend): shell for the compact wizard screens"
```

---

### Task 9: Progress bar and Review screen

**Files:**
- Modify: `src/components/wizard/ProgressBar.vue`, `src/components/wizard/ReviewScreen.vue`
- Test: `tests/wizardComponents.test.js` (rewrite the progress and review tests; Task 11 removes the shell tests)

**Interfaces:**
- `ProgressBar` props: `completion`, `currentScreen` (screen id or null), `loading`. Text: "N of 5 parts complete"; `aria-valuemax="5"`; each marker shows `short` and Complete / Needs information from `screenComplete`.
- `ReviewScreen` props: `plan`, `completion`, `completionLoading`, `saving`, `error` (the `editable` prop is removed). One row per screen: title, `describeScreen`, badge (`Complete` only when `screenComplete`), and an **Edit** button for every row. Emits `edit(screenId)` and `finish`.

- [ ] **Step 1: Write the failing tests** (replace the ProgressBar and ReviewScreen tests in `tests/wizardComponents.test.js`; change its imports to `SCREENS`)

```js
import { SCREENS } from '../src/wizard/screens.js'
import { addAnimal, addMember, setHasVehicle } from '../src/wizard/formActions.js'

const sectionsDone = (done) => ({
  sections: SCREENS.flatMap((screen) => screen.sections).map((section, index) => ({
    section, status: index < done ? 'complete' : 'needs_information',
  })),
  immediate_checks: [],
})

test('the progress bar reports N of 5 in text, in ARIA, and per screen', async () => {
  // Four backend sections done: household, daytime, both vehicle sections.
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: sectionsDone(4), currentScreen: 'places', loading: false,
  })
  assert.match(html, /role="progressbar"/)
  assert.match(html, /aria-valuenow="3"/)
  assert.match(html, /aria-valuemax="5"/)
  assert.match(html, /3 of 5 parts complete/)
  assert.match(html, /aria-current="step"/)
  for (const label of ['Household', 'Daytime', 'Vehicles', 'Places', 'Jobs']) assert.match(html, new RegExp(label))
})

test('a screen with one unfinished section is not counted complete', async () => {
  // Three done: household, daytime, transport; backup_transport is not.
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: sectionsDone(3), currentScreen: null, loading: false,
  })
  assert.match(html, /2 of 5 parts complete/)
})

test('the progress bar shows 0 of 5 before the first save', async () => {
  const html = await render('../src/components/wizard/ProgressBar.vue', { completion: null, currentScreen: 'household', loading: false })
  assert.match(html, /0 of 5 parts complete/)
})

test('review lists five rows, each with an Edit button and an honest status', async () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan).display_name = 'Maya'
  addAnimal(plan)
  setHasVehicle(plan, false)
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: sectionsDone(2), completionLoading: false, saving: false, error: null,
  })
  assert.equal((html.match(/>Edit</g) ?? []).length, 5)
  assert.match(html, /Maya/)
  assert.match(html, /No private vehicle/)
  assert.equal((html.match(/Complete/g) ?? []).length, 2)
  assert.match(html, /Save &amp; Review Plan/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardComponents.test.js`
Expected: FAIL (old components still use `SECTIONS`/7).

- [ ] **Step 3: Implement**

`ProgressBar.vue`, script and template changes:

```vue
<script setup>
import { computed } from 'vue'
import { SCREENS, screenComplete } from '../../wizard/screens'

const props = defineProps({
  completion: { type: Object, default: null },
  currentScreen: { type: String, default: null },
  loading: { type: Boolean, default: false },
})

const statuses = computed(() =>
  SCREENS.map((screen) => ({
    ...screen,
    complete: screenComplete(props.completion, screen.id),
    current: screen.id === props.currentScreen,
  })),
)
const done = computed(() => statuses.value.filter((item) => item.complete).length)
const total = SCREENS.length
const text = computed(() => `${done.value} of ${total} parts complete`)
</script>
```

Keep the template as it is; change `aria-label` to `Plan completion` (unchanged), and in the style change `repeat(7, minmax(0, 1fr))` to `repeat(5, minmax(0, 1fr))`.

`ReviewScreen.vue`:

```vue
<script setup>
import { SCREENS, screenComplete } from '../../wizard/screens'
import { describeScreen } from '../../wizard/summaries'
import LoadingState from '../common/LoadingState.vue'
import PlanChecks from '../completion/PlanChecks.vue'

defineProps({
  plan: { type: Object, required: true },
  completion: { type: Object, default: null },
  completionLoading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: null },
})
const emit = defineEmits(['edit', 'finish'])
</script>
```

In the template, loop `v-for="screen in SCREENS"` with `:key="screen.id"`; title `{{ screen.title }}`; text `{{ describeScreen(plan, screen.id) }}`; badge uses `screenComplete(completion, screen.id)`; the Edit button is always rendered and emits `edit` with `screen.id`. The helper text becomes "Check each part. Use Edit to change anything." (unchanged). Keep the styles.

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardComponents.test.js`
Expected: PASS for the progress and review tests. The old `WizardShell` tests in this file still pass until Task 11 deletes them.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/ProgressBar.vue frontend/src/components/wizard/ReviewScreen.vue frontend/tests/wizardComponents.test.js
git commit -m "feat(frontend): five-part progress bar and review"
```

---

### Task 10: Plan builder view

**Files:**
- Modify: `src/views/PlanBuilderView.vue`
- Test: `tests/wizardView.test.js` (rewrite)

**Interfaces:**
- Consumes everything above plus `useHouseholdStore`, `saveAndReview`, router.
- Behaviour:
  - State: `draft`, `screenId` (`'review'` or a screen id), `returnToReview`, `saveMessage`, `errors` (array).
  - `ensureFirstCards(plan, id)` is a small function in the view's script (not exported): for `household` ensure `plan.members.length >= 1` with `addMember`; for `places` ensure `primaryDestination(plan)` exists; for `jobs` ensure one job with `addJob` when there is at least one person. These never make the plan dirty because the dirty check compares finalised clones.
  - `hasUnsavedChanges` = `JSON.stringify(finalisedClone(draft)) !== JSON.stringify(finalisedClone(householdStore.plan))`.
  - `chooseStartingStep`: `resolveScreenParam(route.query.section)` first (`'review'` goes to Review); no plan, first screen; first incomplete screen from `firstIncompleteScreen(householdStore.completion)`; else Review when completion is loaded, else the first screen.
  - `saveScreen`: `finalisePlan(draft.value)`, then `validateScreen(draft.value, screenId)`; if errors, set `errors`, focus the first invalid control and stop; otherwise `save()` and move to `nextScreen` (or Review when `returnToReview`, which is then cleared).
  - `skip`: move to `nextScreen` without validating or saving. `back`: Review when `returnToReview` (clear it), otherwise `previousScreen`.
  - `editScreen(id)`: `returnToReview = true`, clear errors and `saveMessage`, go to the screen.
  - `errors` as an object for the screens: `computed(() => Object.fromEntries(errors.value.map((e) => [e.field, e.message])))`.
  - Keep `onBeforeRouteLeave`, `beforeunload`, `reviewPlan`, `save` (single `householdStore.savePlan(draft.value)` call site), `resetDraft`.

- [ ] **Step 1: Write the failing tests** (replace `tests/wizardView.test.js`)

```js
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')
const view = () => source('../src/views/PlanBuilderView.vue')

test('the plan view hosts the five screens, the shell, the progress bar and review', async () => {
  const text = await view()
  for (const name of ['ScreenShell', 'ProgressBar', 'ReviewScreen', 'HouseholdScreen', 'DaytimeScreen', 'VehiclesScreen', 'PlacesScreen', 'JobsScreen']) {
    assert.match(text, new RegExp(`import ${name} from`))
  }
})

test('the view saves only through the household store, once, after finalising and validating', async () => {
  const text = await view()
  assert.equal((text.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  const save = text.slice(text.indexOf('async function saveScreen'))
  assert.ok(save.indexOf('finalisePlan(') < save.indexOf('validateScreen('))
  assert.ok(save.indexOf('validateScreen(') < save.indexOf('await save()'))
})

test('the starting screen comes from the section parameter, then the first incomplete screen', async () => {
  const text = await view()
  assert.match(text, /resolveScreenParam\(route\.query\.section\)/)
  assert.match(text, /firstIncompleteScreen\(householdStore\.completion\)/)
})

test('unsaved answers are compared on finalised clones and guarded on reload and on leaving the route', async () => {
  const text = await view()
  assert.match(text, /finalisedClone\(draft\.value\)/)
  assert.match(text, /finalisedClone\(householdStore\.plan\)/)
  assert.match(text, /beforeunload/)
  assert.match(text, /onBeforeRouteLeave/)
  assert.match(text, /removeEventListener\('beforeunload'/)
})

test('editing from review returns to review after saving, and Back returns there too', async () => {
  const text = await view()
  assert.match(text, /function editScreen/)
  assert.match(text, /returnToReview\.value = true/)
  assert.match(text, /goTo\('review'\)/)
  const back = text.slice(text.indexOf('function back'), text.indexOf('function back') + 200)
  assert.match(back, /returnToReview/)
})

test('the old question flow is gone from the view', async () => {
  const text = await view()
  assert.doesNotMatch(text, /WizardShell|SectionSummary|useWizard|buildSteps|HouseholdMembersForm/)
})

test('the final action label lives on the review screen', async () => {
  assert.match(await source('../src/components/wizard/ReviewScreen.vue'), /Save &amp; Review Plan/)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test tests/wizardView.test.js`
Expected: FAIL (view still the old one).

- [ ] **Step 3: Implement** — rewrite `src/views/PlanBuilderView.vue`

```vue
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ProgressBar from '../components/wizard/ProgressBar.vue'
import ReviewScreen from '../components/wizard/ReviewScreen.vue'
import ScreenShell from '../components/wizard/ScreenShell.vue'
import DaytimeScreen from '../components/wizard/screens/DaytimeScreen.vue'
import HouseholdScreen from '../components/wizard/screens/HouseholdScreen.vue'
import JobsScreen from '../components/wizard/screens/JobsScreen.vue'
import PlacesScreen from '../components/wizard/screens/PlacesScreen.vue'
import VehiclesScreen from '../components/wizard/screens/VehiclesScreen.vue'
import { addJob, addMember } from '../wizard/formActions'
import { SCREENS, firstIncompleteScreen, nextScreen, previousScreen, resolveScreenParam } from '../wizard/screens'
import { finalisePlan, finalisedClone, validateScreen } from '../wizard/validation'
import { primaryDestination } from '../wizard/wizardDraft'
import { saveAndReview } from '../utils/planReviewNavigation'

const householdStore = useHouseholdStore()
const route = useRoute()
const router = useRouter()

const SCREEN_COMPONENTS = {
  household: HouseholdScreen,
  daytime: DaytimeScreen,
  vehicles: VehiclesScreen,
  places: PlacesScreen,
  jobs: JobsScreen,
}

const draft = ref(null)
const screenId = ref('review')
const returnToReview = ref(false)
const saveMessage = ref(null)
const errors = ref([])

function resetDraft() {
  // The wizard edits this detached aggregate. Restoring the server plan after a
  // load or save makes the unsaved comparison clean. JSON cloning is safe because
  // HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

// A screen opens with its first card showing. These blank cards are dropped
// again by finalisePlan, so opening a screen is never an unsaved change.
function ensureFirstCards(plan, id) {
  if (id === 'household' && !plan.members.length) addMember(plan)
  if (id === 'places') primaryDestination(plan)
  if (id === 'jobs' && plan.members.length && !plan.responsibilities.length) addJob(plan)
}

function goTo(id) {
  errors.value = []
  if (id !== 'review' && draft.value) ensureFirstCards(draft.value, id)
  screenId.value = id
}

function chooseStartingStep() {
  const requested = resolveScreenParam(route.query.section)
  if (requested) return goTo(requested)
  if (!householdStore.planExists) return goTo(SCREENS[0].id)
  const incomplete = firstIncompleteScreen(householdStore.completion)
  if (incomplete) return goTo(incomplete)
  return goTo(householdStore.completion ? 'review' : SCREENS[0].id)
}

onMounted(async () => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  resetDraft()
  chooseStartingStep()
})

onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload))

watch(
  () => householdStore.plan,
  () => {
    // A plan that arrives after mount (a retry after an error, or a load that
    // finished late) still opens at the right place.
    if (draft.value) return
    resetDraft()
    if (draft.value) chooseStartingStep()
  },
)

const hasUnsavedChanges = computed(() => {
  // A failed save leaves `householdStore.plan` unchanged, so the draft stays
  // dirty and can be retried without losing answers. Blank cards do not count.
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(finalisedClone(draft.value)) !== JSON.stringify(finalisedClone(householdStore.plan))
})

function warnBeforeUnload(event) {
  if (!hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!hasUnsavedChanges.value) return true
  return window.confirm('You have answers that are not saved yet. Leave this page anyway?')
})

const saving = computed(() => householdStore.saveStatus === 'loading')
const currentScreen = computed(() => SCREENS.find((screen) => screen.id === screenId.value) ?? null)
const screenIndex = computed(() => SCREENS.findIndex((screen) => screen.id === screenId.value))
const errorMap = computed(() => Object.fromEntries(errors.value.map((item) => [item.field, item.message])))

async function save() {
  if (!draft.value || saving.value) return false
  await householdStore.savePlan(draft.value)
  if (householdStore.saveStatus !== 'success') {
    saveMessage.value = householdStore.saveError || 'Your plan could not be saved. Please try again.'
    return false
  }
  saveMessage.value = null
  resetDraft()
  return true
}

async function saveScreen() {
  const id = screenId.value
  finalisePlan(draft.value)
  errors.value = validateScreen(draft.value, id)
  if (errors.value.length) {
    await nextTick()
    document.getElementById(errors.value[0].field)?.focus()
    return
  }
  if (!(await save())) return
  if (returnToReview.value) {
    returnToReview.value = false
    goTo('review')
    return
  }
  goTo(nextScreen(id))
}

function skip() {
  goTo(nextScreen(screenId.value))
}

function back() {
  if (returnToReview.value) {
    returnToReview.value = false
    goTo('review')
    return
  }
  goTo(previousScreen(screenId.value) ?? screenId.value)
}

function editScreen(id) {
  returnToReview.value = true
  saveMessage.value = null
  goTo(id)
}

async function reviewPlan() {
  await saveAndReview({
    needsSave: hasUnsavedChanges.value || !householdStore.planExists,
    save,
    navigate: (path) => router.push(path),
  })
}
</script>

<template>
  <div class="plan-wizard">
    <ProgressBar
      :completion="householdStore.completion"
      :current-screen="currentScreen?.id ?? null"
      :loading="householdStore.completionStatus === 'loading'"
    />

    <div class="stage">
      <LoadingState v-if="householdStore.planStatus === 'loading' || householdStore.planStatus === 'idle'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft">
        <ReviewScreen
          v-if="screenId === 'review'"
          :plan="draft"
          :completion="householdStore.completion"
          :completion-loading="householdStore.completionStatus === 'loading'"
          :saving="saving"
          :error="saveMessage"
          @edit="editScreen"
          @finish="reviewPlan"
        />

        <ScreenShell
          v-else-if="currentScreen"
          :key="currentScreen.id"
          :screen="currentScreen"
          :position="screenIndex + 1"
          :total="SCREENS.length"
          :errors="errors"
          :save-error="saveMessage"
          :saving="saving"
          :is-edit="returnToReview"
          :can-go-back="returnToReview || screenIndex > 0"
          @save="saveScreen"
          @skip="skip"
          @back="back"
        >
          <component :is="SCREEN_COMPONENTS[currentScreen.id]" :plan="draft" :errors="errorMap" />
        </ScreenShell>
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan-wizard { display: grid; gap: 1.75rem; margin: 0 auto; max-width: 44rem; width: 100%; }
.stage { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 28px; box-shadow: var(--shadow-card); min-width: 0; padding: clamp(1.25rem, 4vw, 2.25rem); }
</style>
```

The failed-save case keeps the draft, so Review Focus 5 holds: editing from Review changes the draft only; `save()` sends the whole finalised draft (including other unsaved answers) and only then resets it.

- [ ] **Step 4: Run to verify pass**

Run: `node --test tests/wizardView.test.js && npm run build`
Expected: tests PASS; build succeeds (the old modules still exist and are unused).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/PlanBuilderView.vue frontend/tests/wizardView.test.js
git commit -m "feat(frontend): plan builder uses the five form screens"
```

---

### Task 11: Remove the old question flow

**Files:**
- Delete: `src/wizard/flow.js`, `navigation.js`, `useWizard.js`, `step.js`, `pick.js`, `src/wizard/sections/` (all), `src/components/wizard/WizardShell.vue`, `SectionSummary.vue`, `src/components/wizard/questions/ChoiceQuestion.vue`, `MultiQuestion.vue`, `TextQuestion.vue`, `NumberQuestion.vue`
- Delete tests: `tests/wizardUseWizard.test.js`, `wizardProfileSteps.test.js`, `wizardTransportSteps.test.js`, `wizardPlaceSteps.test.js`, `wizardNavigation.test.js`, `wizardPick.test.js`
- Modify: `tests/wizardComponents.test.js` (remove the `WizardShell` and question tests that remain), `tests/wizardDraft.test.js` (remove any import of deleted modules)
- Modify: `src/wizard/summaries.js` only if it still imports `flow.js` (it imports `screens.js` since Task 3)

- [ ] **Step 1: Confirm nothing outside the deleted set imports the old modules**

Run: `grep -rn "wizard/flow\|wizard/navigation\|useWizard\|wizard/step\|wizard/pick\|WizardShell\|SectionSummary\|ChoiceQuestion\|MultiQuestion\|TextQuestion\|NumberQuestion\|wizard/sections" src tests`
Expected: matches only inside the files listed above for deletion.

- [ ] **Step 2: Delete the files and fix the remaining tests**

```bash
git rm -r frontend/src/wizard/flow.js frontend/src/wizard/navigation.js frontend/src/wizard/useWizard.js \
  frontend/src/wizard/step.js frontend/src/wizard/pick.js frontend/src/wizard/sections \
  frontend/src/components/wizard/WizardShell.vue frontend/src/components/wizard/SectionSummary.vue \
  frontend/src/components/wizard/questions/ChoiceQuestion.vue frontend/src/components/wizard/questions/MultiQuestion.vue \
  frontend/src/components/wizard/questions/TextQuestion.vue frontend/src/components/wizard/questions/NumberQuestion.vue \
  frontend/tests/wizardUseWizard.test.js frontend/tests/wizardProfileSteps.test.js \
  frontend/tests/wizardTransportSteps.test.js frontend/tests/wizardPlaceSteps.test.js \
  frontend/tests/wizardNavigation.test.js frontend/tests/wizardPick.test.js
```

Edit `tests/wizardComponents.test.js`: delete the tests that render `WizardShell` or the question components, and delete the `buildSteps` import; keep the progress bar and review tests from Task 9.

- [ ] **Step 3: Run the whole suite and the build**

Run: `npm test && npm run build`
Expected: all frontend tests PASS; build succeeds. If a test fails because it imported a deleted helper, remove that import or test; do not restore the deleted file.

- [ ] **Step 4: Commit**

```bash
git add -A frontend
git commit -m "refactor(frontend): remove the one-question wizard flow"
```

---

### Task 12: Spec corrections, manual check and branch finish

**Files:**
- Modify: `docs/design/specs/2026-10-12-wizard-compact-design.md`
- Create: `docs/design/wizard-compact-manual-check.md`

- [ ] **Step 1: Correct the spec to match the rulings**

In the spec's "Rules (carried over unchanged)" first bullet, replace it with: "An animal kind, vehicle type or job described as 'Something else' needs a description. A relationship of 'Other' keeps an optional description, as today." In "Saving and validation", replace the blank-card sentence with: "**Save and continue** first drops any person, job, destination or backup-place card that was opened but never filled in (animal and vehicle cards hold default values and count as filled; use Remove), trims typed names, then validates, then saves." In the Review Focus list, change item 4 to "A person, job, destination or backup-place card left blank is not saved as an empty record, and opening a screen is not an unsaved change."

- [ ] **Step 2: Write the manual check** (`docs/design/wizard-compact-manual-check.md`) with these cases, each as a checkbox with the expected result:
  1. New household: five screens in order; progress bar shows five parts; Save and continue on each.
  2. Vehicles: answer yes, add a second vehicle with type "Other" and leave the description blank: Save is blocked with the message and focus lands on the field.
  3. Vehicles: choose a first vehicle; it disappears from the backup choices; tick a backup; save; reload; both persist.
  4. Vehicles: answer no with vehicles saved: vehicles disappear and the plan saves with "No private vehicle".
  5. Jobs: choose "Something else", leave blank, save: blocked; type a name, save: succeeds. Choose the same person as main and backup: the backup clears.
  6. Review: five rows with correct status; Edit on Vehicles opens that screen with every answer visible; change one name; Save and return to review returns to Review.
  7. Edit then Back returns to Review without saving.
  8. Opening a screen and leaving without typing shows no unsaved-changes warning; typing something and leaving does.
  9. `/plan?section=transport`, `?section=people`, `?section=review` land on Vehicles, Household, Review.
  10. Phone width: cards are single column and nothing scrolls sideways; keyboard-only: Tab reaches every field and button with a visible focus ring; the error summary links jump to the field.
  11. Voice: "go to my plan" still opens `/plan`.

- [ ] **Step 3: Run the whole suite and the build one last time**

Run: `npm test && npm run build`
Expected: PASS and build OK.

- [ ] **Step 4: Commit**

```bash
git add docs/design/specs/2026-10-12-wizard-compact-design.md docs/design/wizard-compact-manual-check.md
git commit -m "docs: align the compact wizard spec with the plan and add a manual check"
```

- [ ] **Step 5: Final whole-branch review**, then use superpowers:finishing-a-development-branch. Do not push or open a PR without the user asking.
