<script setup>
import { newId } from '../../api/client'
import EmptyState from '../common/EmptyState.vue'

const props = defineProps({ members: { type: Array, required: true } })
const transports = defineModel('transports', { required: true })
const hasPrivateTransport = defineModel('hasPrivateTransport', { required: true })

function addPrivateTransport() {
  hasPrivateTransport.value = true
  transports.value.push({
    transport_id: newId('t'),
    transport_type: 'car',
    display_name: '',
    driver_member_ids: [],
  })
}

function addOtherArrangement() {
  transports.value.push({
    transport_id: newId('t'),
    transport_type: 'other',
    display_name: '',
    driver_member_ids: [],
  })
}

function recordNoPrivateTransport() {
  hasPrivateTransport.value = false
}

function markPrivateTransport(transport) {
  if (transport.transport_type !== 'other') hasPrivateTransport.value = true
}

function removeTransport(id) {
  transports.value = transports.value.filter((t) => t.transport_id !== id)
}

function toggleDriver(transport, memberId) {
  const idx = transport.driver_member_ids.indexOf(memberId)
  if (idx === -1) transport.driver_member_ids.push(memberId)
  else transport.driver_member_ids.splice(idx, 1)
}

function memberName(id) {
  return props.members.find((m) => m.member_id === id)?.display_name || 'Unnamed member'
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Transport & driver availability</h3>
      </div>
      <span class="badge" :class="hasPrivateTransport !== null || transports.length ? 'badge-success' : 'badge-neutral'">
        {{ hasPrivateTransport === false ? 'No private transport recorded' : `${transports.length} recorded` }}
      </span>
    </div>

    <EmptyState
      v-if="transports.length === 0"
      :title="hasPrivateTransport === false ? 'No private transport recorded' : 'No transport recorded yet'"
    >
      <div class="empty-actions">
        <button class="btn btn-primary btn-sm" type="button" @click="addPrivateTransport">Add private transport</button>
        <button v-if="hasPrivateTransport !== false" class="btn btn-ghost btn-sm" type="button" @click="recordNoPrivateTransport">We have no private transport</button>
        <button v-else class="btn btn-ghost btn-sm" type="button" @click="addOtherArrangement">Add another transport arrangement</button>
      </div>
    </EmptyState>

    <template v-else>
      <div v-for="transport in transports" :key="transport.transport_id" class="transport-row">
        <div class="field-grid">
          <div class="field">
            <label>Type</label>
            <select v-model="transport.transport_type" @change="markPrivateTransport(transport)">
              <option value="car">Car</option>
              <option value="motorbike">Motorbike</option>
              <option value="van">Van</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div class="field">
            <label>Name (optional)</label>
            <input v-model="transport.display_name" type="text" placeholder="e.g. Family Car" />
          </div>
        </div>

        <div class="drivers">
          <p class="eyebrow">Who can drive it</p>
          <div v-if="members.length === 0" class="hint">Add household members first to assign drivers.</div>
          <label v-for="member in members" :key="member.member_id" class="checkbox-row">
            <input
              type="checkbox"
              :checked="transport.driver_member_ids.includes(member.member_id)"
              @change="toggleDriver(transport, member.member_id)"
            />
            {{ memberName(member.member_id) }}
          </label>
        </div>

        <button class="btn btn-danger btn-sm" type="button" @click="removeTransport(transport.transport_id)">Remove</button>
      </div>
      <button class="btn btn-ghost btn-sm" type="button" @click="hasPrivateTransport === false ? addOtherArrangement() : addPrivateTransport()">
        + Add another transport option
      </button>
    </template>
  </section>
</template>

<style scoped>
.transport-row {
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.transport-row > .btn-danger {
  align-self: flex-end;
}

.drivers {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.empty-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
