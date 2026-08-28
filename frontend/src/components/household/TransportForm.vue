<script setup lang="ts">
import type { HouseholdMember, Transport } from '../../types/household'
import { newId } from '../../api/client'
import EmptyState from '../common/EmptyState.vue'

const props = defineProps<{ members: HouseholdMember[] }>()
const transports = defineModel<Transport[]>({ required: true })

function addTransport() {
  transports.value.push({
    transport_id: newId('t'),
    transport_type: 'car',
    display_name: '',
    driver_member_ids: [],
  })
}

function addNoTransport() {
  transports.value.push({
    transport_id: newId('t'),
    transport_type: 'none',
    display_name: 'No private transport available',
    driver_member_ids: [],
  })
}

function removeTransport(id: string) {
  transports.value = transports.value.filter((t) => t.transport_id !== id)
}

function toggleDriver(transport: Transport, memberId: string) {
  const idx = transport.driver_member_ids.indexOf(memberId)
  if (idx === -1) transport.driver_member_ids.push(memberId)
  else transport.driver_member_ids.splice(idx, 1)
}

function memberName(id: string) {
  return props.members.find((m) => m.member_id === id)?.display_name || 'Unnamed member'
}
</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Transport & driver availability</h3>
      </div>
      <span class="badge" :class="transports.length ? 'badge-success' : 'badge-neutral'">
        {{ transports.length }} recorded
      </span>
    </div>

    <EmptyState v-if="transports.length === 0" title="No transport recorded yet">
      <div class="empty-actions">
        <button class="btn btn-primary btn-sm" type="button" @click="addTransport">Add transport</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="addNoTransport">We have no private transport</button>
      </div>
    </EmptyState>

    <template v-else>
      <div v-for="transport in transports" :key="transport.transport_id" class="transport-row">
        <div class="field-grid">
          <div class="field">
            <label>Type</label>
            <select v-model="transport.transport_type">
              <option value="car">Car</option>
              <option value="other">Other</option>
              <option value="none">None available</option>
            </select>
          </div>
          <div class="field">
            <label>Name (optional)</label>
            <input v-model="transport.display_name" type="text" placeholder="e.g. Family Car" />
          </div>
        </div>

        <div v-if="transport.transport_type !== 'none'" class="drivers">
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
      <button class="btn btn-ghost btn-sm" type="button" @click="addTransport">+ Add another transport option</button>
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

.drivers {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.hint {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.empty-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
