import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import { backupTransportSteps } from '../src/wizard/sections/backupTransport.js'
import { transportSteps } from '../src/wizard/sections/transport.js'
import { removeMember } from '../src/wizard/wizardDraft.js'

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

test('answering no vehicle removes private vehicles and every reference to them, so the backend accepts the plan', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  byKey(transportSteps(plan), 'vehicle:0:more').write(plan, true)
  const [first, second] = plan.transports.map((t) => t.transport_id)
  plan.transports.push({ transport_id: 't_taxi', transport_type: 'other', transport_type_other: 'Taxi', display_name: '', driver_member_ids: [] })
  plan.arrangements.primary_transport_id = first
  plan.arrangements.backup_arrangements.push({ transport_id: second, destination: { destination_id: 'd_1', display_name: 'Hall' } })

  byKey(transportSteps(plan), 'transport:has').write(plan, false)

  const privateTypes = new Set(['car', 'ute', 'van', 'motorbike', 'truck'])
  assert.ok(plan.transports.every((t) => !privateTypes.has(t.transport_type)))
  assert.deepEqual(plan.transports.map((t) => t.transport_id), ['t_taxi'])
  assert.equal(plan.arrangements.primary_transport_id, null)
  assert.equal(plan.arrangements.backup_arrangements[0].transport_id, null)
  assert.equal(plan.arrangements.backup_arrangements[0].destination.display_name, 'Hall')
})

test('removing a vehicle clears the choices that pointed at it; the first question offers Remove', () => {
  const plan = createEmptyHouseholdPlan()
  byKey(transportSteps(plan), 'transport:has').write(plan, true)
  byKey(transportSteps(plan), 'vehicle:0:more').write(plan, true)
  const [first, second] = plan.transports.map((t) => t.transport_id)
  plan.arrangements.primary_transport_id = first
  plan.arrangements.backup_arrangements.push({ transport_id: second, destination: null })
  const steps = transportSteps(plan)
  assert.equal(byKey(steps, 'vehicle:1:type').remove.label, 'Remove this vehicle')
  byKey(steps, 'vehicle:1:type').remove.run(plan)
  assert.deepEqual(plan.transports.map((t) => t.transport_id), [first])
  assert.equal(plan.arrangements.backup_arrangements[0].transport_id, null)
  byKey(transportSteps(plan), 'vehicle:0:type').remove.run(plan)
  assert.equal(plan.arrangements.primary_transport_id, null)
})

test('removing a person also removes them from drivers and jobs', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' }, { member_id: 'm_b', display_name: 'Sam' })
  plan.transports.push({ transport_id: 't_1', transport_type: 'car', display_name: '', driver_member_ids: ['m_a', 'm_b'] })
  plan.responsibilities.push({ responsibility_id: 'r_1', task_name: 'Drive', primary_member_id: 'm_b', backup_member_id: 'm_a' })
  const gone = plan.members[1]
  removeMember(plan, gone.member_id)
  assert.deepEqual(plan.members.map((m) => m.member_id), ['m_a'])
  assert.deepEqual(plan.transports[0].driver_member_ids, ['m_a'])
  assert.equal(plan.responsibilities[0].primary_member_id, null)
  assert.equal(plan.responsibilities[0].backup_member_id, 'm_a')
})
