import assert from 'node:assert/strict'
import test from 'node:test'
import { createEmptyHouseholdPlan } from '../src/domain/householdPlan.js'
import {
  addJob, addMember, addVehicle, memberHelpValues, setAnimalCategory, setAnimalsAny, setAnimalType,
  setFirstVehicle, setHasVehicle, setJobMain, setMemberHelp, setMemberRelationship, setTaskChoice,
  setVehicleType, taskChoice,
} from '../src/wizard/formActions.js'
import { backupTransportIds, removeMember, setBackupTransports } from '../src/wizard/wizardDraft.js'

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

test('choosing a vehicle as the first choice removes it from the backups', () => {
  const plan = createEmptyHouseholdPlan()
  setHasVehicle(plan, true)
  addVehicle(plan)
  const [a, b] = plan.transports.map((vehicle) => vehicle.transport_id)
  setBackupTransports(plan, [a, b])

  setFirstVehicle(plan, a)

  assert.equal(plan.arrangements.primary_transport_id, a)
  assert.deepEqual(backupTransportIds(plan), [b])
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
