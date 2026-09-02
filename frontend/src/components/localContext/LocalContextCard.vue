<script setup>
import { ref, watch } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'
import { formatAustralianDateTime } from '../../utils/dateTime'
const store = useLocalContextStore()
const draftAddress = ref(store.address)
const editing = ref(!store.submittedAddress)
watch(() => store.address, (value) => { draftAddress.value = value })
function selectSuggestion(suggestion) { store.submitAddress(suggestion.address, suggestion.address); editing.value = false }
async function submit() { if (!draftAddress.value.trim()) return; await store.submitAddress(draftAddress.value.trim()); if (store.saveStatus === 'success') editing.value = false }

function fireHistoryRows(summary) {
  if (!summary) return []
  const count = summary.match(/(\d+) historical bushfire records? (?:were|was) found within ([\d.]+) km/i)
  const noRecords = summary.match(/No historical bushfire records were found within ([\d.]+) km/i)
  const season = summary.match(/latest recorded burn season was (\d{4})/i)
  const dated = summary.match(/most recent dated record was (\d{4}-\d{2}-\d{2})/i)
  const rows = []
  if (count) rows.push({ label: `Records within ${count[2]} km`, value: count[1] })
  else if (noRecords) rows.push({ label: `Records within ${noRecords[1]} km`, value: '0' })
  if (season) rows.push({ label: 'Latest recorded fire season', value: season[1] })
  if (dated) {
    const [year, month, day] = dated[1].split('-').map(Number)
    rows.push({ label: 'Most recent dated fire record', value: new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, day))) })
  }
  return rows
}
</script>

<template>
  <section class="card address-card">
    <div class="card-header"><h2 class="card-title">Household address</h2><button v-if="store.location && !editing" class="btn btn-ghost btn-sm" type="button" @click="editing = true">Edit address</button></div>
    <template v-if="store.location && !editing">
      <p class="saved-address">{{ store.location.address }}</p>
      <p class="verification">{{ store.location.verification_status === 'verified' ? 'Verified address' : 'Address saved but not verified' }}</p>
    </template>
    <template v-else>
      <p v-if="!store.location" class="intro">Add your household address to view local bushfire and weather information for your area.</p>
      <form class="address-form" @submit.prevent="submit">
        <AddressAutocompleteInput v-model="draftAddress" class="field" label="Household address" placeholder="Start typing a Victorian street address" @select="selectSuggestion" />
        <button class="btn btn-accent" type="submit" :disabled="store.saveStatus === 'loading' || !draftAddress.trim()">{{ store.saveStatus === 'loading' ? 'Saving...' : 'Save address' }}</button>
      </form>
    </template>
    <ErrorState v-if="store.saveStatus === 'error'" :message="store.contextError || 'Could not save the household address.'" @retry="submit" />
  </section>

  <section class="card local-card">
    <h2 class="card-title">Local bushfire and weather information</h2>
    <p v-if="store.contextStatus === 'unverified'" class="state-message">Local information is unavailable until this address is verified.</p>
    <LoadingState v-else-if="store.contextStatus === 'loading'" message="Loading local information..." />
    <div v-else-if="store.contextUnavailable" class="state-message">Official local information is temporarily unavailable. Your household address is still saved.</div>
    <ErrorState v-else-if="store.contextStatus === 'error'" :message="store.contextError || 'Could not load local information.'" @retry="store.loadContext" />
    <div v-else-if="store.contextStatus === 'success' && store.context" class="context-grid">
      <div>
        <h3>Bushfire context</h3>
        <dl>
          <div><dt>Bushfire-prone area</dt><dd>{{ store.context.bushfire_context.is_bushfire_prone_area ? 'Yes' : 'No' }}</dd></div>
          <div><dt>CFA Fire District</dt><dd>{{ store.context.bushfire_context.fire_district }}</dd></div>
        </dl>
        <p class="hint">Used to match official fire danger information for your area.</p>
        <div v-if="store.context.environmental_context.fire_history_summary" class="history">
          <strong>Historical fire activity</strong>
          <dl v-if="fireHistoryRows(store.context.environmental_context.fire_history_summary).length">
            <div v-for="row in fireHistoryRows(store.context.environmental_context.fire_history_summary)" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
          <p v-else>{{ store.context.environmental_context.fire_history_summary }}</p>
        </div>
      </div>
      <div>
        <h3>Current conditions</h3>
        <dl>
          <div><dt>Temperature</dt><dd>{{ store.context.weather.temperature_c }}°C</dd></div>
          <div><dt>Humidity</dt><dd>{{ store.context.weather.relative_humidity }}%</dd></div>
          <div><dt>Wind</dt><dd>{{ store.context.weather.wind_speed_kmh }} km/h {{ store.context.weather.wind_direction }}</dd></div>
          <div><dt>Fire Danger Rating</dt><dd>{{ store.context.fire_danger.availability === 'available' ? store.context.fire_danger.today : 'Currently unavailable' }}</dd></div>
        </dl>
        <p class="hint">Bureau of Meteorology</p>
        <p class="hint">Last updated: {{ formatAustralianDateTime(store.context.weather.observed_at) }}</p>
      </div>
    </div>
    <p v-else class="state-message">Add and verify your household address to view local information.</p>
  </section>
</template>

<style scoped>
.intro, .verification, .hint, .state-message { color: var(--color-text-muted); }
.saved-address { font-weight: 600; }
.verification { font-size: 0.9rem; margin-top: 0.25rem; }
.address-form { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 0.75rem; margin-top: 1rem; }
.field { min-width: 0; position: relative; }
.local-card { margin-top: 1.25rem; }
.local-card > .card-title { margin-bottom: 1rem; }
.context-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2rem; }
h3 { font-size: 1.05rem; margin-bottom: 0.75rem; }
dl { margin: 0; }
dl div { display: flex; justify-content: space-between; gap: 1rem; padding: 0.55rem 0; border-bottom: 1px solid var(--color-border); }
dt { color: var(--color-text-muted); } dd { margin: 0; font-weight: 600; text-align: right; }
.hint { font-size: 0.875rem; margin-top: 0.65rem; }
.history { margin-top: 1.25rem; }.history p { margin-top: 0.35rem; }
@media (max-width: 700px) { .context-grid, .address-form { grid-template-columns: 1fr; } .address-form .btn { width: 100%; } }
</style>
