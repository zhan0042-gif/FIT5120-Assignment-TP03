<script setup lang="ts">
import { computed } from 'vue'
import type { Arrangements, Transport } from '../../types/household'
import { newId } from '../../api/client'

defineProps<{ transports: Transport[] }>()
const arrangements = defineModel<Arrangements>({ required: true })

function destinationField(key: 'primary_destination' | 'backup_destination', field: 'display_name' | 'address') {
  return computed({
    get: () => arrangements.value[key]?.[field] ?? '',
    set: (value: string) => {
      if (!arrangements.value[key]) {
        arrangements.value[key] = { destination_id: newId('d'), display_name: '', address: null }
      }
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      arrangements.value[key]![field] = value
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
            {{ t.display_name || t.transport_type }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Primary destination</label>
        <input v-model="primaryName" type="text" placeholder="e.g. Relative's house" />
      </div>
      <div class="field">
        <label>Destination address (optional)</label>
        <input v-model="primaryAddress" type="text" />
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
            {{ t.display_name || t.transport_type }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>Backup destination</label>
        <input v-model="backupName" type="text" placeholder="e.g. Community centre" />
      </div>
      <div class="field">
        <label>Destination address (optional)</label>
        <input v-model="backupAddress" type="text" />
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
  font-size: 0.8rem;
  color: var(--color-text-muted);
  margin-bottom: 0.75rem;
}
</style>
