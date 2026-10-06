# Plan Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four-form stepper at `/plan` with a strict one-question-at-a-time wizard, a completion progress bar, and a Review screen with per-section Edit.

**Architecture:** A pure, data-driven flow (`wizard/flow.js` builds an ordered list of steps from the current draft plan; each step carries its own `read`/`write`/`validate`). A small composable (`wizard/useWizard.js`) tracks the current step key. Vue components only render a step and emit events. The view keeps the detached draft and the explicit per-section save through the unchanged `householdStore`. No backend or API change.

**Tech Stack:** Vue 3.5 (`<script setup>`), Pinia, vue-router 5, plain JavaScript, Node's built-in test runner (`node --test`), `@vue/compiler-sfc` + `vue/server-renderer` for component render tests.

**Spec:** `docs/design/specs/2026-10-07-plan-wizard-design.md`

## Global Constraints

- Plain JavaScript, no TypeScript. No new runtime dependency.
- Frontend only. Do not touch `backend/`, `database/`, `data/`, or `docs/iteration1-integration-contract.md`.
- Never fabricate data: an unskipped answer is written exactly as given; a skipped question writes nothing. Typed addresses stay unverified (null coordinates) until the backend resolves them; selecting a suggestion sets `selected_address`.
- Incomplete plans are always saveable: **every question has "Skip for now"**, and a failed question never blocks Save.
- Completion is read from `householdStore.completion` (backend-derived from the saved plan). Do not recompute completion in the browser.
- Public IDs come from `newId` in `src/api/client.js` (`m_`, `a_`, `t_`, `r_`, `d_` prefixes).
- Do not word anything as prediction (no "risk", "likely", "will be safe").
- Controls are at least 44px tall; focus ring and reduced-motion rules already live in `src/style.css` and must not be bypassed.
- Tests: `cd frontend && npm test` must stay green after every task. Commits use conventional messages with a scope, e.g. `feat(frontend): ...`.
- Do not add attribution lines to commit messages.

## Review Focus

- Double activation of a gate ("Is there anyone else?") must create exactly one new person, and a stale click aimed at a step that is no longer current must be ignored.
- Skipping every question in a section leaves the draft byte-identical and the section still saves.
- Going Back from a newly added person's first question lands on the previous person's last question (the gate disappears), never on a missing step.
- A plan with unusual data does not crash `buildSteps`: no `arrangements.backup_arrangements`, `usual_location: null`, missing `driver_member_ids`, an unnamed member, `completion: null`.
- Editing a selected address by hand clears its verification; an unknown `?section=` value is ignored and a legacy one (`people`, `destinations`) maps to the right section.

---

## File Structure

All paths are under `frontend/`.

| File | Responsibility |
|---|---|
| `src/wizard/options.js` | Choice lists and `transportLabel`. |
| `src/wizard/labels.js` | `memberLabel` (for prompts) and `memberTitle` (for lists). |
| `src/wizard/step.js` | `question()` factory that fills step defaults. |
| `src/wizard/wizardDraft.js` | Pure factories and mutators over a plan aggregate. |
| `src/wizard/sections/*.js` | One builder per section, returning that section's steps. |
| `src/wizard/flow.js` | `SECTIONS` and `buildSteps(plan)`. |
| `src/wizard/navigation.js` | Step lookup, next/previous, section jumps, resume rules. |
| `src/wizard/summaries.js` | One-line description of each section for Review and the section recap. |
| `src/wizard/useWizard.js` | Composable: current key, `submit`, `skip`, `back`, `goTo`. |
| `src/components/wizard/questions/*.vue` | Six small inputs. |
| `src/components/wizard/WizardShell.vue` | One question screen with controls. |
| `src/components/wizard/ProgressBar.vue` | The completion bar. |
| `src/components/wizard/SectionSummary.vue` | End-of-section recap and Save and continue. |
| `src/components/wizard/ReviewScreen.vue` | Seven rows, Edit buttons, checks, final action. |
| `src/views/PlanBuilderView.vue` | Rewritten host. |
| `tests/helpers/loadComponent.js` | Shared SFC loader for render tests. |
| `tests/wizard*.test.js` | One test file per task below. |

A step object: `{ key, section, kind, prompt, helper, optional, read(plan), write(plan, value), validate?(value, plan), options?, placeholder?, maxLength?, min?, select?(plan, suggestion), addVehicle? }` where `kind` is one of `text`, `choice`, `multi`, `yesno`, `address`, `number`, `notice`, `summary`, `review`.

Keys are **index based and stable** (`member:0:name`), so a key survives the item being created by its own answer.

---

### Task 1: Options, labels, step factory, draft helpers

**Files:**
- Create: `src/wizard/options.js`, `src/wizard/labels.js`, `src/wizard/step.js`, `src/wizard/wizardDraft.js`
- Test: `tests/wizardDraft.test.js`

**Interfaces:**
- Produces:
  - `options.js`: `RELATIONSHIPS`, `USUAL_LOCATION_KINDS`, `ANIMAL_CATEGORIES`, `ANIMAL_TYPES`, `TRANSPORT_TYPES`, `TASK_PRESETS` (arrays of `[value, label]` or strings), `transportLabel(transport) -> string`.
  - `labels.js`: `memberLabel(plan, index) -> string`, `memberTitle(plan, index) -> string`.
  - `step.js`: `question(section, key, kind, prompt, extra = {}) -> step`.
  - `wizardDraft.js`: `newMember()`, `newAnimal()`, `newTransport(type = 'car')`, `newResponsibility(taskName = '')`, `newDestination()`, `newBackupArrangement()`, `memberAt(plan, i)`, `animalAt(plan, i)`, `transportAt(plan, i)`, `responsibilityAt(plan, i)`, `backupAt(plan, i)`, `primaryDestination(plan)`, `backupDestination(plan, i)`, `setUsualKind(member, kind)`, `setUsualAddress(member, address)`, `selectUsualAddress(member, suggestion)`, `resetDestinationVerification(destination)`, `setDestinationAddress(destination, address)`, `selectDestinationAddress(destination, suggestion)`. The `*At` helpers create the item (and any lower missing index) and return it.

- [ ] **Step 1: Write the failing test**

Create `tests/wizardDraft.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import {
  animalAt,
  backupAt,
  backupDestination,
  memberAt,
  primaryDestination,
  responsibilityAt,
  selectDestinationAddress,
  selectUsualAddress,
  setDestinationAddress,
  setUsualAddress,
  setUsualKind,
  transportAt,
} from '../src/wizard/wizardDraft.js'
import { memberLabel, memberTitle } from '../src/wizard/labels.js'
import { transportLabel } from '../src/wizard/options.js'
import { question } from '../src/wizard/step.js'

test('memberAt creates the member once and reuses it', () => {
  const plan = createEmptyHouseholdPlan()
  const first = memberAt(plan, 0)
  assert.match(first.member_id, /^m_/)
  assert.equal(first.display_name, '')
  assert.equal(memberAt(plan, 0), first)
  assert.equal(plan.members.length, 1)
  memberAt(plan, 2)
  assert.equal(plan.members.length, 3)
})

test('other *At helpers create their items with sensible defaults', () => {
  const plan = createEmptyHouseholdPlan()
  assert.deepEqual(
    [animalAt(plan, 0).animal_type, animalAt(plan, 0).quantity, animalAt(plan, 0).category],
    ['dog', 1, 'pet'],
  )
  assert.equal(transportAt(plan, 0).transport_type, 'car')
  assert.deepEqual(transportAt(plan, 0).driver_member_ids, [])
  assert.equal(responsibilityAt(plan, 0).task_name, '')
  assert.equal(plan.animals.length, 1)
  assert.equal(plan.transports.length, 1)
  assert.equal(plan.responsibilities.length, 1)
})

test('setUsualKind starts an unverified location and clears it for an empty kind', () => {
  const member = memberAt(createEmptyHouseholdPlan(), 0)
  setUsualKind(member, 'work')
  assert.deepEqual(member.usual_location, {
    kind: 'work', address: '', latitude: null, longitude: null, verification_status: 'unverified',
  })
  setUsualKind(member, '')
  assert.equal(member.usual_location, null)
})

test('editing a usual address by hand clears verification; the same text keeps it', () => {
  const member = memberAt(createEmptyHouseholdPlan(), 0)
  setUsualKind(member, 'home')
  member.usual_location = { ...member.usual_location, address: '1 Test St', latitude: -37.8, longitude: 144.9, verification_status: 'verified' }
  setUsualAddress(member, '1 Test St')
  assert.equal(member.usual_location.verification_status, 'verified')
  setUsualAddress(member, '2 Test St')
  assert.equal(member.usual_location.latitude, null)
  assert.equal(member.usual_location.verification_status, 'unverified')
  selectUsualAddress(member, { address: '3 Test St' })
  assert.equal(member.usual_location.address, '3 Test St')
  assert.equal(member.usual_location.selected_address, '3 Test St')
})

test('destination helpers create once, reset verification on edit, and record a selection', () => {
  const plan = createEmptyHouseholdPlan()
  const place = primaryDestination(plan)
  assert.equal(primaryDestination(plan), place)
  assert.match(place.destination_id, /^d_/)
  place.verification_status = 'verified'
  place.latitude = -37
  setDestinationAddress(place, '9 New Rd')
  assert.equal(place.latitude, null)
  assert.equal(place.verification_status, 'unverified')
  selectDestinationAddress(place, { address: '10 New Rd' })
  assert.equal(place.selected_address, '10 New Rd')
})

test('backup helpers tolerate a plan with no backup list', () => {
  const plan = createEmptyHouseholdPlan()
  delete plan.arrangements.backup_arrangements
  assert.equal(backupAt(plan, 0).transport_id, null)
  assert.equal(plan.arrangements.backup_arrangements.length, 1)
  const place = backupDestination(plan, 1)
  assert.equal(plan.arrangements.backup_arrangements.length, 2)
  assert.equal(place, plan.arrangements.backup_arrangements[1].destination)
})

test('labels fall back gracefully for unnamed people', () => {
  const plan = createEmptyHouseholdPlan()
  memberAt(plan, 1).display_name = '  Sam '
  memberAt(plan, 2)
  assert.equal(memberLabel(plan, 0), 'you')
  assert.equal(memberLabel(plan, 1), 'Sam')
  assert.equal(memberLabel(plan, 2), 'this person')
  assert.equal(memberTitle(plan, 1), 'Sam')
  assert.equal(memberTitle(plan, 2), 'Person 3')
})

test('transportLabel combines the name and the type', () => {
  assert.equal(transportLabel({ transport_type: 'ute', display_name: "Dad's" }), "Dad's: Ute / Pickup")
  assert.equal(transportLabel({ transport_type: 'other', transport_type_other: 'Tractor', display_name: '' }), 'Tractor')
  assert.equal(transportLabel({ transport_type: 'car', display_name: '' }), 'Car / SUV')
})

test('question fills defaults and lets extras override them', () => {
  const step = question('transport', 'k', 'text', 'Prompt?', { optional: false, placeholder: 'x' })
  assert.deepEqual(
    [step.section, step.key, step.kind, step.prompt, step.helper, step.optional, step.placeholder],
    ['transport', 'k', 'text', 'Prompt?', null, false, 'x'],
  )
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardDraft.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/wizardDraft.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/options.js`:

```js
export const RELATIONSHIPS = [
  ['self', 'Self'],
  ['partner', 'Partner / Spouse'],
  ['child', 'Child'],
  ['parent', 'Parent'],
  ['grandparent', 'Grandparent'],
  ['sibling', 'Sibling'],
  ['other_relative', 'Other relative'],
  ['friend_or_housemate', 'Friend / Housemate'],
  ['carer', 'Carer'],
  ['other', 'Other'],
]

export const USUAL_LOCATION_KINDS = [
  ['home', 'Home'],
  ['work', 'Work'],
  ['school', 'School'],
  ['other', 'Somewhere else'],
]

export const ANIMAL_CATEGORIES = [
  ['pet', 'A pet'],
  ['livestock', 'Livestock'],
]

export const ANIMAL_TYPES = {
  pet: [['dog', 'Dog'], ['cat', 'Cat'], ['bird', 'Bird'], ['rabbit', 'Rabbit'], ['reptile', 'Reptile'], ['other', 'Other']],
  livestock: [['horse', 'Horse'], ['cattle', 'Cattle'], ['sheep', 'Sheep'], ['goat', 'Goat'], ['alpaca', 'Alpaca'], ['poultry', 'Poultry'], ['other', 'Other']],
}

export const TRANSPORT_TYPES = [
  ['car', 'Car / SUV'],
  ['ute', 'Ute / Pickup'],
  ['van', 'Van'],
  ['motorbike', 'Motorbike'],
  ['truck', 'Truck'],
  ['other', 'Other'],
]

export const TASK_PRESETS = [
  'Prepare emergency kit',
  'Assist children or dependants',
  'Collect pets / animals',
  'Prepare important medication / documents',
  'Drive the household',
  'Contact household members',
]

export function transportLabel(transport) {
  const typeLabel = transport.transport_type === 'other' && transport.transport_type_other
    ? transport.transport_type_other
    : TRANSPORT_TYPES.find(([value]) => value === transport.transport_type)?.[1] ?? 'Other'
  return transport.display_name ? `${transport.display_name}: ${typeLabel}` : typeLabel
}
```

Create `src/wizard/labels.js`:

```js
// How a person is named inside a question ("Where is Sam ...") and in a list.
export function memberLabel(plan, index) {
  if (index === 0) return 'you'
  return plan.members[index]?.display_name?.trim() || 'this person'
}

export function memberTitle(plan, index) {
  return plan.members[index]?.display_name?.trim() || `Person ${index + 1}`
}
```

Create `src/wizard/step.js`:

```js
// Every step has the same shape; this fills the defaults so section builders
// only state what is particular to a question.
export function question(section, key, kind, prompt, extra = {}) {
  return { section, key, kind, prompt, helper: null, optional: true, ...extra }
}
```

Create `src/wizard/wizardDraft.js`:

