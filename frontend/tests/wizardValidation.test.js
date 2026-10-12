import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { describeScreen } from '../src/wizard/summaries.js'
import { finalisePlan, finalisedClone, validateScreen } from '../src/wizard/validation.js'
import { addAnimal, addJob, addMember, setAnimalType, setHasVehicle, setVehicleType } from '../src/wizard/formActions.js'
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
