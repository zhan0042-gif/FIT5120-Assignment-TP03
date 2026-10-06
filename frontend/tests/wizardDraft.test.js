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
