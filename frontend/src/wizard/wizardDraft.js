import { newId } from '../api/client.js'

export function newMember() {
  return {
    member_id: newId('m'),
    display_name: '',
    is_dependant: false,
    mobility_support_required: false,
    support_notes: null,
    relationship: null,
    usual_location: null,
    relationship_other: null,
  }
}

export function newAnimal() {
  return {
    animal_id: newId('a'),
    category: 'pet',
    display_name: '',
    animal_type: 'dog',
    animal_type_other: null,
    quantity: 1,
    support_notes: null,
  }
}

export function newTransport(type = 'car') {
  return {
    transport_id: newId('t'),
    transport_type: type,
    transport_type_other: null,
    display_name: '',
    driver_member_ids: [],
  }
}

export function newResponsibility(taskName = '') {
  return {
    responsibility_id: newId('r'),
    task_name: taskName,
    primary_member_id: null,
    backup_member_id: null,
  }
}

export function newDestination() {
  return {
    destination_id: newId('d'),
    display_name: '',
    address: null,
    canonical_address: null,
    unit_number: null,
    street_number: null,
    street_name: null,
    suburb_or_locality: null,
    state: 'VIC',
    postcode: null,
    country: 'Australia',
    latitude: null,
    longitude: null,
    verification_status: 'unverified',
    verified_at: null,
    selected_address: null,
  }
}

export function newBackupArrangement() {
  return { transport_id: null, destination: null }
}

function itemAt(list, index, create) {
  while (list.length <= index) list.push(create())
  return list[index]
}

export const memberAt = (plan, index) => itemAt(plan.members, index, newMember)
export const animalAt = (plan, index) => itemAt(plan.animals, index, newAnimal)
export const transportAt = (plan, index) => itemAt(plan.transports, index, () => newTransport())
export const responsibilityAt = (plan, index) => itemAt(plan.responsibilities, index, () => newResponsibility())

export function backupAt(plan, index) {
  plan.arrangements ??= {}
  plan.arrangements.backup_arrangements ??= []
  return itemAt(plan.arrangements.backup_arrangements, index, newBackupArrangement)
}

export function primaryDestination(plan) {
  plan.arrangements ??= {}
  plan.arrangements.primary_destination ??= newDestination()
  return plan.arrangements.primary_destination
}

export function backupDestination(plan, index) {
  const backup = backupAt(plan, index)
  backup.destination ??= newDestination()
  return backup.destination
}

export function setUsualKind(member, kind) {
  // Answering the same kind again (Next on a pre-filled question) must not wipe
  // the address already entered.
  if ((member.usual_location?.kind ?? '') === kind) return
  // Changing the kind discards coordinates: they belonged to the previous place.
  member.usual_location = kind
    ? { kind, address: '', latitude: null, longitude: null, verification_status: 'unverified' }
    : null
}

export function setUsualAddress(member, address) {
  // Typed text is not a verified place. Clearing the flag makes the backend
  // resolve it again on the next save.
  const location = member.usual_location
  if (!location) return
  if (location.address !== address) {
    location.latitude = null
    location.longitude = null
    location.verification_status = 'unverified'
    // Otherwise the backend would resolve the earlier suggestion instead of
    // the text now typed.
    location.selected_address = null
  }
  location.address = address
}

export function selectUsualAddress(member, suggestion) {
  // Suggestions carry no coordinates; selected_address tells the backend which
  // candidate to resolve.
  setUsualAddress(member, suggestion.address)
  if (member.usual_location) member.usual_location.selected_address = suggestion.address
}

export function resetDestinationVerification(destination) {
  // Canonical fields describe the previous official address. Editing the text
  // must clear them rather than show stale verification.
  destination.canonical_address = null
  destination.unit_number = null
  destination.street_number = null
  destination.street_name = null
  destination.suburb_or_locality = null
  destination.state = null
  destination.postcode = null
  destination.country = null
  destination.latitude = null
  destination.longitude = null
  destination.verification_status = 'unverified'
  destination.verified_at = null
  destination.selected_address = null
}

export function setDestinationAddress(destination, address) {
  if (destination.address !== address) resetDestinationVerification(destination)
  destination.address = address || null
}

export function selectDestinationAddress(destination, suggestion) {
  setDestinationAddress(destination, suggestion.address)
  destination.selected_address = suggestion.address
}

const PRIVATE_TRANSPORT_TYPES = ['car', 'ute', 'van', 'motorbike', 'truck']

export function removeMember(plan, memberId) {
  plan.members = plan.members.filter((member) => member.member_id !== memberId)
  for (const transport of plan.transports) {
    transport.driver_member_ids = (transport.driver_member_ids ?? []).filter((id) => id !== memberId)
  }
  for (const item of plan.responsibilities) {
    if (item.primary_member_id === memberId) item.primary_member_id = null
    if (item.backup_member_id === memberId) item.backup_member_id = null
  }
}

export function removeAnimal(plan, index) {
  plan.animals.splice(index, 1)
}

export function removeTransport(plan, transportId) {
  plan.transports = plan.transports.filter((transport) => transport.transport_id !== transportId)
  if (plan.arrangements?.primary_transport_id === transportId) plan.arrangements.primary_transport_id = null
  for (const backup of plan.arrangements?.backup_arrangements ?? []) {
    if (backup.transport_id === transportId) backup.transport_id = null
  }
}

// The backend rejects "no private transport" next to private vehicle records.
export function removePrivateTransports(plan) {
  const ids = plan.transports
    .filter((transport) => PRIVATE_TRANSPORT_TYPES.includes(transport.transport_type))
    .map((transport) => transport.transport_id)
  for (const id of ids) removeTransport(plan, id)
}

export function removeResponsibility(plan, index) {
  plan.responsibilities.splice(index, 1)
}

// A backup entry holds a vehicle and a place. Removing the place keeps the
// vehicle choice, and drops the entry only when nothing else is in it.
export function removeBackupPlace(plan, index) {
  const backups = plan.arrangements?.backup_arrangements
  const entry = backups?.[index]
  if (!entry) return
  entry.destination = null
  if (!entry.transport_id) backups.splice(index, 1)
}
