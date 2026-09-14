<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import { useHouseholdStore } from '../stores/household'

const householdStore = useHouseholdStore()
const exportStatus = ref('idle')
const exportError = ref(null)
const householdAddress = ref('')

const RELATIONSHIP_LABELS = {
  self: 'Self',
  partner: 'Partner / spouse',
  child: 'Child',
  parent: 'Parent',
  grandparent: 'Grandparent',
  sibling: 'Sibling',
  other_relative: 'Other relative',
  friend_or_housemate: 'Friend / housemate',
  carer: 'Carer',
  other: 'Other',
}
const LOCATION_LABELS = { home: 'Home', work: 'Work', school: 'School', other: 'Other' }

onMounted(async () => {
  // Always refresh here: the printable summary represents saved backend state,
  // never a draft that may still be open on the plan page.
  await householdStore.loadPlan()
  if (!householdStore.householdId || householdStore.planStatus !== 'success') return
  try {
    const location = await api.getLocation(householdStore.householdId)
    householdAddress.value = (location.canonical_address || location.address || '').trim()
  } catch {
    householdAddress.value = ''
  }
})

const plan = computed(() => householdStore.plan)
const noSavedPlan = computed(
  () => householdStore.planStatus === 'success' && householdStore.completion === null,
)
const membersById = computed(() =>
  Object.fromEntries((plan.value?.members ?? []).map((member) => [member.member_id, member])),
)
const transportsById = computed(() =>
  Object.fromEntries((plan.value?.transports ?? []).map((transport) => [transport.transport_id, transport])),
)

function recorded(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : 'Not recorded'
}

function memberName(memberId) {
  return recorded(membersById.value[memberId]?.display_name)
}

function relationship(member) {
  if (member.relationship === 'other' && member.relationship_other?.trim()) {
    return member.relationship_other.trim()
  }
  return RELATIONSHIP_LABELS[member.relationship] ?? 'Not recorded'
}

function supportNeeds(member) {
  const needs = []
  if (member.is_dependant) needs.push('Needs help from another household member')
  if (member.mobility_support_required) needs.push('Mobility support required')
  if (member.support_notes?.trim()) needs.push(member.support_notes.trim())
  return needs.length ? needs.join('; ') : 'Not recorded'
}

function daytimeLocation(member) {
  return LOCATION_LABELS[member.usual_location?.kind] ?? 'Not recorded'
}

function daytimeAddress(member) {
  if (!member.usual_location) return 'Not recorded'
  if (member.usual_location.kind === 'home') return recorded(householdAddress.value)
  return recorded(member.usual_location.address)
}

function animalType(animal) {
  const value = animal.animal_type === 'other'
    ? animal.animal_type_other
    : animal.animal_type?.replaceAll('_', ' ')
  const text = recorded(value)
  return text === 'Not recorded' ? text : text.charAt(0).toUpperCase() + text.slice(1)
}

function transportType(transport) {
  if (!transport) return 'Not recorded'
  const value = transport.transport_type === 'other'
    ? transport.transport_type_other
    : transport.transport_type?.replaceAll('_', ' ')
  const text = recorded(value)
  return text === 'Not recorded' ? text : text.charAt(0).toUpperCase() + text.slice(1)
}

function driverNames(transport) {
  if (!transport?.driver_member_ids?.length) return 'Not recorded'
  return transport.driver_member_ids.map(memberName).join(', ')
}

function destinationParts(destination) {
  if (!destination) return ['Not recorded']
  const values = [destination.display_name, destination.canonical_address || destination.address]
    .filter((value) => value?.trim())
    .map((value) => value.trim())
  return values.length ? values : ['Not recorded']
}

const transportRows = computed(() => {
  const primary = transportsById.value[plan.value?.arrangements?.primary_transport_id] ?? null
  const rows = [{ arrangement: 'Primary', transport: primary }]
  const backups = plan.value?.arrangements?.backup_arrangements ?? []
  if (!backups.length) return [...rows, { arrangement: 'Backup', transport: null }]
  return rows.concat(backups.map((backup, index) => ({
    arrangement: backups.length === 1 ? 'Backup' : `Backup ${index + 1}`,
    transport: transportsById.value[backup.transport_id] ?? null,
  })))
})

