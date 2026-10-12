import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { describeScreen } from '../src/wizard/summaries.js'
import { finalisePlan, finalisedClone, validatePlan, validateScreen } from '../src/wizard/validation.js'
import { addAnimal, addJob, addMember, setAnimalType, setHasVehicle, setJobMain, setVehicleType } from '../src/wizard/formActions.js'
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

test('finalising drops blank jobs, destinations and places and trims names; filled cards stay', () => {
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

  // The blank first card stays while a later person is kept (see the next tests).
  assert.deepEqual(plan.members.map((m) => m.display_name), ['', 'Sam'])
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

test('finalising removes a blank person from drivers and jobs, leaving no dangling id', () => {
  const plan = createEmptyHouseholdPlan()
  const ann = addMember(plan)
  ann.display_name = 'Ann'
  const blank = addMember(plan)
  setHasVehicle(plan, true)
  plan.transports[0].driver_member_ids = [ann.member_id, blank.member_id]
  const job = addJob(plan)
  job.task_name = 'Drive the household'
  setJobMain(job, blank.member_id)
  job.backup_member_id = ann.member_id

  finalisePlan(plan)

  assert.deepEqual(plan.members.map((m) => m.display_name), ['Ann'])
  assert.deepEqual(plan.transports[0].driver_member_ids, [ann.member_id])
  assert.equal(plan.responsibilities[0].primary_member_id, null)
})

test('a blank first card is kept while later people exist, so the second person never becomes "You"', () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan) // blank "You"
  const sam = addMember(plan)
  sam.display_name = 'Sam'
  sam.relationship = 'partner'

  finalisePlan(plan)

  assert.equal(plan.members.length, 2)
  assert.equal(plan.members[0].relationship, 'self')
  assert.equal(plan.members[1].display_name, 'Sam')
})

test('a lone blank first card is still dropped', () => {
  const plan = createEmptyHouseholdPlan()
  addMember(plan)
  finalisePlan(plan)
  assert.equal(plan.members.length, 0)
})

test('validating the whole plan finds a problem on a screen the person skipped, and names the screen', () => {
  const plan = createEmptyHouseholdPlan()
  addAnimal(plan)
  plan.animals[0].quantity = ''
  const problems = validatePlan(plan)
  assert.deepEqual(problems.map((p) => [p.screen, p.field]), [['household', 'animal:0:quantity']])
  plan.animals[0].quantity = 2
  assert.deepEqual(validatePlan(plan), [])
})
