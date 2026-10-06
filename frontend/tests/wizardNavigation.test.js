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