```js
import { newId } from '../api/client.js'

export function newMember() {
  return {
    member_id: newId('m'),
    display_name: '',
    is_dependant: false,
    mobility_support_required: false,
    support_notes: null,
    relationship: null,
    usual_location: null,
    relationship_other: null,
  }
}

export function newAnimal() {
  return {
    animal_id: newId('a'),
    category: 'pet',
    display_name: '',
    animal_type: 'dog',
    animal_type_other: null,
    quantity: 1,
    support_notes: null,
  }
}

export function newTransport(type = 'car') {
  return {
    transport_id: newId('t'),
    transport_type: type,
    transport_type_other: null,
    display_name: '',
    driver_member_ids: [],
  }
}

export function newResponsibility(taskName = '') {
  return {
    responsibility_id: newId('r'),
    task_name: taskName,
    primary_member_id: null,
    backup_member_id: null,
  }
}

export function newDestination() {
  return {
    destination_id: newId('d'),
    display_name: '',
    address: null,
    canonical_address: null,
    unit_number: null,
    street_number: null,
    street_name: null,
    suburb_or_locality: null,
    state: 'VIC',
    postcode: null,
    country: 'Australia',
    latitude: null,
    longitude: null,
    verification_status: 'unverified',
    verified_at: null,
    selected_address: null,
  }
}

export function newBackupArrangement() {
  return { transport_id: null, destination: null }
}

function itemAt(list, index, create) {
  while (list.length <= index) list.push(create())
  return list[index]
}

export const memberAt = (plan, index) => itemAt(plan.members, index, newMember)
export const animalAt = (plan, index) => itemAt(plan.animals, index, newAnimal)
export const transportAt = (plan, index) => itemAt(plan.transports, index, () => newTransport())
export const responsibilityAt = (plan, index) => itemAt(plan.responsibilities, index, () => newResponsibility())

export function backupAt(plan, index) {
  plan.arrangements ??= {}
  plan.arrangements.backup_arrangements ??= []
  return itemAt(plan.arrangements.backup_arrangements, index, newBackupArrangement)
}

export function primaryDestination(plan) {
  plan.arrangements ??= {}
  plan.arrangements.primary_destination ??= newDestination()
  return plan.arrangements.primary_destination
}

export function backupDestination(plan, index) {
  const backup = backupAt(plan, index)
  backup.destination ??= newDestination()
  return backup.destination
}

export function setUsualKind(member, kind) {
  // Changing the kind discards coordinates: they belonged to the previous place.
  member.usual_location = kind
    ? { kind, address: '', latitude: null, longitude: null, verification_status: 'unverified' }
    : null
}

export function setUsualAddress(member, address) {
  // Typed text is not a verified place. Clearing the flag makes the backend
  // resolve it again on the next save.
  const location = member.usual_location
  if (!location) return
  if (location.address !== address) {
    location.latitude = null
    location.longitude = null
    location.verification_status = 'unverified'
  }
  location.address = address
}

export function selectUsualAddress(member, suggestion) {
  // Suggestions carry no coordinates; selected_address tells the backend which
  // candidate to resolve.
  setUsualAddress(member, suggestion.address)
  if (member.usual_location) member.usual_location.selected_address = suggestion.address
}

export function resetDestinationVerification(destination) {
  // Canonical fields describe the previous official address. Editing the text
  // must clear them rather than show stale verification.
  destination.canonical_address = null
  destination.unit_number = null
  destination.street_number = null
  destination.street_name = null
  destination.suburb_or_locality = null
  destination.state = null
  destination.postcode = null
  destination.country = null
  destination.latitude = null
  destination.longitude = null
  destination.verification_status = 'unverified'
  destination.verified_at = null
  destination.selected_address = null
}

export function setDestinationAddress(destination, address) {
  if (destination.address !== address) resetDestinationVerification(destination)
  destination.address = address || null
}

export function selectDestinationAddress(destination, suggestion) {
  setDestinationAddress(destination, suggestion.address)
  destination.selected_address = suggestion.address
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardDraft.test.js`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard frontend/tests/wizardDraft.test.js
git commit -m "feat(frontend): add the plan wizard draft helpers and option lists"
```

---

### Task 2: Sections 1 and 2 (household profile, daytime locations)

**Files:**
- Create: `src/wizard/sections/householdProfile.js`, `src/wizard/sections/memberLocations.js`
- Test: `tests/wizardProfileSteps.test.js`

**Interfaces:**
- Consumes: Task 1 (`question`, `memberAt`, `animalAt`, `setUsualKind`, `setUsualAddress`, `selectUsualAddress`, `memberLabel`, `memberTitle`, option lists).
- Produces: `householdProfileSteps(plan) -> step[]` and `memberLocationSteps(plan) -> step[]`. Step keys: `member:{i}:name|relationship|relationship_other|help|support_notes|more`, `animals:any`, `animal:{i}:category|type|type_other|quantity|more`, `location:{i}:kind|address`, `locations:none`.

- [ ] **Step 1: Write the failing test**

Create `tests/wizardProfileSteps.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { householdProfileSteps } from '../src/wizard/sections/householdProfile.js'
import { memberLocationSteps } from '../src/wizard/sections/memberLocations.js'

const keys = (steps) => steps.map((step) => step.key)
const byKey = (steps, key) => steps.find((step) => step.key === key)

test('an empty plan asks for the first name, then animals, and offers no gate yet', () => {
  const steps = householdProfileSteps(createEmptyHouseholdPlan())
  assert.deepEqual(keys(steps), ['member:0:name', 'member:0:help', 'animals:any'])
  assert.equal(steps[0].prompt, 'What is your name?')
})

test('answering the first name creates the member and marks them as self', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(householdProfileSteps(plan), 'member:0:name').write(plan, '  Maya ')
  assert.equal(plan.members[0].display_name, 'Maya')
  assert.equal(plan.members[0].relationship, 'self')
})

test('a named last person unlocks the gate; yes appends exactly one person', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(householdProfileSteps(plan), 'member:0:name').write(plan, 'Maya')
  const gate = byKey(householdProfileSteps(plan), 'member:0:more')
  assert.equal(gate.kind, 'yesno')
  gate.write(plan, true)
  gate.write(plan, true)
  assert.equal(plan.members.length, 2)
  const next = keys(householdProfileSteps(plan))
  assert.ok(!next.includes('member:0:more'))
  assert.deepEqual(next.slice(next.indexOf('member:1:name'), next.indexOf('member:1:name') + 3), [
    'member:1:name', 'member:1:relationship', 'member:1:help',
  ])
})

test('"Other" relationship asks for a description; extra help asks for notes', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ ...createMember('Sam'), relationship: 'other' })
  const steps = householdProfileSteps(plan)
  assert.ok(keys(steps).includes('member:0:relationship_other'))
  assert.ok(!keys(steps).includes('member:0:support_notes'))
  byKey(steps, 'member:0:help').write(plan, ['mobility'])
  assert.equal(plan.members[0].mobility_support_required, true)
  assert.equal(plan.members[0].is_dependant, false)
  assert.ok(keys(householdProfileSteps(plan)).includes('member:0:support_notes'))
  assert.deepEqual(byKey(householdProfileSteps(plan), 'member:0:help').read(plan), ['mobility'])
})

test('animals: yes adds one pet with defaults, no removes them, category resets the type', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(householdProfileSteps(plan), 'animals:any').write(plan, true)
  assert.equal(plan.animals.length, 1)
  let steps = householdProfileSteps(plan)
  assert.deepEqual(
    keys(steps).filter((key) => key.startsWith('animal:')),
    ['animal:0:category', 'animal:0:type', 'animal:0:quantity', 'animal:0:more'],
  )
  byKey(steps, 'animal:0:category').write(plan, 'livestock')
  assert.equal(plan.animals[0].animal_type, 'horse')
  byKey(householdProfileSteps(plan), 'animal:0:type').write(plan, 'other')
  steps = householdProfileSteps(plan)
  assert.ok(keys(steps).includes('animal:0:type_other'))
  assert.equal(byKey(steps, 'animal:0:type_other').validate('  ', plan), 'Please describe the animal.')
  assert.equal(byKey(steps, 'animal:0:type_other').validate('Ferret', plan), null)
  byKey(steps, 'animals:any').write(plan, false)
  assert.equal(plan.animals.length, 0)
})

test('animal quantity must be a whole number of at least 1', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(householdProfileSteps(plan), 'animals:any').write(plan, true)
  const quantity = byKey(householdProfileSteps(plan), 'animal:0:quantity')
  assert.equal(quantity.validate(0, plan), 'Enter a whole number of at least 1.')
  assert.equal(quantity.validate(1.5, plan), 'Enter a whole number of at least 1.')
  assert.equal(quantity.validate(3, plan), null)
  quantity.write(plan, 3)
  assert.equal(plan.animals[0].quantity, 3)
})

test('locations: no members gives a notice; each person asks a kind, then an address once chosen', () => {
  const empty = memberLocationSteps(createEmptyHouseholdPlan())
  assert.deepEqual(keys(empty), ['locations:none'])
  assert.equal(empty[0].kind, 'notice')

  const plan = createEmptyHouseholdPlan()
  plan.members.push(createMember('Maya'), createMember('Sam'))
  assert.deepEqual(keys(memberLocationSteps(plan)), ['location:0:kind', 'location:1:kind'])
  byKey(memberLocationSteps(plan), 'location:1:kind').write(plan, 'work')
  const steps = memberLocationSteps(plan)
  assert.deepEqual(keys(steps), ['location:0:kind', 'location:1:kind', 'location:1:address'])
  assert.equal(byKey(steps, 'location:1:kind').prompt, 'Where is Sam during the day?')
  assert.equal(byKey(steps, 'location:0:kind').prompt, 'Where are you during the day?')
  byKey(steps, 'location:1:address').write(plan, '5 Work St')
  assert.equal(plan.members[1].usual_location.address, '5 Work St')
  byKey(steps, 'location:1:address').select(plan, { address: '6 Work St' })
  assert.equal(plan.members[1].usual_location.selected_address, '6 Work St')
})

test('builders survive unusual saved data', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ ...createMember(''), usual_location: null })
  delete plan.arrangements
  assert.doesNotThrow(() => householdProfileSteps(plan))
  assert.doesNotThrow(() => memberLocationSteps(plan))
})

