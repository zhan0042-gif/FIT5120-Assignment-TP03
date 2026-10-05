<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import CompletionOverview from '../components/completion/CompletionOverview.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import PreparationSupportBanner from '../components/localContext/PreparationSupportBanner.vue'
import SafetyChatPanel from '../components/overview/SafetyChatPanel.vue'
import { useHouseholdStore } from '../stores/household'
import { useLocalContextStore } from '../stores/localContext'
import { useRendezvousStore } from '../stores/rendezvous'

const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()
const rendezvousStore = useRendezvousStore()
const exportStatus = ref('idle')
const exportError = ref(null)

const LOCATION_LABELS = { home: 'Home', work: 'Work', school: 'School', other: 'Other' }
const plan = computed(() => householdStore.plan)
const noSavedPlan = computed(
  () => householdStore.planStatus === 'success' && householdStore.completion === null,
)
const householdAddress = computed(() => {
  const location = localContextStore.location
  return (location?.canonical_address || location?.address || '').trim() || 'Not recorded'
})
const membersById = computed(() =>
  Object.fromEntries((plan.value?.members ?? []).map((member) => [member.member_id, member])),
)

function recorded(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : 'Not recorded'
}

function memberName(memberId) {
  return recorded(membersById.value[memberId]?.display_name)
}

function daytimeLocation(member) {
  return LOCATION_LABELS[member.usual_location?.kind] ?? 'Not recorded'
}

function daytimeAddress(member) {
  if (!member.usual_location) return 'Not recorded'
  if (member.usual_location.kind === 'home') return householdAddress.value
  return recorded(member.usual_location.address)
}

function destinationText(destination) {
  if (!destination) return 'Not recorded'
  return [destination.display_name, destination.canonical_address || destination.address]
    .filter((value) => value?.trim())
    .map((value) => value.trim())
    .join(' - ') || 'Not recorded'
}

const keyLocations = computed(() => {
  const arrangements = plan.value?.arrangements
  const rows = [
    { label: 'Primary destination', value: destinationText(arrangements?.primary_destination) },
  ]
  const backups = arrangements?.backup_arrangements ?? []
  if (!backups.length) {
    rows.push({ label: 'Backup destination', value: 'Not recorded' })
  } else {
    backups.forEach((backup, index) => rows.push({
      label: backups.length === 1 ? 'Backup destination' : `Backup destination ${index + 1}`,
      value: destinationText(backup.destination),
    }))
  }
  rows.push({ label: 'Meeting point', value: recorded(arrangements?.meeting_point) })
  return rows
})

const acceptedAdvice = computed(() =>
  rendezvousStore.explanationStatus === 'success' ? rendezvousStore.explanation : null,
)

async function exportPdf() {
  exportStatus.value = 'loading'
  exportError.value = null
  try {
    const householdId = await householdStore.ensureHousehold()
    const { blob, filename } = await api.getPreparednessPlanPdf(householdId, acceptedAdvice.value)
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

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  await localContextStore.init()
})
</script>

