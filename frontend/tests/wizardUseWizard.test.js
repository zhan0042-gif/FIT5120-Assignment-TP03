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

test('Next on a required description with nothing typed shows its error instead of skipping', () => {
  const plan = createEmptyHouseholdPlan()
  plan.animals.push({ animal_id: 'a_1', category: 'pet', animal_type: 'other', animal_type_other: null, quantity: 1 })
  const { wizard } = start(plan, 'animal:0:type_other')
  assert.equal(wizard.submit('animal:0:type_other', ''), false)
  assert.equal(wizard.error.value, 'Please describe the animal.')
  assert.equal(wizard.currentKey.value, 'animal:0:type_other')
  wizard.skip('animal:0:type_other')
  assert.equal(wizard.currentKey.value, 'animal:0:quantity')
})

test('removeCurrent removes the record behind the current question and returns to its section', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push(
    { member_id: 'm_a', display_name: 'Maya', relationship: 'self', usual_location: null },
    { member_id: 'm_b', display_name: 'Sam', relationship: 'partner', usual_location: null },
  )
  const { draft, wizard } = start(plan, 'member:1:name')
  assert.equal(wizard.removeCurrent('member:0:name'), false)
  assert.equal(draft.value.members.length, 2)
  assert.equal(wizard.removeCurrent('member:1:name'), true)
  assert.deepEqual(draft.value.members.map((m) => m.display_name), ['Maya'])
  assert.equal(wizard.currentKey.value, 'member:0:name')
  assert.equal(wizard.removeCurrent('member:0:name'), true)
  assert.equal(draft.value.members.length, 0)
})
