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