const evacuationRows = computed(() => {
  const arrangements = plan.value?.arrangements
  const rows = [
    { arrangement: 'Meeting point', values: [recorded(arrangements?.meeting_point)] },
    { arrangement: 'Primary destination', values: destinationParts(arrangements?.primary_destination) },
  ]
  const backups = arrangements?.backup_arrangements ?? []
  if (!backups.length) {
    return [...rows, { arrangement: 'Backup destination', values: ['Not recorded'] }]
  }
  return rows.concat(backups.map((backup, index) => ({
    arrangement: backups.length === 1 ? 'Backup destination' : `Backup destination ${index + 1}`,
    values: destinationParts(backup.destination),
  })))
})

async function exportPdf() {
  exportStatus.value = 'loading'
  exportError.value = null
  try {
    const householdId = await householdStore.ensureHousehold()
    const { blob, filename } = await api.getPreparednessPlanPdf(householdId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    exportStatus.value = 'success'
  } catch (error) {
    exportStatus.value = 'error'
    exportError.value = error instanceof Error ? error.message : 'Could not export the PDF.'
  }
}
</script>

<template>
  <div class="summary-view">
    <header class="page-header">
      <div>
        <h1>Preparedness Summary</h1>
        <p>Check your saved plan before exporting or printing it.</p>
      </div>
      <div class="page-actions">
        <router-link class="btn btn-ghost" to="/plan">Edit Plan</router-link>
        <button class="btn btn-accent" type="button" :disabled="noSavedPlan || exportStatus === 'loading'" @click="exportPdf">
          {{ exportStatus === 'loading' ? 'Generating PDF...' : 'Export PDF' }}
        </button>
      </div>
    </header>

    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your saved plan..." />
    <ErrorState v-else-if="householdStore.planStatus === 'error'" :message="householdStore.planError || 'Could not load your saved plan.'" @retry="householdStore.loadPlan" />
    <section v-else-if="noSavedPlan" class="card empty-summary">
      <h2>No saved plan found</h2>
      <p>Create and save a household plan before exporting it.</p>
      <router-link class="btn btn-accent" to="/plan">Create Plan</router-link>
    </section>

    <template v-else-if="plan">
      <p v-if="exportError" class="field-error export-error">{{ exportError }}</p>

      <section class="card summary-section">
        <h2>Household</h2>
        <h3>Household members</h3>
        <div class="table-wrap">
          <table class="summary-table">
            <colgroup><col class="member-name"><col class="member-relationship"><col class="member-support"><col class="member-location"><col class="member-address"></colgroup>
            <thead><tr><th>Name</th><th>Relationship</th><th>Support needs</th><th>Daytime location</th><th>Daytime address</th></tr></thead>
            <tbody>
              <tr v-if="!plan.members.length"><td colspan="5">No household members recorded</td></tr>
              <template v-else>
                <tr v-for="member in plan.members" :key="member.member_id"><td>{{ recorded(member.display_name) }}</td><td>{{ relationship(member) }}</td><td>{{ supportNeeds(member) }}</td><td>{{ daytimeLocation(member) }}</td><td>{{ daytimeAddress(member) }}</td></tr>
              </template>
            </tbody>
          </table>
        </div>

        <h3 class="subsection-heading">Animals / pets</h3>
        <div class="table-wrap">
          <table class="summary-table">
            <thead><tr><th>Pet type</th><th>Name</th><th>Quantity</th></tr></thead>
            <tbody>
              <tr v-if="!plan.animals.length"><td colspan="3">No animals or pets recorded</td></tr>
              <template v-else>
                <tr v-for="animal in plan.animals" :key="animal.animal_id"><td>{{ animalType(animal) }}</td><td>{{ recorded(animal.display_name) }}</td><td>{{ animal.quantity }}</td></tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card summary-section">
        <h2>Transport</h2>
        <div class="table-wrap">
          <table class="summary-table">
            <thead><tr><th>Arrangement</th><th>Vehicle</th><th>Type</th><th>Driver</th></tr></thead>
            <tbody><tr v-for="row in transportRows" :key="row.arrangement"><td>{{ row.arrangement }}</td><td>{{ recorded(row.transport?.display_name) }}</td><td>{{ transportType(row.transport) }}</td><td>{{ driverNames(row.transport) }}</td></tr></tbody>
          </table>
        </div>
      </section>

      <section class="card summary-section">
        <h2>Evacuation Arrangements</h2>
        <div class="table-wrap">
          <table class="summary-table">
            <thead><tr><th>Arrangement</th><th>Destination / Address</th></tr></thead>
            <tbody><tr v-for="row in evacuationRows" :key="row.arrangement"><td>{{ row.arrangement }}</td><td><span v-for="value in row.values" :key="value" class="cell-line">{{ value }}</span></td></tr></tbody>
          </table>
        </div>
      </section>

      <section class="card summary-section">
        <h2>Responsibilities</h2>
        <div class="table-wrap">
          <table class="summary-table">
            <thead><tr><th>Responsibility</th><th>Primary person</th><th>Backup person</th></tr></thead>
            <tbody>
              <tr v-if="!plan.responsibilities.length"><td colspan="3">No responsibilities recorded</td></tr>
              <template v-else>
                <tr v-for="responsibility in plan.responsibilities" :key="responsibility.responsibility_id"><td>{{ recorded(responsibility.task_name) }}</td><td>{{ memberName(responsibility.primary_member_id) }}</td><td>{{ memberName(responsibility.backup_member_id) }}</td></tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.summary-view { width: 100%; min-width: 0; }
.page-header { align-items: flex-start; display: flex; gap: 1.5rem; justify-content: space-between; margin-bottom: 1.5rem; }
.page-header h1 { font-size: clamp(2rem, 4vw, 2.25rem); line-height: 1.2; }
.page-header p, .empty-summary p { color: var(--color-text-muted); margin-top: 0.5rem; }
.page-actions { display: flex; flex: 0 0 auto; gap: 0.75rem; }
.page-actions .btn { align-items: center; display: inline-flex; text-decoration: none; }
.summary-section + .summary-section { margin-top: 1.25rem; }
.summary-section h2 { font-size: 1.35rem; margin-bottom: 1rem; }
.summary-section h3 { font-size: 1rem; margin-bottom: 0.65rem; }
.subsection-heading { margin-top: 1.5rem; }
.table-wrap { max-width: 100%; overflow-x: auto; }
.summary-table { border-collapse: collapse; font-size: 0.9rem; min-width: 100%; width: 100%; }
.summary-table th, .summary-table td { border: 1px solid var(--color-border); padding: 0.7rem 0.75rem; text-align: left; vertical-align: top; }
.summary-table th { background: var(--color-bg-card-muted); color: var(--color-text); font-size: 0.8rem; font-weight: 700; letter-spacing: 0.02em; }
.summary-table td { background: var(--color-bg-card); color: var(--color-text); font-weight: 500; }
.member-name, .member-relationship { width: 14%; }
.member-support { width: 20%; }
.member-location { width: 16%; }
.member-address { width: 36%; }
.cell-line { display: block; }
.cell-line + .cell-line { color: var(--color-text-muted); margin-top: 0.2rem; }
.export-error { margin-bottom: 1rem; }
.empty-summary { text-align: center; }
.empty-summary .btn { display: inline-flex; margin-top: 1rem; text-decoration: none; }
@media (max-width: 700px) {
  .page-header { align-items: stretch; flex-direction: column; }
  .page-actions { flex-wrap: wrap; }
  .page-actions .btn { flex: 1; justify-content: center; }
  .summary-table { min-width: 42rem; }
}
</style>
