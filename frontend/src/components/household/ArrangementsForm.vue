<script setup>
import { computed } from 'vue'
import { newId } from '../../api/client'
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'

defineProps({ transports: { type: Array, required: true } })
const arrangements = defineModel({ required: true })

const TRANSPORT_LABELS = {
  car: 'Car / SUV',
  ute: 'Ute / Pickup',
  van: 'Van',
  motorbike: 'Motorbike',
  truck: 'Truck',
  other: 'Other',
}

function transportOptionLabel(transport) {
  const typeLabel = transport.transport_type === 'other' && transport.transport_type_other
    ? transport.transport_type_other
    : TRANSPORT_LABELS[transport.transport_type] || 'Other'
  return transport.display_name ? `${transport.display_name} — ${typeLabel}` : typeLabel
}

function newDestination() {
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

function destinationField(key, field) {
  return computed({
    get: () => arrangements.value[key]?.[field] ?? '',
    set: (value) => {
      arrangements.value[key] ??= newDestination()
      arrangements.value[key][field] = value
    },
  })
}

const primaryName = destinationField('primary_destination', 'display_name')
const primaryAddress = destinationField('primary_destination', 'address')

function addBackupArrangement() {
  arrangements.value.backup_arrangements ??= []
  arrangements.value.backup_arrangements.push({ transport_id: null, destination: null })
}

function setBackupDestinationField(backup, field, value) {
  backup.destination ??= newDestination()
  backup.destination[field] = value
}

function resetDestinationVerification(destination) {
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

function setDestinationAddress(destination, address) {
  if (destination.address !== address) resetDestinationVerification(destination)
  destination.address = address || null
}

function selectDestinationAddress(destination, suggestion) {
  setDestinationAddress(destination, suggestion.address)
  destination.selected_address = suggestion.address
}

function setPrimaryDestinationAddress(address) {
  arrangements.value.primary_destination ??= newDestination()
  setDestinationAddress(arrangements.value.primary_destination, address)
}

function selectPrimaryDestinationAddress(suggestion) {
  arrangements.value.primary_destination ??= newDestination()
  selectDestinationAddress(arrangements.value.primary_destination, suggestion)
}

function setBackupDestinationAddress(backup, address) {
  backup.destination ??= newDestination()
  setDestinationAddress(backup.destination, address)
}

function selectBackupDestinationAddress(backup, suggestion) {
  backup.destination ??= newDestination()
  selectDestinationAddress(backup.destination, suggestion)
}

function removeBackupArrangement(index) {
  arrangements.value.backup_arrangements.splice(index, 1)
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Primary & backup arrangements</h3>
      </div>
    </div>

    <p class="section-label">Primary</p>
    <div class="field-grid">
      <div class="field">
        <label>Primary transport</label>
        <select v-model="arrangements.primary_transport_id">
          <option :value="null">Not set</option>
          <option v-for="t in transports" :key="t.transport_id" :value="t.transport_id">
            {{ transportOptionLabel(t) }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Primary destination</label>
        <input v-model="primaryName" type="text" placeholder="e.g. Relative's house" />
      </div>
      <AddressAutocompleteInput :model-value="primaryAddress" label="Destination address (optional)" placeholder="Start typing a Victorian address" :helper-text="arrangements.primary_destination?.address ? (arrangements.primary_destination.verification_status === 'verified' ? 'Verified address' : 'Address saved but not verified') : ''" @update:model-value="setPrimaryDestinationAddress" @select="selectPrimaryDestinationAddress" />
    </div>

    <hr class="divider" />

    <div class="backup-heading">
      <div>
        <p class="section-label">Backup arrangements</p>
        <p class="hint">Optional now, but recommended — plan tests flag missing independent backups.</p>
      </div>
      <button class="btn btn-ghost btn-sm" type="button" @click="addBackupArrangement">
        Add backup arrangement
      </button>
    </div>
    <p v-if="!arrangements.backup_arrangements?.length" class="hint">
      No backup arrangements added yet.
    </p>
    <section v-for="(backup, index) in arrangements.backup_arrangements" :key="index" class="backup-option">
      <div class="backup-option-header">
        <p class="section-label">Backup {{ index + 1 }}</p>
        <button class="btn btn-ghost btn-sm" type="button" @click="removeBackupArrangement(index)">
          Remove
        </button>
      </div>
      <div class="field-grid">
        <div class="field">
          <label>Backup transport</label>
          <select v-model="backup.transport_id">
            <option :value="null">Not set</option>
            <option v-for="t in transports" :key="t.transport_id" :value="t.transport_id">
              {{ transportOptionLabel(t) }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Backup destination</label>
          <input :value="backup.destination?.display_name ?? ''" type="text" placeholder="e.g. Community centre" @input="setBackupDestinationField(backup, 'display_name', $event.target.value)" />
        </div>
        <AddressAutocompleteInput :model-value="backup.destination?.address ?? ''" label="Destination address (optional)" placeholder="Start typing a Victorian address" :helper-text="backup.destination?.address ? (backup.destination.verification_status === 'verified' ? 'Verified address' : 'Address saved but not verified') : ''" @update:model-value="setBackupDestinationAddress(backup, $event)" @select="selectBackupDestinationAddress(backup, $event)" />
      </div>
      <button v-if="backup.destination" class="btn btn-ghost btn-sm" type="button" @click="backup.destination = null">
        Clear backup destination
      </button>
    </section>

    <hr class="divider" />

    <div class="field">
      <label>Meeting point if separated (optional)</label>
      <input v-model="arrangements.meeting_point" type="text" placeholder="e.g. Front gate" />
    </div>
  </section>
</template>

<style scoped>
.section-label {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin-bottom: 0.75rem;
}

.backup-heading,
.backup-option-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.backup-option {
  border-top: 1px solid var(--color-border);
  margin-top: 1rem;
  padding-top: 1rem;
}

</style>
