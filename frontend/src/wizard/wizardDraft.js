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
