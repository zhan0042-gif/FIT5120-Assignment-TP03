import { ANIMAL_TYPES, TASK_PRESETS } from './options.js'
import {
  animalAt, backupAt, backupTransportIds, memberAt, removePrivateTransports, responsibilityAt,
  setBackupTransports, transportAt,
} from './wizardDraft.js'

export const HELP_OPTIONS = [
  ['dependant', 'Depends on someone else to leave, such as a young child'],
  ['mobility', 'Needs help moving or getting into a vehicle'],
]

export const memberHelpValues = (member) =>
  [member.is_dependant && 'dependant', member.mobility_support_required && 'mobility'].filter(Boolean)

export function setMemberHelp(member, values) {
  member.is_dependant = values.includes('dependant')
  member.mobility_support_required = values.includes('mobility')
}

export function addMember(plan) {
  const member = memberAt(plan, plan.members.length)
  if (plan.members.length === 1 && member.relationship === null) member.relationship = 'self'
  return member
}

export function setMemberRelationship(member, value) {
  member.relationship = value || null
  if (value !== 'other') member.relationship_other = null
}

export function setAnimalsAny(plan, yes) {
  if (yes) {
    if (!plan.animals.length) animalAt(plan, 0)
  } else {
    plan.animals.splice(0)
  }
}

export const addAnimal = (plan) => animalAt(plan, plan.animals.length)

export function setAnimalCategory(animal, value) {
  // The same category again must keep the kind already chosen.
  if (animal.category === value) return
  animal.category = value
  animal.animal_type = ANIMAL_TYPES[value][0][0]
  animal.animal_type_other = null
}

export function setAnimalType(animal, value) {
  animal.animal_type = value
  if (value !== 'other') animal.animal_type_other = null
}

export function setHasVehicle(plan, yes) {
  plan.has_private_transport = yes
  if (yes) {
    if (!plan.transports.length) transportAt(plan, 0)
    return
  }
  // The backend rejects "no private transport" beside private vehicle records,
  // and only counts it complete while no first vehicle is set.
  removePrivateTransports(plan)
  plan.arrangements ??= {}
  plan.arrangements.primary_transport_id = null
}

export const addVehicle = (plan) => transportAt(plan, plan.transports.length)

export function setVehicleType(vehicle, value) {
  vehicle.transport_type = value
  if (value !== 'other') vehicle.transport_type_other = null
}

export function setFirstVehicle(plan, id) {
  plan.arrangements ??= {}
  plan.arrangements.primary_transport_id = id || null
  // A vehicle cannot be both the first choice and its own backup.
  if (id) setBackupTransports(plan, backupTransportIds(plan).filter((backup) => backup !== id))
}

// Returns the backup entry that will hold the new place; the Places screen
// creates its destination through backupDestination(plan, index).
export function addBackupPlace(plan) {
  const entries = plan.arrangements?.backup_arrangements ?? []
  const target = entries.findIndex((entry) => !entry.destination)
  return backupAt(plan, target === -1 ? entries.length : target)
}

export const addJob = (plan) => responsibilityAt(plan, plan.responsibilities.length)

// '' = nothing chosen, a preset name, or 'other'. A single space in `task_name`
// means "Something else" was chosen but nothing is typed yet.
export function taskChoice(item) {
  const name = item.task_name ?? ''
  if (name === '') return ''
  return TASK_PRESETS.includes(name) ? name : 'other'
}

export function setTaskChoice(item, value) {
  if (value === 'other') {
    if (TASK_PRESETS.includes(item.task_name) || !item.task_name) item.task_name = ' '
  } else {
    item.task_name = value
  }
}

export function setJobMain(item, memberId) {
  item.primary_member_id = memberId || null
  // The backend rejects a backup person who is also the main person.
  if (item.backup_member_id && item.backup_member_id === item.primary_member_id) item.backup_member_id = null
}