function createMember(name) {
  return {
    member_id: `m_${name || 'blank'}`,
    display_name: name,
    is_dependant: false,
    mobility_support_required: false,
    support_notes: null,
    relationship: null,
    usual_location: null,
    relationship_other: null,
  }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardProfileSteps.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/sections/householdProfile.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/sections/householdProfile.js`:

```js
import { ANIMAL_CATEGORIES, ANIMAL_TYPES, RELATIONSHIPS } from '../options.js'
import { memberLabel } from '../labels.js'
import { question } from '../step.js'
import { animalAt, memberAt } from '../wizardDraft.js'

const SECTION = 'household_profile'

const HELP_OPTIONS = [
  ['dependant', 'Depends on someone else to leave, such as a young child'],
  ['mobility', 'Needs help moving or getting into a vehicle'],
]

export function householdProfileSteps(plan) {
  const steps = []
  const memberCount = Math.max(plan.members.length, 1)

  for (let i = 0; i < memberCount; i += 1) {
    const member = plan.members[i]
    const label = memberLabel(plan, i)

    steps.push(question(SECTION, `member:${i}:name`, 'text', i === 0 ? 'What is your name?' : 'What is their name?', {
      placeholder: 'e.g. Maya',
      maxLength: 100,
      read: (p) => p.members[i]?.display_name ?? '',
      write: (p, value) => {
        const created = !p.members[i]
        const target = memberAt(p, i)
        target.display_name = value.trim()
        if (created && i === 0 && target.relationship === null) target.relationship = 'self'
      },
    }))

    if (i > 0) {
      steps.push(question(SECTION, `member:${i}:relationship`, 'choice', `How is ${label} related to you?`, {
        options: [['', 'Prefer not to say'], ...RELATIONSHIPS],
        read: (p) => p.members[i]?.relationship ?? '',
        write: (p, value) => { memberAt(p, i).relationship = value || null },
      }))
    }

    if (member?.relationship === 'other') {
      steps.push(question(SECTION, `member:${i}:relationship_other`, 'text', `How would you describe ${label}?`, {
        placeholder: 'e.g. Neighbour',
        maxLength: 100,
        read: (p) => p.members[i]?.relationship_other ?? '',
        write: (p, value) => { memberAt(p, i).relationship_other = value.trim() || null },
      }))
    }

    steps.push(question(
      SECTION,
      `member:${i}:help`,
      'multi',
      i === 0 ? 'Do you need any extra help to leave?' : `Does ${label} need any extra help to leave?`,
      {
        helper: 'Tick any that apply. Skip if none do.',
        options: HELP_OPTIONS,
        read: (p) => {
          const m = p.members[i]
          return [m?.is_dependant && 'dependant', m?.mobility_support_required && 'mobility'].filter(Boolean)
        },
        write: (p, values) => {
          const m = memberAt(p, i)
          m.is_dependant = values.includes('dependant')
          m.mobility_support_required = values.includes('mobility')
        },
      },
    ))

    if (member?.is_dependant || member?.mobility_support_required) {
      steps.push(question(SECTION, `member:${i}:support_notes`, 'text', `Is there anything else we should know about ${label}?`, {
        placeholder: 'e.g. Needs medication prepared',
        read: (p) => p.members[i]?.support_notes ?? '',
        write: (p, value) => { memberAt(p, i).support_notes = value.trim() || null },
      }))
    }
  }

  const last = memberCount - 1
  if (plan.members[last]?.display_name?.trim()) {
    steps.push(question(SECTION, `member:${last}:more`, 'yesno', 'Is there anyone else in your household?', {
      read: () => false,
      write: (p, value) => { if (value) memberAt(p, memberCount) },
    }))
  }

  steps.push(question(SECTION, 'animals:any', 'yesno', 'Do any animals leave with you?', {
    helper: 'Pets or livestock. Skip if you have none.',
    read: (p) => p.animals.length > 0,
    write: (p, value) => {
      if (value) animalAt(p, 0)
      else p.animals.splice(0)
    },
  }))

  const animalCount = plan.animals.length
  for (let i = 0; i < animalCount; i += 1) {
    const animal = plan.animals[i]
    steps.push(question(SECTION, `animal:${i}:category`, 'choice', 'Is this a pet or livestock?', {
      options: ANIMAL_CATEGORIES,
      read: (p) => p.animals[i]?.category ?? '',
      write: (p, value) => {
        const target = animalAt(p, i)
        target.category = value
        target.animal_type = ANIMAL_TYPES[value][0][0]
        target.animal_type_other = null
      },
    }))
    steps.push(question(SECTION, `animal:${i}:type`, 'choice', 'What kind of animal is it?', {
      options: ANIMAL_TYPES[animal.category] ?? ANIMAL_TYPES.pet,
      read: (p) => p.animals[i]?.animal_type ?? '',
      write: (p, value) => {
        const target = animalAt(p, i)
        target.animal_type = value
        if (value !== 'other') target.animal_type_other = null
      },
    }))
    if (animal.animal_type === 'other') {
      steps.push(question(SECTION, `animal:${i}:type_other`, 'text', 'What kind of animal?', {
        placeholder: 'e.g. Ferret',
        maxLength: 100,
        optional: false,
        read: (p) => p.animals[i]?.animal_type_other ?? '',
        write: (p, value) => { animalAt(p, i).animal_type_other = value.trim() || null },
        validate: (value) => (value.trim() ? null : 'Please describe the animal.'),
      }))
    }
    steps.push(question(SECTION, `animal:${i}:quantity`, 'number', 'How many?', {
      min: 1,
      read: (p) => p.animals[i]?.quantity ?? 1,
      write: (p, value) => { animalAt(p, i).quantity = Number(value) },
      validate: (value) => (Number.isInteger(Number(value)) && Number(value) >= 1 ? null : 'Enter a whole number of at least 1.'),
    }))
  }

  if (animalCount > 0) {
    const lastAnimal = animalCount - 1
    steps.push(question(SECTION, `animal:${lastAnimal}:more`, 'yesno', 'Is there another animal?', {
      read: () => false,
      write: (p, value) => { if (value) animalAt(p, animalCount) },
    }))
  }

  return steps
}
```

Create `src/wizard/sections/memberLocations.js`:

```js
import { USUAL_LOCATION_KINDS } from '../options.js'
import { memberLabel } from '../labels.js'
import { question } from '../step.js'
import { memberAt, selectUsualAddress, setUsualAddress, setUsualKind } from '../wizardDraft.js'

const SECTION = 'member_locations'

export function memberLocationSteps(plan) {
  if (!plan.members.length) {
    return [question(SECTION, 'locations:none', 'notice', 'Add the people in your household first', {
      helper: 'Once they are added, come back here to say where each person is during the day.',
    })]
  }

  const steps = []
  plan.members.forEach((member, i) => {
    const label = memberLabel(plan, i)
    steps.push(question(
      SECTION,
      `location:${i}:kind`,
      'choice',
      i === 0 ? 'Where are you during the day?' : `Where is ${label} during the day?`,
      {
        options: [['', 'Not sure'], ...USUAL_LOCATION_KINDS],
        read: (p) => p.members[i]?.usual_location?.kind ?? '',
        write: (p, value) => setUsualKind(memberAt(p, i), value),
      },
    ))
    if (member.usual_location) {
      steps.push(question(SECTION, `location:${i}:address`, 'address', 'What is the address?', {
        helper: 'Pick a suggestion, or type it in if it is not listed.',
        read: (p) => p.members[i]?.usual_location?.address ?? '',
        write: (p, value) => {
          const target = p.members[i]
          if (target?.usual_location) setUsualAddress(target, value)
        },
        select: (p, suggestion) => {
          const target = p.members[i]
          if (target?.usual_location) selectUsualAddress(target, suggestion)
        },
      }))
    }
  })
  return steps
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardProfileSteps.test.js`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/sections frontend/tests/wizardProfileSteps.test.js
git commit -m "feat(frontend): add wizard questions for the household and daytime locations"
```

---

### Task 3: Sections 3 and 4 (transport, backup transport)

**Files:**
- Create: `src/wizard/sections/transport.js`, `src/wizard/sections/backupTransport.js`
- Test: `tests/wizardTransportSteps.test.js`

**Interfaces:**
- Consumes: Task 1 helpers; `transportLabel`, `TRANSPORT_TYPES`, `memberTitle`.
- Produces: `transportSteps(plan)`, `backupTransportSteps(plan)`. Keys: `transport:has`, `vehicle:{i}:type|type_other|name|drivers|more`, `transport:primary`, `backup:{i}:transport|more`, `backup:none` (a `choice` step with `options: []` and `addVehicle: true`). `backupTransportSteps` returns `[]` when `has_private_transport === false` (the section is skipped).

- [ ] **Step 1: Write the failing test**

Create `tests/wizardTransportSteps.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { backupTransportSteps } from '../src/wizard/sections/backupTransport.js'
import { transportSteps } from '../src/wizard/sections/transport.js'

const keys = (steps) => steps.map((step) => step.key)
const byKey = (steps, key) => steps.find((step) => step.key === key)

test('before answering, only the yes/no question is asked', () => {
  const steps = transportSteps(createEmptyHouseholdPlan())
  assert.deepEqual(keys(steps), ['transport:has'])
  assert.equal(steps[0].read(createEmptyHouseholdPlan()), null)
})

test('yes adds one vehicle and reveals its questions and the primary choice', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  assert.equal(plan.has_private_transport, true)
  assert.equal(plan.transports.length, 1)
  assert.deepEqual(keys(transportSteps(plan)), [
    'transport:has', 'vehicle:0:type', 'vehicle:0:name', 'vehicle:0:more', 'transport:primary',
  ])
})

test('drivers are asked only when there are people, and write driver ids', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' }, { member_id: 'm_b', display_name: '' })
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  const steps = transportSteps(plan)
  const drivers = byKey(steps, 'vehicle:0:drivers')
  assert.deepEqual(drivers.options, [['m_a', 'Maya'], ['m_b', 'Person 2']])
  drivers.write(plan, ['m_b'])
  assert.deepEqual(plan.transports[0].driver_member_ids, ['m_b'])
  assert.deepEqual(byKey(transportSteps(plan), 'vehicle:0:drivers').read(plan), ['m_b'])
})

test('"Other" vehicle type requires a description; type and name are written', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  byKey(transportSteps(plan), 'vehicle:0:type').write(plan, 'other')
  const steps = transportSteps(plan)
  assert.ok(keys(steps).includes('vehicle:0:type_other'))
  assert.equal(byKey(steps, 'vehicle:0:type_other').validate('', plan), 'Please describe the vehicle.')
  byKey(steps, 'vehicle:0:name').write(plan, " Dad's ")
  assert.equal(plan.transports[0].display_name, "Dad's")
})

test('"another vehicle" appends one; the primary choice lists every vehicle', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  const gate = byKey(transportSteps(plan), 'vehicle:0:more')
  gate.write(plan, true)
  gate.write(plan, true)
  assert.equal(plan.transports.length, 2)
  const primary = byKey(transportSteps(plan), 'transport:primary')
  assert.equal(primary.options.length, 3)
  primary.write(plan, plan.transports[1].transport_id)
  assert.equal(plan.arrangements.primary_transport_id, plan.transports[1].transport_id)
})

test('no vehicle clears the primary choice and skips the backup section', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  plan.arrangements.primary_transport_id = plan.transports[0].transport_id
  byKey(transportSteps(plan), 'transport:has').write(plan, false)
  assert.equal(plan.has_private_transport, false)
  assert.equal(plan.arrangements.primary_transport_id, null)
  assert.deepEqual(keys(transportSteps(plan)), ['transport:has'])
  assert.deepEqual(backupTransportSteps(plan), [])
})

test('backup: with one vehicle the user is invited to add another', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  plan.arrangements.primary_transport_id = plan.transports[0].transport_id
  const steps = backupTransportSteps(plan)
  assert.deepEqual(keys(steps), ['backup:none'])
  assert.equal(steps[0].addVehicle, true)
  assert.deepEqual(steps[0].options, [])
})

test('backup: pick another vehicle, then offer another only while some remain unused', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  byKey(transportSteps(plan), 'vehicle:0:more').write(plan, true)
  byKey(transportSteps(plan), 'vehicle:1:more').write(plan, true)
  plan.arrangements.primary_transport_id = plan.transports[0].transport_id

  let steps = backupTransportSteps(plan)
  assert.deepEqual(keys(steps), ['backup:0:transport'])
  assert.equal(steps[0].options.length, 3)
  steps[0].write(plan, plan.transports[1].transport_id)
  assert.equal(plan.arrangements.backup_arrangements[0].transport_id, plan.transports[1].transport_id)

  steps = backupTransportSteps(plan)
  assert.deepEqual(keys(steps), ['backup:0:transport', 'backup:0:more'])
  byKey(steps, 'backup:0:more').write(plan, true)
  assert.equal(plan.arrangements.backup_arrangements.length, 2)
  steps = backupTransportSteps(plan)
  assert.deepEqual(keys(steps), ['backup:0:transport', 'backup:1:transport'])
})

test('builders survive missing arrangements and driver lists', () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = true
  plan.transports.push({ transport_id: 't_x', transport_type: 'car', display_name: '' })
  delete plan.arrangements
  assert.doesNotThrow(() => transportSteps(plan))
  assert.doesNotThrow(() => backupTransportSteps(plan))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardTransportSteps.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/sections/transport.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/sections/transport.js`:

```js
import { TRANSPORT_TYPES, transportLabel } from '../options.js'
import { memberTitle } from '../labels.js'
import { question } from '../step.js'
import { transportAt } from '../wizardDraft.js'

const SECTION = 'transport'

export function transportSteps(plan) {
  const steps = [question(SECTION, 'transport:has', 'yesno', 'Do you have a vehicle you would leave in?', {
    read: (p) => (p.has_private_transport === undefined ? null : p.has_private_transport),
    write: (p, value) => {
      p.has_private_transport = value
      if (value) {
        transportAt(p, 0)
      } else {
        // The backend only counts "no private transport" as complete while no
        // primary vehicle is set.
        p.arrangements ??= {}
        p.arrangements.primary_transport_id = null
      }
    },
  })]

  if (plan.has_private_transport !== true) return steps

  const count = Math.max(plan.transports.length, 1)
  for (let i = 0; i < count; i += 1) {
    const vehicle = plan.transports[i]

    steps.push(question(SECTION, `vehicle:${i}:type`, 'choice', i === 0 ? 'What kind of vehicle is it?' : 'What kind of vehicle is the next one?', {
      options: TRANSPORT_TYPES,
      read: (p) => p.transports[i]?.transport_type ?? '',
      write: (p, value) => {
        const target = transportAt(p, i)
        target.transport_type = value
        if (value !== 'other') target.transport_type_other = null
      },
    }))

    if (vehicle?.transport_type === 'other') {
      steps.push(question(SECTION, `vehicle:${i}:type_other`, 'text', 'What kind of vehicle?', {
        placeholder: 'e.g. Tractor',
        maxLength: 100,
        optional: false,
        read: (p) => p.transports[i]?.transport_type_other ?? '',
        write: (p, value) => { transportAt(p, i).transport_type_other = value.trim() || null },
        validate: (value) => (value.trim() ? null : 'Please describe the vehicle.'),
      }))
    }

    steps.push(question(SECTION, `vehicle:${i}:name`, 'text', 'What do you call it?', {
      helper: 'For example "Dad\'s ute". Optional.',
      placeholder: 'Optional',
      maxLength: 100,
      read: (p) => p.transports[i]?.display_name ?? '',
      write: (p, value) => { transportAt(p, i).display_name = value.trim() },
    }))

    if (plan.members.length) {
      steps.push(question(SECTION, `vehicle:${i}:drivers`, 'multi', 'Who can drive it?', {
        helper: 'Tick everyone who could drive it. Skip if you are not sure.',
        options: plan.members.map((member, index) => [member.member_id, memberTitle(plan, index)]),
        read: (p) => p.transports[i]?.driver_member_ids ?? [],
        write: (p, values) => { transportAt(p, i).driver_member_ids = [...values] },
      }))
    }
  }

  const last = count - 1
  steps.push(question(SECTION, `vehicle:${last}:more`, 'yesno', 'Is there another vehicle?', {
    read: () => false,
    write: (p, value) => { if (value) transportAt(p, count) },
  }))

  if (plan.transports.length) {
    steps.push(question(SECTION, 'transport:primary', 'choice', 'Which one would you take first?', {
      options: [['', 'Not sure yet'], ...plan.transports.map((t) => [t.transport_id, transportLabel(t)])],
      read: (p) => p.arrangements?.primary_transport_id ?? '',
      write: (p, value) => {
        p.arrangements ??= {}
        p.arrangements.primary_transport_id = value || null
      },
    }))
  }

  return steps
}
```

Create `src/wizard/sections/backupTransport.js`:

```js
import { transportLabel } from '../options.js'
import { question } from '../step.js'
import { backupAt } from '../wizardDraft.js'

const SECTION = 'backup_transport'

export function backupTransportSteps(plan) {
  // With no private transport the backend already counts this section complete.
  if (plan.has_private_transport === false) return []

  const primary = plan.arrangements?.primary_transport_id ?? null
  const candidates = plan.transports.filter((t) => t.transport_id !== primary)

  if (!candidates.length) {
    return [question(SECTION, 'backup:none', 'choice', 'If your main vehicle cannot be used, which would you take?', {
      helper: 'You have not added a second vehicle yet.',
      options: [],
      addVehicle: true,
      read: () => '',
      write: () => {},
    })]
  }

  const backups = plan.arrangements?.backup_arrangements ?? []
  const count = Math.max(backups.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    steps.push(question(
      SECTION,
      `backup:${i}:transport`,
      'choice',
      i === 0 ? 'If your main vehicle cannot be used, which would you take?' : 'Which other vehicle could you use?',
      {
        options: [['', 'Not sure yet'], ...candidates.map((t) => [t.transport_id, transportLabel(t)])],
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.transport_id ?? '',
        write: (p, value) => { backupAt(p, i).transport_id = value || null },
      },
    ))
  }

  const last = count - 1
  const assigned = backups.filter((backup) => backup.transport_id).length
  if (backups[last]?.transport_id && assigned < candidates.length) {
    steps.push(question(SECTION, `backup:${last}:more`, 'yesno', 'Is there another vehicle you could use?', {
      read: () => false,
      write: (p, value) => { if (value) backupAt(p, count) },
    }))
  }

  return steps
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardTransportSteps.test.js`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/sections frontend/tests/wizardTransportSteps.test.js
git commit -m "feat(frontend): add wizard questions for transport and backup transport"
```

---

### Task 4: Sections 5, 6 and 7 (destinations, responsibilities)

**Files:**
- Create: `src/wizard/sections/primaryDestination.js`, `src/wizard/sections/backupDestination.js`, `src/wizard/sections/responsibilities.js`
- Test: `tests/wizardPlaceSteps.test.js`

**Interfaces:**
- Consumes: Task 1 helpers, `TASK_PRESETS`, `memberTitle`.
- Produces: `primaryDestinationSteps(plan)`, `backupDestinationSteps(plan)`, `responsibilitySteps(plan)`. Keys: `place:name|address|meeting`, `backupplace:{i}:name|address|more`, `resp:{i}:task|task_custom|primary|backup|more`, `resp:none` (`notice`).

- [ ] **Step 1: Write the failing test**

Create `tests/wizardPlaceSteps.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { backupDestinationSteps } from '../src/wizard/sections/backupDestination.js'
import { primaryDestinationSteps } from '../src/wizard/sections/primaryDestination.js'
import { responsibilitySteps } from '../src/wizard/sections/responsibilities.js'

const keys = (steps) => steps.map((step) => step.key)
const byKey = (steps, key) => steps.find((step) => step.key === key)

test('primary destination: name first; the address is asked only once there is a place', () => {
  const plan = createEmptyHouseholdPlan()
  assert.deepEqual(keys(primaryDestinationSteps(plan)), ['place:name', 'place:meeting'])
  byKey(primaryDestinationSteps(plan), 'place:name').write(plan, " Nan's house ")
  assert.equal(plan.arrangements.primary_destination.display_name, "Nan's house")
  const steps = primaryDestinationSteps(plan)
  assert.deepEqual(keys(steps), ['place:name', 'place:address', 'place:meeting'])
  byKey(steps, 'place:address').write(plan, '1 Hill Rd')
  byKey(steps, 'place:address').select(plan, { address: '2 Hill Rd' })
  assert.equal(plan.arrangements.primary_destination.selected_address, '2 Hill Rd')
  byKey(steps, 'place:meeting').write(plan, ' Front gate ')
  assert.equal(plan.arrangements.meeting_point, 'Front gate')
  byKey(steps, 'place:meeting').write(plan, '  ')
  assert.equal(plan.arrangements.meeting_point, null)
})

test('backup destination: loops over backup entries and offers another once one is named', () => {
  const plan = createEmptyHouseholdPlan()
  assert.deepEqual(keys(backupDestinationSteps(plan)), ['backupplace:0:name'])
  byKey(backupDestinationSteps(plan), 'backupplace:0:name').write(plan, 'Community centre')
  assert.equal(plan.arrangements.backup_arrangements[0].destination.display_name, 'Community centre')
  let steps = backupDestinationSteps(plan)
  assert.deepEqual(keys(steps), ['backupplace:0:name', 'backupplace:0:address', 'backupplace:0:more'])
  byKey(steps, 'backupplace:0:address').write(plan, '3 Park St')
  byKey(steps, 'backupplace:0:more').write(plan, true)
  byKey(steps, 'backupplace:0:more').write(plan, true)
  assert.equal(plan.arrangements.backup_arrangements.length, 2)
  steps = backupDestinationSteps(plan)
  assert.deepEqual(keys(steps), [
    'backupplace:0:name', 'backupplace:0:address', 'backupplace:1:name',
  ])
  assert.equal(byKey(steps, 'backupplace:1:name').prompt, 'Where else could you go?')
})

test('backup destination shares its entries with the backup vehicle', () => {
  const plan = createEmptyHouseholdPlan()
  plan.arrangements.backup_arrangements.push({ transport_id: 't_1', destination: null })
  byKey(backupDestinationSteps(plan), 'backupplace:0:name').write(plan, 'Library')
  assert.equal(plan.arrangements.backup_arrangements.length, 1)
  assert.equal(plan.arrangements.backup_arrangements[0].transport_id, 't_1')
})

test('responsibilities: a notice when nobody has been added', () => {
  const steps = responsibilitySteps(createEmptyHouseholdPlan())
  assert.deepEqual(keys(steps), ['resp:none'])
  assert.equal(steps[0].kind, 'notice')
})

test('responsibilities: preset task, people lists and the different-backup rule', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' }, { member_id: 'm_b', display_name: 'Sam' })
  let steps = responsibilitySteps(plan)
  assert.deepEqual(keys(steps), ['resp:0:task', 'resp:0:primary', 'resp:0:backup'])
  byKey(steps, 'resp:0:task').write(plan, 'Drive the household')
  assert.equal(plan.responsibilities[0].task_name, 'Drive the household')
  byKey(responsibilitySteps(plan), 'resp:0:primary').write(plan, 'm_a')
  steps = responsibilitySteps(plan)
  assert.deepEqual(byKey(steps, 'resp:0:backup').options, [['', 'No one yet'], ['m_b', 'Sam']])
  assert.equal(byKey(steps, 'resp:0:backup').validate('m_a', plan), 'Choose someone other than the main person.')
  assert.equal(byKey(steps, 'resp:0:backup').validate('m_b', plan), null)
  byKey(steps, 'resp:0:backup').write(plan, 'm_b')
  assert.equal(plan.responsibilities[0].backup_member_id, 'm_b')
  assert.deepEqual(byKey(steps, 'resp:0:task').read(plan), 'Drive the household')
})

test('responsibilities: "something else" asks for a task and requires it', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' })
  byKey(responsibilitySteps(plan), 'resp:0:task').write(plan, 'other')
  const steps = responsibilitySteps(plan)
  assert.ok(keys(steps).includes('resp:0:task_custom'))
  assert.equal(byKey(steps, 'resp:0:task').read(plan), 'other')
  assert.equal(byKey(steps, 'resp:0:task_custom').validate(' ', plan), 'Please describe the task.')
  byKey(steps, 'resp:0:task_custom').write(plan, ' Feed the chickens ')
  assert.equal(plan.responsibilities[0].task_name, 'Feed the chickens')
  assert.equal(byKey(responsibilitySteps(plan), 'resp:0:task').read(plan), 'other')
})

