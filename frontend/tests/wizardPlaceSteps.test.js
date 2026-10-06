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

test('pressing Next on "Something else" keeps a custom job name', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' })
  plan.responsibilities.push({ responsibility_id: 'r_1', task_name: 'Feed the chickens', primary_member_id: null, backup_member_id: null })
  byKey(responsibilitySteps(plan), 'resp:0:task').write(plan, 'other')
  assert.equal(plan.responsibilities[0].task_name, 'Feed the chickens')
  plan.responsibilities[0].task_name = 'Drive the household'
  byKey(responsibilitySteps(plan), 'resp:0:task').write(plan, 'other')
  assert.equal(plan.responsibilities[0].task_name, '')
})

test('choosing the backup person as the main person clears the backup', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' }, { member_id: 'm_b', display_name: 'Sam' })
  plan.responsibilities.push({ responsibility_id: 'r_1', task_name: 'Drive the household', primary_member_id: 'm_a', backup_member_id: 'm_b' })
  byKey(responsibilitySteps(plan), 'resp:0:primary').write(plan, 'm_b')
  assert.equal(plan.responsibilities[0].primary_member_id, 'm_b')
  assert.equal(plan.responsibilities[0].backup_member_id, null)
})

test('jobs and backup places can be removed from their first question', () => {
  const plan = createEmptyHouseholdPlan()
  plan.members.push({ member_id: 'm_a', display_name: 'Maya' })
  plan.responsibilities.push({ responsibility_id: 'r_1', task_name: 'Drive', primary_member_id: 'm_a', backup_member_id: null })
  plan.arrangements.backup_arrangements.push(
    { transport_id: null, destination: { destination_id: 'd_1', display_name: 'Library' } },
    { transport_id: 't_1', destination: { destination_id: 'd_2', display_name: 'Hall' } },
  )
  const job = byKey(responsibilitySteps(plan), 'resp:0:task')
  assert.equal(job.remove.label, 'Remove this job')
  job.remove.run(plan)
  assert.equal(plan.responsibilities.length, 0)

  const places = backupDestinationSteps(plan)
  assert.equal(byKey(places, 'backupplace:0:name').remove.label, 'Remove this place')
  byKey(places, 'backupplace:0:name').remove.run(plan)
  assert.equal(plan.arrangements.backup_arrangements.length, 1)
  byKey(backupDestinationSteps(plan), 'backupplace:0:name').remove.run(plan)
  assert.equal(plan.arrangements.backup_arrangements.length, 1)
  assert.equal(plan.arrangements.backup_arrangements[0].transport_id, 't_1')
  assert.equal(plan.arrangements.backup_arrangements[0].destination, null)
})
