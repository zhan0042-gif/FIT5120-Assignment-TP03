<script setup>
import { computed } from 'vue'
import { newId } from '../../api/client'

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

function destinationField(key, field) {
  return computed({
    get: () => arrangements.value[key]?.[field] ?? '',
    set: (value) => {
      if (!arrangements.value[key]) {
        arrangements.value[key] = {
          destination_id: newId('d'),
          display_name: '',
          address: null,
          unit_number: null,
          street_number: null,
          street_name: null,
          suburb_or_locality: null,
          state: 'VIC',
          postcode: null,
          country: 'Australia',
          latitude: null,
          longitude: null,
        }
      }
      arrangements.value[key][field] = value
    },
  })
}

const primaryName = destinationField('primary_destination', 'display_name')
const primaryAddress = destinationField('primary_destination', 'address')
const backupName = destinationField('backup_destination', 'display_name')
const backupAddress = destinationField('backup_destination', 'address')

function clearBackupDestination() {
  arrangements.value.backup_destination = null
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
      <div class="field">
        <label>Destination address (optional)</label>
        <input v-model="primaryAddress" type="text" placeholder="e.g. 1 Main Street, Bendigo VIC 3550" autocomplete="street-address" />
      </div>
    </div>

    <hr class="divider" />

    <p class="section-label">Backup</p>
    <p class="hint">Optional now, but recommended — a plan test will flag missing backups.</p>
    <div class="field-grid">
      <div class="field">
        <label>Backup transport</label>
        <select v-model="arrangements.backup_transport_id">
          <option :value="null">Not set</option>
          <option v-for="t in transports" :key="t.transport_id" :value="t.transport_id">
            {{ transportOptionLabel(t) }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Backup destination</label>
        <input v-model="backupName" type="text" placeholder="e.g. Community centre" />
      </div>
      <div class="field">
        <label>Destination address (optional)</label>
        <input v-model="backupAddress" type="text" placeholder="e.g. 10 High Street, Ballarat VIC 3350" autocomplete="street-address" />
      </div>
    </div>
    <button v-if="arrangements.backup_destination" class="btn btn-ghost btn-sm" type="button" @click="clearBackupDestination">
      Clear backup destination
    </button>

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
</style>