test('responsibilities: another task is offered once the last has a task name', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' })
  byKey(responsibilitySteps(plan), 'resp:0:task').write(plan, 'Prepare emergency kit')
  const gate = byKey(responsibilitySteps(plan), 'resp:0:more')
  gate.write(plan, true)
  gate.write(plan, true)
  assert.equal(plan.responsibilities.length, 2)
  assert.ok(!keys(responsibilitySteps(plan)).includes('resp:0:more'))
})

test('builders survive missing arrangements', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' })
  delete plan.arrangements
  assert.doesNotThrow(() => primaryDestinationSteps(plan))
  assert.doesNotThrow(() => backupDestinationSteps(plan))
  assert.doesNotThrow(() => responsibilitySteps(plan))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardPlaceSteps.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/sections/primaryDestination.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/sections/primaryDestination.js`:

```js
import { question } from '../step.js'
import { primaryDestination, selectDestinationAddress, setDestinationAddress } from '../wizardDraft.js'

const SECTION = 'primary_destination'

export function primaryDestinationSteps(plan) {
  const place = plan.arrangements?.primary_destination ?? null
  const steps = [question(SECTION, 'place:name', 'text', 'Where would you go?', {
    helper: 'A name you would recognise, such as "Nan\'s house".',
    placeholder: "e.g. Relative's house",
    maxLength: 100,
    read: (p) => p.arrangements?.primary_destination?.display_name ?? '',
    write: (p, value) => { primaryDestination(p).display_name = value.trim() },
  })]

  if (place) {
    steps.push(question(SECTION, 'place:address', 'address', 'What is the address?', {
      helper: 'Pick a suggestion, or type it in if it is not listed.',
      read: (p) => p.arrangements?.primary_destination?.address ?? '',
      write: (p, value) => {
        const target = p.arrangements?.primary_destination
        if (target) setDestinationAddress(target, value)
      },
      select: (p, suggestion) => {
        const target = p.arrangements?.primary_destination
        if (target) selectDestinationAddress(target, suggestion)
      },
    }))
  }

  steps.push(question(SECTION, 'place:meeting', 'text', 'If your household is separated, where would you meet?', {
    helper: 'Optional.',
    placeholder: 'e.g. Front gate',
    maxLength: 200,
    read: (p) => p.arrangements?.meeting_point ?? '',
    write: (p, value) => {
      p.arrangements ??= {}
      p.arrangements.meeting_point = value.trim() || null
    },
  }))

  return steps
}
```

Create `src/wizard/sections/backupDestination.js`:

```js
import { question } from '../step.js'
import { backupAt, backupDestination, selectDestinationAddress, setDestinationAddress } from '../wizardDraft.js'

const SECTION = 'backup_destination'

export function backupDestinationSteps(plan) {
  const backups = plan.arrangements?.backup_arrangements ?? []
  const count = Math.max(backups.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    const place = backups[i]?.destination ?? null

    steps.push(question(
      SECTION,
      `backupplace:${i}:name`,
      'text',
      i === 0 ? 'If you could not go there, where would you go instead?' : 'Where else could you go?',
      {
        placeholder: 'e.g. Community centre',
        maxLength: 100,
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.destination?.display_name ?? '',
        write: (p, value) => { backupDestination(p, i).display_name = value.trim() },
      },
    ))

    if (place) {
      steps.push(question(SECTION, `backupplace:${i}:address`, 'address', 'What is the address?', {
        helper: 'Pick a suggestion, or type it in if it is not listed.',
        read: (p) => p.arrangements?.backup_arrangements?.[i]?.destination?.address ?? '',
        write: (p, value) => {
          const target = p.arrangements?.backup_arrangements?.[i]?.destination
          if (target) setDestinationAddress(target, value)
        },
        select: (p, suggestion) => {
          const target = p.arrangements?.backup_arrangements?.[i]?.destination
          if (target) selectDestinationAddress(target, suggestion)
        },
      }))
    }
  }

  const last = count - 1
  if (backups[last]?.destination?.display_name?.trim()) {
    steps.push(question(SECTION, `backupplace:${last}:more`, 'yesno', 'Is there another place you could go?', {
      read: () => false,
      write: (p, value) => { if (value) backupAt(p, count) },
    }))
  }

  return steps
}
```

Create `src/wizard/sections/responsibilities.js`:

```js
import { TASK_PRESETS } from '../options.js'
import { memberTitle } from '../labels.js'
import { question } from '../step.js'
import { responsibilityAt } from '../wizardDraft.js'

const SECTION = 'responsibilities'

export function responsibilitySteps(plan) {
  if (!plan.members.length) {
    return [question(SECTION, 'resp:none', 'notice', 'Add the people in your household first', {
      helper: 'Once they are added, come back here to say who does what.',
    })]
  }

  const people = plan.members.map((member, index) => [member.member_id, memberTitle(plan, index)])
  const count = Math.max(plan.responsibilities.length, 1)
  const steps = []

  for (let i = 0; i < count; i += 1) {
    const item = plan.responsibilities[i]

    steps.push(question(SECTION, `resp:${i}:task`, 'choice', i === 0 ? 'What is one job that has to happen?' : 'What is the next job?', {
      options: [...TASK_PRESETS.map((task) => [task, task]), ['other', 'Something else']],
      read: (p) => {
        const name = p.responsibilities[i]?.task_name
        if (!p.responsibilities[i]) return ''
        return TASK_PRESETS.includes(name) ? name : 'other'
      },
      write: (p, value) => {
        responsibilityAt(p, i).task_name = value === 'other' ? '' : value
      },
    }))

    if (item && !TASK_PRESETS.includes(item.task_name)) {
      steps.push(question(SECTION, `resp:${i}:task_custom`, 'text', 'What is the job?', {
        placeholder: 'e.g. Feed the chickens',
        maxLength: 100,
        optional: false,
        read: (p) => p.responsibilities[i]?.task_name ?? '',
        write: (p, value) => { responsibilityAt(p, i).task_name = value.trim() },
        validate: (value) => (value.trim() ? null : 'Please describe the task.'),
      }))
    }

    steps.push(question(SECTION, `resp:${i}:primary`, 'choice', 'Who does it?', {
      options: [['', 'Not decided yet'], ...people],
      read: (p) => p.responsibilities[i]?.primary_member_id ?? '',
      write: (p, value) => { responsibilityAt(p, i).primary_member_id = value || null },
    }))

    steps.push(question(SECTION, `resp:${i}:backup`, 'choice', 'Who covers it if they cannot?', {
      options: [['', 'No one yet'], ...people.filter(([id]) => id !== item?.primary_member_id)],
      read: (p) => p.responsibilities[i]?.backup_member_id ?? '',
      write: (p, value) => { responsibilityAt(p, i).backup_member_id = value || null },
      validate: (value, p) => (
        value && value === p.responsibilities[i]?.primary_member_id
          ? 'Choose someone other than the main person.'
          : null
      ),
    }))
  }

  const last = count - 1
  if (plan.responsibilities[last]?.task_name?.trim()) {
    steps.push(question(SECTION, `resp:${last}:more`, 'yesno', 'Is there another job to cover?', {
      read: () => false,
      write: (p, value) => { if (value) responsibilityAt(p, count) },
    }))
  }

  return steps
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardPlaceSteps.test.js`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/sections frontend/tests/wizardPlaceSteps.test.js
git commit -m "feat(frontend): add wizard questions for destinations and responsibilities"
```

---

### Task 5: Flow assembly, navigation, summaries

**Files:**
- Create: `src/wizard/flow.js`, `src/wizard/navigation.js`, `src/wizard/summaries.js`
- Test: `tests/wizardNavigation.test.js`

**Interfaces:**
- Consumes: the seven section builders (Tasks 2-4), `memberTitle`, `transportLabel`.
- Produces:
  - `flow.js`: `SECTIONS` (`[{ id, title, short }]` in backend order), `buildSteps(plan) -> step[]` (each non-empty section's steps, then `{ key: 'summary:<id>', section: id, kind: 'summary' }`, finally `{ key: 'review', section: null, kind: 'review' }`).
  - `navigation.js`: `indexOfKey(steps, key) -> number`, `nextKey(steps, key) -> string`, `previousKey(steps, key) -> string`, `keyAfterWrite(steps, previousKey, previousIndex) -> string`, `firstKeyOfSection(steps, sectionId) -> string`, `nextSectionKey(steps, sectionId) -> string`, `firstIncompleteSection(completion) -> string | null`, `resolveSectionParam(value) -> string | null`.
  - `summaries.js`: `describeSection(plan, sectionId) -> string`.

- [ ] **Step 1: Write the failing test**

Create `tests/wizardNavigation.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { SECTIONS, buildSteps } from '../src/wizard/flow.js'
import {
  firstIncompleteSection,
  firstKeyOfSection,
  indexOfKey,
  keyAfterWrite,
  nextKey,
  nextSectionKey,
  previousKey,
  resolveSectionParam,
} from '../src/wizard/navigation.js'
import { describeSection } from '../src/wizard/summaries.js'

const keys = (steps) => steps.map((step) => step.key)

test('SECTIONS follow the backend order', () => {
  assert.deepEqual(SECTIONS.map((section) => section.id), [
    'household_profile', 'member_locations', 'transport', 'backup_transport',
    'primary_destination', 'backup_destination', 'responsibilities',
  ])
})

test('every non-empty section ends with a summary and the flow ends with review', () => {
  const plan = createEmptyHouseholdPlan()
  const steps = buildSteps(plan)
  const summaries = steps.filter((step) => step.kind === 'summary').map((step) => step.section)
  assert.deepEqual(summaries, SECTIONS.map((section) => section.id))
  assert.equal(steps.at(-1).key, 'review')
  assert.equal(new Set(keys(steps)).size, steps.length)
  for (const section of SECTIONS) {
    const own = steps.filter((step) => step.section === section.id)
    assert.equal(own.at(-1).kind, 'summary')
  }
})

test('with no private transport the backup transport section disappears', () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = false
  const sections = buildSteps(plan).filter((step) => step.kind === 'summary').map((step) => step.section)
  assert.ok(!sections.includes('backup_transport'))
  assert.equal(sections.length, 6)
})

test('next, previous and clamping', () => {
  const steps = buildSteps(createEmptyHouseholdPlan())
  assert.equal(nextKey(steps, steps[0].key), steps[1].key)
  assert.equal(previousKey(steps, steps[1].key), steps[0].key)
  assert.equal(previousKey(steps, steps[0].key), steps[0].key)
  assert.equal(nextKey(steps, 'review'), 'review')
  assert.equal(indexOfKey(steps, 'nope'), -1)
})

test('section jumps', () => {
  const steps = buildSteps(createEmptyHouseholdPlan())
  assert.equal(firstKeyOfSection(steps, 'transport'), 'transport:has')
  assert.equal(firstKeyOfSection(steps, 'nonexistent'), 'review')
  assert.equal(nextSectionKey(steps, 'household_profile'), 'locations:none')
  assert.equal(nextSectionKey(steps, 'responsibilities'), 'review')
})

test('nextSectionKey skips a section that has no steps', () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = false
  const steps = buildSteps(plan)
  assert.equal(nextSectionKey(steps, 'transport'), 'place:name')
})

test('keyAfterWrite advances past a surviving step and holds the slot of a vanished one', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self' })
  let steps = buildSteps(plan)
  const gateIndex = indexOfKey(steps, 'member:0:more')
  assert.ok(gateIndex > 0)
  assert.equal(keyAfterWrite(steps, 'member:0:more', gateIndex), steps[gateIndex + 1].key)
  plan.members.push({ member_id: 'm_b', display_name: '', relationship: null })
  steps = buildSteps(plan)
  assert.equal(indexOfKey(steps, 'member:0:more'), -1)
  assert.equal(keyAfterWrite(steps, 'member:0:more', gateIndex), 'member:1:name')
  assert.equal(previousKey(steps, 'member:1:name'), 'member:0:help')
})

test('resume picks the first incomplete section or nothing', () => {
  const sections = SECTIONS.map((section) => ({ section: section.id, status: 'complete' }))
  assert.equal(firstIncompleteSection({ sections }), null)
  sections[2].status = 'needs_information'
  sections[4].status = 'needs_information'
  assert.equal(firstIncompleteSection({ sections }), 'transport')
  assert.equal(firstIncompleteSection(null), null)
  assert.equal(firstIncompleteSection({}), null)
})

test('the section query accepts new ids, maps the old ones, and ignores the rest', () => {
  assert.equal(resolveSectionParam('transport'), 'transport')
  assert.equal(resolveSectionParam('backup_destination'), 'backup_destination')
  assert.equal(resolveSectionParam('people'), 'household_profile')
  assert.equal(resolveSectionParam('destinations'), 'primary_destination')
  assert.equal(resolveSectionParam('responsibilities'), 'responsibilities')
  assert.equal(resolveSectionParam('review'), 'review')
  assert.equal(resolveSectionParam('<script>'), null)
  assert.equal(resolveSectionParam(undefined), null)
  assert.equal(resolveSectionParam(['transport']), null)
})

test('describeSection reads like a short sentence for every section, even for an empty plan', () => {
  const empty = createEmptyHouseholdPlan()
  for (const section of SECTIONS) assert.equal(typeof describeSection(empty, section.id), 'string')
  assert.equal(describeSection(empty, 'household_profile'), 'No one added yet')

  const plan = createEmptyHouseholdPlan()
  plan.members.push(
    { member_id: 'm_a', display_name: 'Maya', usual_location: { kind: 'home', address: '1 St' } },
    { member_id: 'm_b', display_name: 'Sam', usual_location: null },
  )
  plan.animals.push({ animal_id: 'a_1', animal_type: 'dog', quantity: 2 })
  plan.has_private_transport = true
  plan.transports.push({ transport_id: 't_1', transport_type: 'ute', display_name: "Dad's" })
  plan.arrangements.primary_transport_id = 't_1'
  plan.arrangements.primary_destination = { display_name: "Nan's", address: '2 Hill Rd' }
  plan.arrangements.backup_arrangements.push({ transport_id: null, destination: { display_name: 'Library' } })
  plan.responsibilities.push({ responsibility_id: 'r_1', task_name: 'Drive', primary_member_id: 'm_a' })

  assert.equal(describeSection(plan, 'household_profile'), 'Maya, Sam. 1 animal')
  assert.equal(describeSection(plan, 'member_locations'), '1 of 2 people have a daytime place')
  assert.equal(describeSection(plan, 'transport'), "Dad's: Ute / Pickup. First choice: Dad's: Ute / Pickup")
  assert.equal(describeSection(plan, 'backup_transport'), 'No backup vehicle yet')
  assert.equal(describeSection(plan, 'primary_destination'), "Nan's, 2 Hill Rd")
  assert.equal(describeSection(plan, 'backup_destination'), 'Library')
  assert.equal(describeSection(plan, 'responsibilities'), '1 job')
  plan.has_private_transport = false
  assert.equal(describeSection(plan, 'transport'), 'No private vehicle')
  assert.equal(describeSection(plan, 'backup_transport'), 'Not needed without a vehicle')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardNavigation.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/flow.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/flow.js`:

```js
import { backupDestinationSteps } from './sections/backupDestination.js'
import { backupTransportSteps } from './sections/backupTransport.js'
import { householdProfileSteps } from './sections/householdProfile.js'
import { memberLocationSteps } from './sections/memberLocations.js'
import { primaryDestinationSteps } from './sections/primaryDestination.js'
import { responsibilitySteps } from './sections/responsibilities.js'
import { transportSteps } from './sections/transport.js'

// The order matches PlanCompletionService.SECTION_ORDER in the backend.
export const SECTIONS = [
  { id: 'household_profile', title: 'Your household', short: 'Household' },
  { id: 'member_locations', title: 'Where everyone is by day', short: 'Daytime' },
  { id: 'transport', title: 'How you would leave', short: 'Vehicle' },
  { id: 'backup_transport', title: 'If that vehicle is not available', short: 'Backup vehicle' },
  { id: 'primary_destination', title: 'Where you would go', short: 'Destination' },
  { id: 'backup_destination', title: 'Where you would go instead', short: 'Backup place' },
  { id: 'responsibilities', title: 'Who does what', short: 'Jobs' },
]

const BUILDERS = {
  household_profile: householdProfileSteps,
  member_locations: memberLocationSteps,
  transport: transportSteps,
  backup_transport: backupTransportSteps,
  primary_destination: primaryDestinationSteps,
  backup_destination: backupDestinationSteps,
  responsibilities: responsibilitySteps,
}

export function buildSteps(plan) {
  const steps = []
  for (const section of SECTIONS) {
    const questions = BUILDERS[section.id](plan)
    // An empty section (backup transport without a vehicle) is skipped whole.
    if (!questions.length) continue
    steps.push(...questions, { key: `summary:${section.id}`, section: section.id, kind: 'summary', optional: false })
  }
  steps.push({ key: 'review', section: null, kind: 'review', optional: false })
  return steps
}
```

Create `src/wizard/navigation.js`:

```js
import { SECTIONS } from './flow.js'

export function indexOfKey(steps, key) {
  return steps.findIndex((step) => step.key === key)
}

export function nextKey(steps, key) {
  return steps[indexOfKey(steps, key) + 1]?.key ?? 'review'
}

export function previousKey(steps, key) {
  const index = indexOfKey(steps, key)
  return steps[Math.max(index - 1, 0)]?.key ?? 'review'
}

// After an answer is written the list is rebuilt. If the step that was answered
// still exists, move past it. If it vanished (a "yes" turned the last-person
// gate into a new person's questions) the next step now occupies its slot.
export function keyAfterWrite(steps, previousStepKey, previousIndex) {
  const index = indexOfKey(steps, previousStepKey)
  const target = index === -1 ? Math.min(previousIndex, steps.length - 1) : index + 1
  return steps[target]?.key ?? 'review'
}

export function firstKeyOfSection(steps, sectionId) {
  return steps.find((step) => step.section === sectionId)?.key ?? 'review'
}

export function nextSectionKey(steps, sectionId) {
  const last = steps.findLastIndex((step) => step.section === sectionId)
  return steps[last + 1]?.key ?? 'review'
}

export function firstIncompleteSection(completion) {
  return completion?.sections?.find((section) => section.status !== 'complete')?.section ?? null
}

const LEGACY_SECTIONS = {
  people: 'household_profile',
  destinations: 'primary_destination',
}

export function resolveSectionParam(value) {
  if (typeof value !== 'string') return null
  if (value === 'review') return 'review'
  if (SECTIONS.some((section) => section.id === value)) return value
  return LEGACY_SECTIONS[value] ?? null
}
```

Create `src/wizard/summaries.js`:

```js
import { transportLabel } from './options.js'
import { memberTitle } from './labels.js'

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

export function describeSection(plan, sectionId) {
  const arrangements = plan.arrangements ?? {}
  const backups = arrangements.backup_arrangements ?? []

  switch (sectionId) {
    case 'household_profile': {
      if (!plan.members.length) return 'No one added yet'
      const names = plan.members.map((_, index) => memberTitle(plan, index)).join(', ')
      return plan.animals.length ? `${names}. ${plural(plan.animals.length, 'animal')}` : names
    }
    case 'member_locations': {
      if (!plan.members.length) return 'No one added yet'
      const placed = plan.members.filter((member) => member.usual_location).length
      return `${placed} of ${plan.members.length} ${placed === 1 && plan.members.length === 1 ? 'person has' : 'people have'} a daytime place`
    }
    case 'transport': {
      if (plan.has_private_transport === false) return 'No private vehicle'
      if (!plan.transports.length) return 'Not answered yet'
      const labels = plan.transports.map(transportLabel).join(', ')
      const primary = plan.transports.find((t) => t.transport_id === arrangements.primary_transport_id)
      return primary ? `${labels}. First choice: ${transportLabel(primary)}` : labels
    }
    case 'backup_transport': {
      if (plan.has_private_transport === false) return 'Not needed without a vehicle'
      const chosen = backups
        .map((backup) => plan.transports.find((t) => t.transport_id === backup.transport_id))
        .filter(Boolean)
      return chosen.length ? chosen.map(transportLabel).join(', ') : 'No backup vehicle yet'
    }
    case 'primary_destination': {
      const place = arrangements.primary_destination
      if (!place?.display_name) return 'No destination yet'
      return place.address ? `${place.display_name}, ${place.address}` : place.display_name
    }
    case 'backup_destination': {
      const names = backups.map((backup) => backup.destination?.display_name).filter(Boolean)
      return names.length ? names.join(', ') : 'No backup place yet'
    }
    case 'responsibilities':
      return plan.responsibilities.length ? plural(plan.responsibilities.length, 'job') : 'No jobs yet'
    default:
      return ''
  }
}
```

Note: `navigation.js` imports `SECTIONS` from `flow.js`, and `flow.js` does not import `navigation.js`, so there is no cycle.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardNavigation.test.js`
Expected: PASS (10 tests). If `describeSection` for `member_locations` fails on wording, the expected strings in the test are the source of truth for the wording; change the implementation to match.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard frontend/tests/wizardNavigation.test.js
git commit -m "feat(frontend): assemble the wizard flow with navigation and summaries"
```

---

### Task 6: The `useWizard` composable

**Files:**
- Create: `src/wizard/useWizard.js`
- Test: `tests/wizardUseWizard.test.js`

**Interfaces:**
- Consumes: `buildSteps`, navigation helpers (Task 5).
- Produces: `useWizard(plan)` where `plan` is a Vue `ref` holding the draft (or `null`). Returns `{ steps, current, currentIndex, currentKey, error, goTo(key), goToSection(id), skip(forKey), back(), submit(forKey, value) -> boolean }`. `submit` ignores a call whose `forKey` is not the current key, treats an empty answer for an empty field as a skip, runs `step.validate`, then writes and advances.

- [ ] **Step 1: Write the failing test**

Create `tests/wizardUseWizard.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { useWizard } from '../src/wizard/useWizard.js'

function start(plan = createEmptyHouseholdPlan(), key = 'member:0:name') {
  const draft = ref(plan)
  const wizard = useWizard(draft)
  wizard.goTo(key)
  return { draft, wizard }
}

test('answering a text question writes it and moves on', () => {
  const { draft, wizard } = start()
  assert.equal(wizard.currentKey.value, 'member:0:name')
  assert.equal(wizard.submit('member:0:name', 'Maya'), true)
  assert.equal(draft.value.members[0].display_name, 'Maya')
  assert.equal(wizard.currentKey.value, 'member:0:help')
})

test('skipping writes nothing and leaves the plan identical', () => {
  const { draft, wizard } = start()
  const before = JSON.stringify(draft.value)
  while (wizard.current.value.kind !== 'summary') {
    const step = wizard.current.value
    if (step.kind === 'yesno') break
    wizard.skip(step.key)
  }
  assert.equal(JSON.stringify(draft.value), before)
})

test('submitting an empty answer for an empty field counts as a skip', () => {
  const { draft, wizard } = start()
  assert.equal(wizard.submit('member:0:name', '   '), true)
  assert.equal(draft.value.members.length, 0)
  assert.equal(wizard.currentKey.value, 'member:0:help')
})

test('a stale submit aimed at a step that is no longer current is ignored', () => {
  const { draft, wizard } = start()
  wizard.submit('member:0:name', 'Maya')
  assert.equal(wizard.submit('member:0:name', 'Someone else'), false)
  assert.equal(draft.value.members[0].display_name, 'Maya')
  assert.equal(wizard.currentKey.value, 'member:0:help')
})

test('validation blocks Next with a message but skip still works', () => {
  const { draft, wizard } = start(createEmptyHouseholdPlan(), 'animals:any')
  wizard.submit('animals:any', true)
  assert.equal(wizard.currentKey.value, 'animal:0:category')
  wizard.goTo('animal:0:quantity')
  assert.equal(wizard.submit('animal:0:quantity', 0), false)
  assert.equal(wizard.error.value, 'Enter a whole number of at least 1.')
  assert.equal(draft.value.animals[0].quantity, 1)
  wizard.skip('animal:0:quantity')
  assert.equal(wizard.error.value, null)
  assert.equal(wizard.currentKey.value, 'animal:0:more')
})

test('"yes" at the last-person gate adds one person even when activated twice', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: null })
  const { draft, wizard } = start(plan, 'member:0:more')
  assert.equal(wizard.submit('member:0:more', true), true)
  assert.equal(wizard.submit('member:0:more', true), false)
  assert.equal(draft.value.members.length, 2)
  assert.equal(wizard.currentKey.value, 'member:1:name')
})

test('"no" at a gate moves to the next section question', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: null })
  const { wizard } = start(plan, 'member:0:more')
  wizard.submit('member:0:more', false)
  assert.equal(wizard.currentKey.value, 'animals:any')
})

test('back from a new person lands on the previous person, not a missing step', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: null })
  const { wizard } = start(plan, 'member:0:more')
  wizard.submit('member:0:more', true)
  wizard.back()
  assert.equal(wizard.currentKey.value, 'member:0:help')
  wizard.goTo('member:0:name')
  wizard.back()
  assert.equal(wizard.currentKey.value, 'member:0:name')
})

test('an unknown key falls back to the first step instead of crashing', () => {
  const { wizard } = start(createEmptyHouseholdPlan(), 'no-such-key')
  assert.equal(wizard.currentIndex.value, 0)
  assert.ok(wizard.current.value)
})

test('goToSection jumps to the first question of that section, or review when it has none', () => {
  const { wizard } = start()
  wizard.goToSection('transport')
  assert.equal(wizard.currentKey.value, 'transport:has')
  wizard.goToSection('does-not-exist')
  assert.equal(wizard.currentKey.value, 'review')
})

test('notices are skipped by submit; a null plan yields no steps', () => {
  const { wizard } = start(createEmptyHouseholdPlan(), 'locations:none')
  assert.equal(wizard.current.value.kind, 'notice')
  wizard.submit('locations:none', null)
  assert.notEqual(wizard.currentKey.value, 'locations:none')
  const empty = useWizard(ref(null))
  assert.deepEqual(empty.steps.value, [])
  assert.equal(empty.current.value, null)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardUseWizard.test.js`
Expected: FAIL with `Cannot find module '../src/wizard/useWizard.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/wizard/useWizard.js`:

```js
import { computed, ref } from 'vue'
import { buildSteps } from './flow.js'
import { firstKeyOfSection, indexOfKey, keyAfterWrite, nextKey, previousKey } from './navigation.js'

function isEmptyAnswer(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

export function useWizard(plan) {
  const currentKey = ref('review')
  const error = ref(null)

  const steps = computed(() => (plan.value ? buildSteps(plan.value) : []))
  const currentIndex = computed(() => Math.max(0, indexOfKey(steps.value, currentKey.value)))
  const current = computed(() => steps.value[currentIndex.value] ?? null)

  function goTo(key) {
    error.value = null
    currentKey.value = key
  }

  function goToSection(sectionId) {
    goTo(firstKeyOfSection(steps.value, sectionId))
  }

  function skip(forKey = currentKey.value) {
    if (current.value?.key !== forKey) return
    goTo(nextKey(steps.value, current.value.key))
  }

  function back() {
    if (!current.value) return
    goTo(previousKey(steps.value, current.value.key))
  }

  // `forKey` is the step the person was looking at when they acted. A second,
  // late activation of the same control targets a step that is no longer
  // current and must do nothing.
  function submit(forKey, value) {
    const step = current.value
    if (!step || step.key !== forKey) return false
    if (!step.write) {
      skip(forKey)
      return true
    }
    if (isEmptyAnswer(value) && isEmptyAnswer(step.read?.(plan.value))) {
      skip(forKey)
      return true
    }
    const message = step.validate?.(value, plan.value) ?? null
    error.value = message
    if (message) return false

    const index = currentIndex.value
    step.write(plan.value, value)
    goTo(keyAfterWrite(steps.value, step.key, index))
    return true
  }

  return { steps, current, currentIndex, currentKey, error, goTo, goToSection, skip, back, submit }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardUseWizard.test.js`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/wizard/useWizard.js frontend/tests/wizardUseWizard.test.js
git commit -m "feat(frontend): add the wizard state composable"
```

---

### Task 7: Question inputs, shell, progress bar, summary, review

**Files:**
- Create: `tests/helpers/loadComponent.js`, `src/components/wizard/questions/TextQuestion.vue`, `ChoiceQuestion.vue`, `MultiQuestion.vue`, `YesNoQuestion.vue`, `AddressQuestion.vue`, `NumberQuestion.vue`, `src/components/wizard/WizardShell.vue`, `ProgressBar.vue`, `SectionSummary.vue`, `ReviewScreen.vue`
- Test: `tests/wizardComponents.test.js`

**Interfaces:**
- Consumes: `buildSteps` steps (their `kind`, `prompt`, `helper`, `options`, `read`, `placeholder`, `maxLength`, `min`), `SECTIONS`, `describeSection`, `AddressAutocompleteInput`, `PlanChecks`, `LoadingState`.
- Produces:
  - `ProgressBar` props: `completion` (object or null), `currentSection` (string or null), `loading` (boolean). Renders `role="progressbar"`.
  - `WizardShell` props: `step` (object), `plan` (object), `error` (string or null), `canGoBack` (boolean). Emits: `submit(key, value)`, `skip(key)`, `back`, `select(key, suggestion)`, `add-vehicle`.
  - `SectionSummary` props: `section` (a `SECTIONS` entry), `text` (string), `needsAttention` (boolean), `saving` (boolean), `error` (string or null), `isEdit` (boolean). Emits: `save`, `back`.
  - `ReviewScreen` props: `plan`, `completion`, `completionLoading`, `editable` (array of section ids), `saving`. Emits: `edit(sectionId)`, `finish`.

- [ ] **Step 1: Write the failing test**

Create `tests/helpers/loadComponent.js`:

```js
import { readFile } from 'node:fs/promises'
import { compileScript, parse } from '@vue/compiler-sfc'

// Compile a real single-file component without a browser, resolving its relative
// imports (including other .vue files) to data: URLs. Same approach as the
// other component tests.
export async function loadComponent(path, base = import.meta.url) {
  const url = new URL(path, base)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: url.href, inlineTemplate: true }).content
  code = code.replace(/^import ['"][^'"]+['"]\s*$/gm, '')
  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    let resolved
    if (name.endsWith('.vue')) {
      resolved = await loadComponent(new URL(name, url).href, url)
    } else {
      resolved = name.startsWith('.')
        ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href
        : import.meta.resolve(name)
    }
    code = code.replace(match[0], `from '${resolved}'`)
  }
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

export async function importComponent(path) {
  return (await import(await loadComponent(path))).default
}
```

Create `tests/wizardComponents.test.js`:

```js
import assert from 'node:assert/strict'
import test from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { SECTIONS, buildSteps } from '../src/wizard/flow.js'
import { importComponent } from './helpers/loadComponent.js'

const render = async (path, props) => {
  const Component = await importComponent(path)
  return renderToString(createSSRApp(Component, props))
}

const completion = (done) => ({
  sections: SECTIONS.map((section, index) => ({
    section: section.id,
    status: index < done ? 'complete' : 'needs_information',
  })),
  immediate_checks: [],
})

test('the progress bar reports N of 7 in text, in ARIA, and per section', async () => {
  const html = await render('../src/components/wizard/ProgressBar.vue', {
    completion: completion(3), currentSection: 'transport', loading: false,
  })
  assert.match(html, /role="progressbar"/)
  assert.match(html, /aria-valuenow="3"/)
  assert.match(html, /aria-valuemax="7"/)
  assert.match(html, /3 of 7 sections complete/)
  assert.match(html, /Complete/)
  assert.match(html, /Needs information/)
  assert.match(html, /aria-current="step"/)
})

test('the progress bar shows 0 of 7 before the first save and survives loading', async () => {
  const none = await render('../src/components/wizard/ProgressBar.vue', {
    completion: null, currentSection: 'household_profile', loading: false,
  })
  assert.match(none, /0 of 7 sections complete/)
  const loading = await render('../src/components/wizard/ProgressBar.vue', {
    completion: completion(2), currentSection: null, loading: true,
  })
  assert.match(loading, /2 of 7 sections complete/)
})

test('the shell renders a text question with a label, helper, Skip and Next', async () => {
  const plan = createEmptyHouseholdPlan()
  const step = buildSteps(plan)[0]
  const html = await render('../src/components/wizard/WizardShell.vue', { step, plan, error: null, canGoBack: false })
  assert.match(html, /What is your name\?/)
  assert.match(html, /Skip for now/)
  assert.match(html, />Next</)
  assert.doesNotMatch(html, />Back</)
  assert.match(html, /<label/)
})

test('the shell shows an error as an alert tied to the input, and Back when allowed', async () => {
  const plan = createEmptyHouseholdPlan()
  const step = buildSteps(plan)[0]
  const html = await render('../src/components/wizard/WizardShell.vue', {
    step, plan, error: 'Please describe the animal.', canGoBack: true,
  })
  assert.match(html, /role="alert"[^>]*>Please describe the animal\./)
  assert.match(html, /aria-describedby/)
  assert.match(html, />Back</)
})

test('yes/no, choice, multi, address and number steps each render their control', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: { kind: 'home', address: '', latitude: null, longitude: null, verification_status: 'unverified' }, is_dependant: false, mobility_support_required: false })
  plan.animals.push({ animal_id: 'a_1', category: 'pet', animal_type: 'dog', quantity: 1 })
  const find = (key) => buildSteps(plan).find((step) => step.key === key)
  const html = (key) => render('../src/components/wizard/WizardShell.vue', { step: find(key), plan, error: null, canGoBack: true })

  assert.match(await html('animals:any'), />Yes</)
  assert.match(await html('animals:any'), />No</)
  assert.match(await html('location:0:kind'), /type="radio"/)
  assert.match(await html('member:0:help'), /type="checkbox"/)
  assert.match(await html('location:0:address'), /Victorian/)
  assert.match(await html('animal:0:quantity'), /type="number"/)
})