<template>
  <div class="overview">
    <header class="page-header">
      <div>
        <h1>Overview</h1>
        <p>Review your household's preparedness and saved plan.</p>
      </div>
    </header>

    <div class="top-grid">
      <CompletionOverview :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
      <div class="right-stack">
        <PreparationSupportBanner />
      </div>
    </div>

    <SafetyChatPanel />

    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your saved plan..." />
    <ErrorState v-else-if="householdStore.planStatus === 'error'" :message="householdStore.planError || 'Could not load your saved plan.'" @retry="householdStore.loadPlan" />
    <section v-else-if="noSavedPlan" class="card empty-summary">
      <h2>Household Plan Summary</h2>
      <p>Create and save a household plan to see its key details here.</p>
      <router-link class="btn btn-accent" to="/plan">Create my plan</router-link>
    </section>

    <section v-else-if="plan" class="card plan-summary">
      <h2>Household Plan Summary</h2>

      <h3>Household Members</h3>
      <div class="table-wrap">
        <table class="summary-table member-table">
          <thead><tr><th>Name</th><th>Daytime location</th><th>Daytime address</th></tr></thead>
          <tbody>
            <tr v-if="!plan.members.length"><td colspan="3">No household members recorded</td></tr>
            <template v-else>
              <tr v-for="member in plan.members" :key="member.member_id">
                <td>{{ recorded(member.display_name) }}</td>
                <td>{{ daytimeLocation(member) }}</td>
                <td>{{ daytimeAddress(member) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <h3>Key Locations</h3>
      <dl class="summary-list">
        <div v-for="location in keyLocations" :key="location.label">
          <dt>{{ location.label }}</dt><dd>{{ location.value }}</dd>
        </div>
      </dl>

      <h3>Responsibilities</h3>
      <div class="table-wrap">
        <table class="summary-table responsibility-table">
          <thead><tr><th>Responsibility</th><th>Primary person</th><th>Backup person</th></tr></thead>
          <tbody>
            <tr v-if="!plan.responsibilities.length"><td colspan="3">No responsibilities recorded</td></tr>
            <template v-else>
              <tr v-for="responsibility in plan.responsibilities" :key="responsibility.responsibility_id">
                <td>{{ recorded(responsibility.task_name) }}</td>
                <td>{{ memberName(responsibility.primary_member_id) }}</td>
                <td>{{ memberName(responsibility.backup_member_id) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <div class="page-actions">
      <button class="btn btn-accent" type="button" :disabled="noSavedPlan || exportStatus === 'loading'" @click="exportPdf">
        {{ exportStatus === 'loading' ? 'Generating PDF...' : 'Export preparedness plan' }}
      </button>
    </div>
    <p v-if="exportError" class="field-error export-error">{{ exportError }}</p>
  </div>
</template>

<style scoped>
.overview { width: 100%; min-width: 0; }
.page-header { align-items: flex-start; display: flex; gap: 1.5rem; justify-content: space-between; margin-bottom: 1.75rem; }
.page-header h1 { font-size: clamp(2rem, 4vw, 2.25rem); line-height: 1.2; }
.page-header p, .empty-summary p { color: var(--color-text-muted); margin-top: 0.5rem; }
.page-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem; }
.page-actions .btn, .empty-summary .btn { align-items: center; display: inline-flex; justify-content: center; text-decoration: none; }
.top-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.25rem; align-items: start; }
.right-stack { display: grid; gap: 1.25rem; }
.right-stack :deep(.card) { margin-top: 0; }
.plan-summary, .empty-summary { margin-top: 1.25rem; }
.plan-summary > h2 { font-size: 1.35rem; margin-bottom: 1.25rem; }
.plan-summary h3 { font-size: 1rem; margin: 1.35rem 0 0.65rem; }
.table-wrap { max-width: 100%; overflow-x: auto; }
.summary-table { border-collapse: collapse; font-size: 0.9rem; table-layout: fixed; width: 100%; }
.summary-table th, .summary-table td { border: 1px solid var(--color-summary-border); color: var(--color-summary-text); overflow-wrap: anywhere; padding: 0.7rem 0.75rem; text-align: left; vertical-align: top; }
.summary-table th { background: var(--color-summary-heading); font-size: 0.8rem; letter-spacing: 0.02em; }
.summary-table td { background: var(--color-summary-row); }
.member-table th:nth-child(1) { width: 22%; }
.member-table th:nth-child(2) { width: 25%; }
.member-table th:nth-child(3) { width: 53%; }
.responsibility-table th:nth-child(1) { width: 50%; }
.responsibility-table th:nth-child(2), .responsibility-table th:nth-child(3) { width: 25%; }
.summary-list { background: var(--color-summary-row); border: 1px solid var(--color-summary-border); margin: 0; }
.summary-list div { display: grid; grid-template-columns: minmax(8rem, 0.35fr) minmax(0, 1fr); gap: 1rem; padding: 0.65rem 0.75rem; }
.summary-list div + div { border-top: 1px solid var(--color-summary-border); }
.summary-list dt { color: var(--color-summary-muted); }
.summary-list dd { color: var(--color-summary-text); margin: 0; overflow-wrap: anywhere; }
.export-error { margin: 1rem 0; }
.empty-summary { text-align: center; }
.empty-summary .btn { margin-top: 1rem; }
@media (max-width: 800px) {
  .page-header { align-items: stretch; flex-direction: column; }
  .page-actions { flex-wrap: wrap; }
  .page-actions .btn { flex: 1 1 12rem; }
  .top-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .summary-table { font-size: 0.8rem; }
  .summary-table th, .summary-table td { padding: 0.55rem 0.45rem; }
  .summary-list div { grid-template-columns: 1fr; gap: 0.2rem; }
}
</style>