test('a vehicle prompt with no second vehicle offers to add one', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = true
  plan.transports.push({ transport_id: 't_1', transport_type: 'car', display_name: '', driver_member_ids: [] })
  plan.arrangements.primary_transport_id = 't_1'
  const step = buildSteps(plan).find((s) => s.key === 'backup:none')
  const html = await render('../src/components/wizard/WizardShell.vue', { step, plan, error: null, canGoBack: true })
  assert.match(html, /Add another vehicle/)
})

test('the section recap shows its text, a Save and continue button, and any error', async () => {
  const html = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'Maya, Sam', needsAttention: true, saving: false, error: 'Could not save.', isEdit: false,
  })
  assert.match(html, /Your household/)
  assert.match(html, /Maya, Sam/)
  assert.match(html, /Save and continue/)
  assert.match(html, /Some answers are still missing/)
  assert.match(html, /role="alert"[^>]*>Could not save\./)
  const edit = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'x', needsAttention: false, saving: false, isEdit: true, error: null,
  })
  assert.match(edit, /Save and return to review/)
  assert.doesNotMatch(edit, /Some answers are still missing/)
  const busy = await render('../src/components/wizard/SectionSummary.vue', {
    section: SECTIONS[0], text: 'x', needsAttention: false, saving: true, isEdit: false, error: null,
  })
  assert.match(busy, /Saving…/)
  assert.match(busy, /disabled/)
})

test('the review screen lists all seven sections with status, summary and Edit', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya', usual_location: null })
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: completion(2), completionLoading: false, editable: SECTIONS.map((s) => s.id), saving: false,
  })
  for (const section of SECTIONS) assert.match(html, new RegExp(section.title))
  assert.equal((html.match(/>Edit</g) ?? []).length, 7)
  assert.match(html, /Maya/)
  assert.match(html, /Save &amp; Review Plan/)
  assert.match(html, /Plan checks/)
})

test('the review screen hides Edit for a section that has no questions', async () => {
  const plan = createEmptyHouseholdPlan()
  plan.has_private_transport = false
  const editable = buildSteps(plan).filter((s) => s.kind === 'summary').map((s) => s.section)
  const html = await render('../src/components/wizard/ReviewScreen.vue', {
    plan, completion: completion(7), completionLoading: false, editable, saving: false,
  })
  assert.equal((html.match(/>Edit</g) ?? []).length, 6)
  assert.match(html, /Not needed without a vehicle/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardComponents.test.js`
Expected: FAIL with `ENOENT` for `ProgressBar.vue`.

- [ ] **Step 3: Write the implementation**

Create `src/components/wizard/questions/TextQuestion.vue`:

```vue
<script setup>
defineProps({
  id: { type: String, required: true },
  describedBy: { type: String, default: undefined },
  placeholder: { type: String, default: '' },
  maxLength: { type: Number, default: 200 },
})
const model = defineModel({ type: String, default: '' })
</script>

<template>
  <input
    :id="id"
    v-model="model"
    class="wizard-input"
    type="text"
    autocomplete="off"
    :placeholder="placeholder"
    :maxlength="maxLength"
    :aria-describedby="describedBy"
  />
</template>

<style scoped>
.wizard-input { width: 100%; border: 2px solid var(--color-border-strong); border-radius: 12px; background: var(--color-bg-card); color: var(--color-text); font-size: 1.125rem; min-height: 3.25rem; padding: 0.7rem 0.9rem; }
</style>
```

Create `src/components/wizard/questions/NumberQuestion.vue`:

```vue
<script setup>
defineProps({
  id: { type: String, required: true },
  describedBy: { type: String, default: undefined },
  min: { type: Number, default: 0 },
})
const model = defineModel({ default: 1 })
</script>

<template>
  <input
    :id="id"
    v-model.number="model"
    class="wizard-input"
    type="number"
    inputmode="numeric"
    :min="min"
    step="1"
    :aria-describedby="describedBy"
  />
</template>

<style scoped>
.wizard-input { width: 100%; max-width: 12rem; border: 2px solid var(--color-border-strong); border-radius: 12px; background: var(--color-bg-card); color: var(--color-text); font-size: 1.125rem; min-height: 3.25rem; padding: 0.7rem 0.9rem; }
</style>
```

Create `src/components/wizard/questions/ChoiceQuestion.vue`:

```vue
<script setup>
defineProps({
  name: { type: String, required: true },
  options: { type: Array, required: true },
  describedBy: { type: String, default: undefined },
})
const model = defineModel({ type: String, default: '' })
const emit = defineEmits(['pick'])
</script>

<template>
  <div class="choices" role="radiogroup" :aria-describedby="describedBy">
    <label v-for="[value, label] in options" :key="value" class="choice" :class="{ 'is-selected': model === value }">
      <input
        type="radio"
        :name="name"
        :value="value"
        :checked="model === value"
        @change="model = value; emit('pick', value)"
      />
      <span>{{ label }}</span>
    </label>
  </div>
</template>

<style scoped>
.choices { display: grid; gap: 0.6rem; }
.choice { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 14px; cursor: pointer; display: flex; font-size: 1.0625rem; gap: 0.75rem; min-height: 3.25rem; padding: 0.6rem 1rem; }
.choice:hover { background: var(--color-bg-card-muted); }
.choice.is-selected { background: var(--color-accent-soft); border-color: var(--color-accent-ink); font-weight: 700; }
.choice input { flex: none; height: 1.25rem; width: 1.25rem; }
.choice:focus-within { outline: 3px solid var(--color-focus); outline-offset: 2px; }
</style>
```

Create `src/components/wizard/questions/MultiQuestion.vue`:

```vue
<script setup>
defineProps({
  options: { type: Array, required: true },
  describedBy: { type: String, default: undefined },
})
const model = defineModel({ type: Array, default: () => [] })

function toggle(value) {
  model.value = model.value.includes(value)
    ? model.value.filter((item) => item !== value)
    : [...model.value, value]
}
</script>

<template>
  <div class="choices" role="group" :aria-describedby="describedBy">
    <label v-for="[value, label] in options" :key="value" class="choice" :class="{ 'is-selected': model.includes(value) }">
      <input type="checkbox" :value="value" :checked="model.includes(value)" @change="toggle(value)" />
      <span>{{ label }}</span>
    </label>
  </div>
</template>

<style scoped>
.choices { display: grid; gap: 0.6rem; }
.choice { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 14px; cursor: pointer; display: flex; font-size: 1.0625rem; gap: 0.75rem; min-height: 3.25rem; padding: 0.6rem 1rem; }
.choice:hover { background: var(--color-bg-card-muted); }
.choice.is-selected { background: var(--color-accent-soft); border-color: var(--color-accent-ink); font-weight: 700; }
.choice input { flex: none; height: 1.25rem; width: 1.25rem; }
.choice:focus-within { outline: 3px solid var(--color-focus); outline-offset: 2px; }
</style>
```

Create `src/components/wizard/questions/YesNoQuestion.vue`:

```vue
<script setup>
defineProps({ current: { type: [Boolean, null], default: null } })
const emit = defineEmits(['answer'])
</script>

<template>
  <div class="yesno">
    <button type="button" class="btn btn-accent btn-big" :aria-pressed="current === true" @click="emit('answer', true)">Yes</button>
    <button type="button" class="btn btn-primary btn-big" :aria-pressed="current === false" @click="emit('answer', false)">No</button>
  </div>
</template>

<style scoped>
.yesno { display: flex; flex-wrap: wrap; gap: 1rem; }
.btn-big { flex: 1 1 8rem; font-size: 1.125rem; min-height: 3.5rem; }
</style>
```

Create `src/components/wizard/questions/AddressQuestion.vue`:

```vue
<script setup>
import AddressAutocompleteInput from '../../common/AddressAutocompleteInput.vue'

defineProps({ label: { type: String, required: true }, helper: { type: String, default: '' } })
const model = defineModel({ type: String, default: '' })
const emit = defineEmits(['select'])
</script>

<template>
  <AddressAutocompleteInput
    v-model="model"
    :label="label"
    :helper-text="helper"
    placeholder="Start typing a Victorian street address"
    @select="emit('select', $event)"
  />
</template>
```

Create `src/components/wizard/ProgressBar.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { SECTIONS } from '../../wizard/flow'

const props = defineProps({
  completion: { type: Object, default: null },
  currentSection: { type: String, default: null },
  loading: { type: Boolean, default: false },
})

const statuses = computed(() =>
  SECTIONS.map((section) => ({
    ...section,
    complete: props.completion?.sections?.find((item) => item.section === section.id)?.status === 'complete',
    current: section.id === props.currentSection,
  })),
)
const done = computed(() => statuses.value.filter((item) => item.complete).length)
const total = SECTIONS.length
const text = computed(() => `${done.value} of ${total} sections complete`)
</script>

<template>
  <div class="progress" :aria-busy="loading">
    <div class="progress-head">
      <strong>{{ text }}</strong>
    </div>
    <div
      class="bar"
      role="progressbar"
      aria-label="Plan completion"
      aria-valuemin="0"
      :aria-valuemax="total"
      :aria-valuenow="done"
      :aria-valuetext="text"
    >
      <span class="fill" :style="{ width: `${(done / total) * 100}%` }"></span>
    </div>
    <ol class="markers">
      <li v-for="item in statuses" :key="item.id" :class="{ 'is-complete': item.complete, 'is-current': item.current }" :aria-current="item.current ? 'step' : undefined">
        <span class="dot" aria-hidden="true">{{ item.complete ? '✓' : '' }}</span>
        <span class="name">{{ item.short }}</span>
        <span class="sr-only">{{ item.complete ? 'Complete' : 'Needs information' }}</span>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.progress { display: grid; gap: 0.6rem; }
.progress-head { font-size: 0.9375rem; }
.bar { background: var(--color-bg-card-muted); border: 2px solid var(--color-border-strong); border-radius: 999px; height: 1rem; overflow: hidden; }
.fill { background: var(--color-accent); display: block; height: 100%; transition: width 0.3s ease; }
.markers { display: grid; gap: 0.35rem; grid-template-columns: repeat(7, minmax(0, 1fr)); list-style: none; margin: 0; padding: 0; }
.markers li { align-items: center; color: var(--color-text-muted); display: flex; flex-direction: column; font-size: 0.75rem; gap: 0.2rem; text-align: center; }
.dot { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 50%; display: inline-flex; font-size: 0.75rem; font-weight: 800; height: 1.3rem; justify-content: center; width: 1.3rem; }
.is-complete .dot { background: var(--color-success); border-color: var(--color-success); color: var(--color-text-inverse); }
.is-current { color: var(--color-text); font-weight: 800; }
.is-current .dot { background: var(--color-accent); border-color: var(--color-border-strong); }
@media (max-width: 600px) { .name { display: none; } }
</style>
```

Create `src/components/wizard/WizardShell.vue`:

```vue
<script setup>
import { nextTick, onMounted, ref, useId, watch } from 'vue'
import AddressQuestion from './questions/AddressQuestion.vue'
import ChoiceQuestion from './questions/ChoiceQuestion.vue'
import MultiQuestion from './questions/MultiQuestion.vue'
import NumberQuestion from './questions/NumberQuestion.vue'
import TextQuestion from './questions/TextQuestion.vue'
import YesNoQuestion from './questions/YesNoQuestion.vue'

const props = defineProps({
  step: { type: Object, required: true },
  plan: { type: Object, required: true },
  error: { type: String, default: null },
  canGoBack: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'skip', 'back', 'select', 'add-vehicle'])

const uid = useId()
const inputId = `${uid}-input`
const errorId = `${uid}-error`
const prompt = ref(null)
const value = ref(initial())

function initial() {
  return props.step.read ? props.step.read(props.plan) : null
}

// A question starts from what is already in the plan and takes focus, so a
// screen reader announces the prompt. The view re-keys the shell per question,
// so mounting is the usual path; the watcher covers a reused instance.
onMounted(() => prompt.value?.focus())
watch(() => props.step.key, async () => {
  value.value = initial()
  await nextTick()
  prompt.value?.focus()
})

const describedBy = () => (props.error ? errorId : undefined)

function submit() {
  emit('submit', props.step.key, value.value)
}

function answer(picked) {
  emit('submit', props.step.key, picked)
}
</script>

<template>
  <section class="shell" aria-labelledby="wizard-prompt">
    <h2 id="wizard-prompt" ref="prompt" class="prompt" tabindex="-1">{{ step.prompt }}</h2>
    <p v-if="step.helper" class="helper">{{ step.helper }}</p>

    <form class="body" @submit.prevent="submit">
      <template v-if="step.kind === 'text'">
        <label class="sr-only" :for="inputId">{{ step.prompt }}</label>
        <TextQuestion v-model="value" :id="inputId" :placeholder="step.placeholder ?? ''" :max-length="step.maxLength ?? 200" :described-by="describedBy()" />
      </template>

      <template v-else-if="step.kind === 'number'">
        <label class="sr-only" :for="inputId">{{ step.prompt }}</label>
        <NumberQuestion v-model="value" :id="inputId" :min="step.min ?? 0" :described-by="describedBy()" />
      </template>

      <ChoiceQuestion v-else-if="step.kind === 'choice' && step.options.length" v-model="value" :name="uid" :options="step.options" :described-by="describedBy()" @pick="answer" />

      <div v-else-if="step.kind === 'choice'" class="empty">
        <button v-if="step.addVehicle" type="button" class="btn btn-accent" @click="emit('add-vehicle')">Add another vehicle</button>
      </div>

      <MultiQuestion v-else-if="step.kind === 'multi'" v-model="value" :options="step.options" :described-by="describedBy()" />

      <AddressQuestion v-else-if="step.kind === 'address'" v-model="value" label="Address" :helper="step.helper ?? ''" @select="emit('select', step.key, $event)" />

      <YesNoQuestion v-else-if="step.kind === 'yesno'" :current="value" @answer="answer" />

      <p v-if="error" :id="errorId" class="field-error" role="alert">{{ error }}</p>

      <div class="controls">
        <button v-if="canGoBack" type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
        <span class="spacer"></span>
        <template v-if="step.kind !== 'yesno'">
          <button type="button" class="btn btn-ghost" @click="emit('skip', step.key)">Skip for now</button>
          <button type="submit" class="btn btn-accent">Next</button>
        </template>
      </div>
    </form>
  </section>
</template>

<style scoped>
.shell { display: grid; gap: 1rem; }
.prompt { font-size: clamp(1.6rem, 4vw, 2.25rem); line-height: 1.15; }
.prompt:focus { outline: none; }
.helper { color: var(--color-text-muted); font-size: 1.0625rem; }
.body { display: grid; gap: 1.25rem; margin-top: 0.5rem; }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; }
.spacer { flex: 1 1 0; }
.empty { display: grid; gap: 0.75rem; }
</style>
```

Create `src/components/wizard/SectionSummary.vue`:

```vue
<script setup>
defineProps({
  section: { type: Object, required: true },
  text: { type: String, required: true },
  needsAttention: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: null },
  isEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'back'])
</script>

<template>
  <section class="recap" aria-labelledby="recap-title">
    <p class="eyebrow">Section done</p>
    <h2 id="recap-title" class="title">{{ section.title }}</h2>
    <p class="text">{{ text }}</p>
    <p v-if="needsAttention" class="note">Some answers are still missing. You can save now and fill them in later.</p>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
    <div class="controls">
      <button type="button" class="btn btn-ghost" @click="emit('back')">Back</button>
      <span class="spacer"></span>
      <button type="button" class="btn btn-accent" :disabled="saving" @click="emit('save')">
        {{ saving ? 'Saving…' : isEdit ? 'Save and return to review' : 'Save and continue' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.recap { display: grid; gap: 0.9rem; }
.title { font-size: clamp(1.6rem, 4vw, 2.25rem); }
.text { font-size: 1.125rem; }
.note { color: var(--color-text-muted); }
.controls { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.spacer { flex: 1 1 0; }
</style>
```

Create `src/components/wizard/ReviewScreen.vue`:

```vue
<script setup>
import { SECTIONS } from '../../wizard/flow'
import { describeSection } from '../../wizard/summaries'
import LoadingState from '../common/LoadingState.vue'
import PlanChecks from '../completion/PlanChecks.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  completion: { type: Object, default: null },
  completionLoading: { type: Boolean, default: false },
  editable: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['edit', 'finish'])

function statusOf(id) {
  return props.completion?.sections?.find((item) => item.section === id)?.status === 'complete'
}
</script>

<template>
  <section class="review" aria-labelledby="review-title">
    <h2 id="review-title" class="title">Your plan so far</h2>
    <p class="helper">Check each part. Use Edit to change anything.</p>

    <LoadingState v-if="completionLoading && !completion" message="Checking your saved plan…" />
    <ul class="rows">
      <li v-for="section in SECTIONS" :key="section.id" class="row">
        <div class="row-main">
          <h3 class="row-title">{{ section.title }}</h3>
          <p class="row-text">{{ describeSection(plan, section.id) }}</p>
        </div>
        <span class="badge" :class="statusOf(section.id) ? 'badge-success' : 'badge-warning'">
          {{ statusOf(section.id) ? 'Complete' : 'Needs information' }}
        </span>
        <button v-if="editable.includes(section.id)" type="button" class="btn btn-ghost btn-sm" @click="emit('edit', section.id)">Edit</button>
      </li>
    </ul>

    <PlanChecks :completion="completion" :loading="completionLoading" />

    <div class="controls">
      <button type="button" class="btn btn-accent" :disabled="saving" @click="emit('finish')">Save &amp; Review Plan</button>
    </div>
  </section>
</template>

<style scoped>
.review { display: grid; gap: 1rem; }
.title { font-size: clamp(1.6rem, 4vw, 2.25rem); }
.helper { color: var(--color-text-muted); }
.rows { display: grid; gap: 0.75rem; list-style: none; margin: 0; padding: 0; }
.row { align-items: center; background: var(--color-bg-card); border: 2px solid var(--color-border-strong); border-radius: 16px; display: grid; gap: 0.5rem 1rem; grid-template-columns: minmax(0, 1fr) auto auto; padding: 0.9rem 1rem; }
.row-title { font-size: 1.0625rem; }
.row-text { color: var(--color-text-muted); font-size: 0.9375rem; overflow-wrap: anywhere; }
.controls { display: flex; justify-content: flex-end; margin-top: 0.5rem; }
@media (max-width: 600px) { .row { grid-template-columns: minmax(0, 1fr) auto; } .row .btn { grid-column: 1 / -1; justify-self: start; } }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/wizardComponents.test.js`
Expected: PASS (9 tests). If an assertion on markup text fails (for example `>Next<`), adjust the component markup to match the assertion; the test strings are the contract.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard frontend/tests/helpers frontend/tests/wizardComponents.test.js
git commit -m "feat(frontend): add the wizard question screens, progress bar and review screen"
```

---

### Task 8: Rewrite `PlanBuilderView` and update the old tests

**Files:**
- Modify (rewrite): `src/views/PlanBuilderView.vue`
- Modify: `tests/guidedJourney.test.js` (replace the first test and one assertion in the "dirty Review" test)
- Test: `tests/wizardView.test.js`

**Interfaces:**
- Consumes: `useWizard`, `SECTIONS`, `buildSteps`, navigation helpers, `describeSection`, `WizardShell`, `ProgressBar`, `SectionSummary`, `ReviewScreen`, `householdStore`, `saveAndReview`.
- Produces: the `/plan` page. Behaviour: starts at `?section=` (resolved with `resolveSectionParam`), else the first incomplete section, else Review (all complete), else the first question; `Save and continue` saves the draft then moves to the next section; **Edit** from Review opens that section and returns to Review after saving; `beforeunload` and route-leave warn while the draft has unsaved changes.

- [ ] **Step 1: Write the failing test**

Create `tests/wizardView.test.js` (source-level checks in the style of `guidedJourney.test.js`, since the view needs a router and store to render):

```js
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('the plan view is the wizard host and saves only through the household store', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  for (const name of ['WizardShell', 'ProgressBar', 'SectionSummary', 'ReviewScreen']) {
    assert.match(view, new RegExp(`import ${name} from`))
  }
  assert.match(view, /useWizard\(draft\)/)
  assert.equal((view.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  assert.match(view, /resolveSectionParam\(route\.query\.section\)/)
  assert.match(view, /firstIncompleteSection\(householdStore\.completion\)/)
  assert.match(view, /needsSave: hasUnsavedChanges\.value \|\| !householdStore\.planExists/)
  assert.match(view, /saveAndReview\(/)
})

test('unsaved answers are guarded on reload and on leaving the route', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  assert.match(view, /beforeunload/)
  assert.match(view, /onBeforeRouteLeave/)
  assert.match(view, /removeEventListener\('beforeunload'/)
})

test('the old stepper markup is gone from the view', async () => {
  const view = await source('../src/views/PlanBuilderView.vue')
  assert.doesNotMatch(view, /class="stepper"/)
  assert.doesNotMatch(view, /HouseholdMembersForm|TransportForm|ArrangementsForm|ResponsibilitiesForm/)
})

test('the final action label lives on the review screen', async () => {
  const review = await source('../src/components/wizard/ReviewScreen.vue')
  assert.match(review, /Save &amp; Review Plan/)
})
```

Then edit `tests/guidedJourney.test.js`:

1. Replace the entire first `test('editable steps offer a second Save ...', ...)` block (from `test('editable steps offer a second Save` through its closing `})`) with:

```js
test('the plan view saves one draft through the household store and the API client', async () => {
  const plan = await source('../src/views/PlanBuilderView.vue')
  const store = await source('../src/stores/household.js')
  const client = await source('../src/api/client.js')

  assert.equal((plan.match(/householdStore\.savePlan\(draft\.value\)/g) ?? []).length, 1)
  assert.match(store, /api\.saveHouseholdPlan\(id, next\)/)
  assert.match(client, /method: 'PUT',[\s\S]*?body: JSON\.stringify\(plan\)/)
})
```

2. In the second test (`dirty Review saves before navigation`), replace the line `assert.match(plan, /Save &amp; Review Plan/)` with:

```js
  const review = await source('../src/components/wizard/ReviewScreen.vue')
  assert.match(review, /Save &amp; Review Plan/)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/wizardView.test.js tests/guidedJourney.test.js`
Expected: FAIL in `wizardView.test.js` (the view still imports the old forms) and `guidedJourney.test.js` passes its remaining tests.

- [ ] **Step 3: Write the implementation**

Replace the whole of `src/views/PlanBuilderView.vue` with:

```vue
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHouseholdStore } from '../stores/household'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ProgressBar from '../components/wizard/ProgressBar.vue'
import ReviewScreen from '../components/wizard/ReviewScreen.vue'
import SectionSummary from '../components/wizard/SectionSummary.vue'
import WizardShell from '../components/wizard/WizardShell.vue'
import { SECTIONS } from '../wizard/flow'
import { firstIncompleteSection, nextSectionKey, resolveSectionParam } from '../wizard/navigation'
import { describeSection } from '../wizard/summaries'
import { useWizard } from '../wizard/useWizard'
import { transportAt } from '../wizard/wizardDraft'
import { saveAndReview } from '../utils/planReviewNavigation'

const householdStore = useHouseholdStore()
const route = useRoute()
const router = useRouter()

const draft = ref(null)
const wizard = useWizard(draft)
const returnToReview = ref(false)
const saveMessage = ref(null)

function resetDraft() {
  // The wizard edits this detached aggregate. Restoring the server plan after a
  // load or save makes the unsaved comparison clean. JSON cloning is safe because
  // HouseholdPlan is JSON-serialisable data.
  draft.value = householdStore.plan ? JSON.parse(JSON.stringify(householdStore.plan)) : null
}

function chooseStartingStep() {
  const requested = resolveSectionParam(route.query.section)
  if (requested === 'review') return wizard.goTo('review')
  if (requested) return wizard.goToSection(requested)
  if (!householdStore.planExists) return wizard.goToSection(SECTIONS[0].id)
  const incomplete = firstIncompleteSection(householdStore.completion)
  if (incomplete) return wizard.goToSection(incomplete)
  return wizard.goTo(householdStore.completion ? 'review' : wizard.steps.value[0]?.key ?? 'review')
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
    if (!draft.value) resetDraft()
  },
)

const hasUnsavedChanges = computed(() => {
  // A failed save leaves `householdStore.plan` unchanged, so the draft stays
  // dirty and can be retried without losing answers.
  if (!draft.value || !householdStore.plan) return false
  return JSON.stringify(draft.value) !== JSON.stringify(householdStore.plan)
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
const currentSection = computed(() => SECTIONS.find((section) => section.id === wizard.current.value?.section) ?? null)
const editableSections = computed(() => [...new Set(wizard.steps.value.filter((step) => step.kind === 'summary').map((step) => step.section))])
const sectionNeedsAttention = computed(() => {
  const status = householdStore.completion?.sections?.find((item) => item.section === currentSection.value?.id)?.status
  return status !== 'complete'
})

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

async function saveSection() {
  const sectionId = wizard.current.value?.section
  if (!(await save())) return
  if (returnToReview.value) {
    returnToReview.value = false
    wizard.goTo('review')
    return
  }
  wizard.goTo(nextSectionKey(wizard.steps.value, sectionId))
}

function editSection(sectionId) {
  returnToReview.value = true
  saveMessage.value = null
  wizard.goToSection(sectionId)
}

function addVehicle() {
  // Starts the next vehicle's questions in the transport section; the backup
  // section afterwards then offers that vehicle.
  const next = draft.value.transports.length
  draft.value.has_private_transport = true
  transportAt(draft.value, next)
  wizard.goTo(`vehicle:${next}:type`)
}

function selectAddress(key, suggestion) {
  const step = wizard.current.value
  if (step?.key === key) step.select?.(draft.value, suggestion)
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
      :current-section="currentSection?.id ?? null"
      :loading="householdStore.completionStatus === 'loading'"
    />

    <div class="stage">
      <LoadingState v-if="householdStore.planStatus === 'loading' || householdStore.planStatus === 'idle'" message="Loading your household plan…" />
      <ErrorState
        v-else-if="householdStore.planStatus === 'error'"
        message="Could not load your household plan."
        @retry="householdStore.loadPlan"
      />

      <template v-else-if="draft && wizard.current.value">
        <p v-if="currentSection && wizard.current.value.kind !== 'review'" class="where">
          {{ currentSection.title }} · {{ SECTIONS.indexOf(currentSection) + 1 }} of {{ SECTIONS.length }}
        </p>

        <SectionSummary
          v-if="wizard.current.value.kind === 'summary'"
          :section="currentSection"
          :text="describeSection(draft, currentSection.id)"
          :needs-attention="sectionNeedsAttention"
          :saving="saving"
          :error="saveMessage"
          :is-edit="returnToReview"
          @save="saveSection"
          @back="wizard.back()"
        />

        <ReviewScreen
          v-else-if="wizard.current.value.kind === 'review'"
          :plan="draft"
          :completion="householdStore.completion"
          :completion-loading="householdStore.completionStatus === 'loading'"
          :editable="editableSections"
          :saving="saving"
          @edit="editSection"
          @finish="reviewPlan"
        />

        <WizardShell
          v-else
          :key="wizard.current.value.key"
          :step="wizard.current.value"
          :plan="draft"
          :error="wizard.error.value"
          :can-go-back="wizard.currentIndex.value > 0"
          @submit="wizard.submit"
          @skip="wizard.skip"
          @back="wizard.back()"
          @select="selectAddress"
          @add-vehicle="addVehicle"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan-wizard { display: grid; gap: 1.75rem; margin: 0 auto; max-width: 44rem; width: 100%; }
.stage { background: var(--color-bg-card); border: var(--border-width) solid var(--color-border-strong); border-radius: 28px; box-shadow: var(--shadow-card); min-width: 0; padding: clamp(1.25rem, 4vw, 2.25rem); }
.where { color: var(--color-text-muted); font-size: 0.875rem; font-weight: 700; margin-bottom: 0.75rem; }
</style>
```

- [ ] **Step 4: Run the whole suite and a build**

Run: `cd frontend && npm test`
Expected: PASS for every file. Count should be the previous 153 minus the replaced guidedJourney test plus the new wizard tests.

Run: `cd frontend && npm run build`
Expected: `built in ...` with no errors.

If `guidedJourney.test.js` still has an assertion about `needsSave: hasUnsavedChanges.value || !householdStore.planExists`, it passes because that exact expression is kept in `reviewPlan`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/PlanBuilderView.vue frontend/tests/wizardView.test.js frontend/tests/guidedJourney.test.js
git commit -m "feat(frontend): turn the plan builder into a one-question-at-a-time wizard"
```

---

### Task 9: Run it in a browser and fix what it shows

**Files:**
- Modify: whichever wizard files the walkthrough shows need changes (styling in the wizard components, copy in `src/wizard/sections/*.js`).
- No new test file unless a bug is found; a found bug gets a regression test in the matching `tests/wizard*.test.js` first.

**Interfaces:** none new.

- [ ] **Step 1: Start an isolated mock backend and the dev server**

Do not use the developer's own backend on port 8000. From the repo root:

```bash
cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock .venv/bin/uvicorn app.main:app --port 8011 &
```

Create a temporary Vite config outside the repo (in the session scratchpad) that sets `root` to `frontend`, `server.port` to `5200` with `strictPort`, and proxies `/api` to `http://127.0.0.1:8011`, then run `node_modules/.bin/vite --config <that file>` from `frontend/`. Expected: both servers answer; `http://localhost:5200/plan` loads.

- [ ] **Step 2: Walk the wizard end to end**

In the browser at `http://localhost:5200/plan`, with a fresh household, check each of these and note any problem:

1. The first screen is "What is your name?" with the progress bar at 0 of 7.
2. Answer two people (second one related as "Other" to see the description question), say no more people, then add one animal of type "Other" and see the description question; leave quantity at 0 and see the error; fix it.
3. Reach the section recap, press **Save and continue**; the bar shows 1 of 7.
4. Daytime place for each person (one "Work" with a typed address; one suggestion if the mock provides them).
5. Answer "No" to a vehicle; confirm the backup section is skipped and the bar moves to 3 of 7 after saving.
6. Use the browser Back to confirm Back from a second person's name returns to the first person's last question.
7. Press **Skip for now** on every question of a section and confirm the section still saves.
8. Finish destinations and a responsibility with a backup person; confirm the Review screen shows seven rows, statuses, summaries and **Edit**.
9. **Edit** a section, change an answer, **Save and return to review**; confirm it returns to Review.
10. Reload mid-section: the browser warns about unsaved answers when something changed; after a save, reload opens the first incomplete section or Review.
11. Open `/plan?section=destinations` and `/plan?section=nonsense`.
12. Tab through one question using only the keyboard; confirm the focus ring, that focus lands on the question after Next, and that Enter submits.
13. Narrow the window to phone width (about 390px) and repeat a few questions.

- [ ] **Step 3: Fix what the walkthrough found**

For every defect: write a failing test in the matching `tests/wizard*.test.js` when it is logic, fix it, rerun `npm test`. For layout or copy problems, fix the component or section file directly and re-check in the browser. Keep a short list of what was changed for the final report.

- [ ] **Step 4: Final verification**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass and the build succeeds. Stop the temporary servers and delete the temporary Vite config.

- [ ] **Step 5: Commit**

```bash
git add -A frontend
git commit -m "fix(frontend): polish the plan wizard after a browser walkthrough"
```

(Skip this commit if Step 3 changed nothing.)

---

## Self-review notes

- **Spec coverage:** seven sections and their complete rules (Tasks 2-4); skip on every question (Task 6 `skip`, Task 7 shell); explicit save per section and progress from the backend (Task 8 `saveSection`, Task 7 `ProgressBar`); Review with Edit and return (Tasks 7-8); resume and legacy `?section` (Tasks 5, 8); validation (Tasks 2-4 `validate`, Task 6 `submit`); focus, 44px, reduced motion (Task 7 shell and existing global CSS); unsaved guard (Task 8); tests per the spec's list (Tasks 1-8) plus the manual walkthrough (Task 9). The old four form components are intentionally left in the tree (spec "Out of scope").
- **Type consistency:** step keys, `question()` fields, and helper names are the same everywhere they appear; `useWizard` returns exactly the names the view uses (`submit`, `skip`, `back`, `goTo`, `goToSection`, `current`, `currentIndex`, `steps`, `error`).
- **Known follow-ups, not part of this plan:** delete the four unused form components; remove the now-unreachable dark theme rules; per-backup choice of transport for entries after the first is not asked in the wizard (the first backup vehicle and any number of backup places are).
