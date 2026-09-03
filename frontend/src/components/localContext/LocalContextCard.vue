<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'
import { formatAustralianDateTime } from '../../utils/dateTime'
const store = useLocalContextStore()
const draftAddress = ref(store.address)
const editing = ref(!store.submittedAddress)
const geolocationStatus = ref('idle')
const geolocationMessage = ref('')
let mounted = true
watch(() => store.address, (value) => { draftAddress.value = value })
function selectSuggestion(suggestion) { store.submitAddress(suggestion.address, suggestion.address); editing.value = false }
async function submit() { if (!draftAddress.value.trim()) return; await store.submitAddress(draftAddress.value.trim()); if (store.saveStatus === 'success') editing.value = false }
function hasMissingForecastPeriods(fireDanger) {
  return ['today', 'tomorrow', 'day_3', 'day_4'].some((period) => fireDanger?.[period] == null)
}
async function confirmNearbyAddress(suggestion) {
  await store.submitAddress(suggestion.address, suggestion.address)
  if (store.saveStatus === 'success') editing.value = false
}

function useCurrentLocation() {
  geolocationMessage.value = ''
  if (!navigator.geolocation) {
    geolocationStatus.value = 'error'
    geolocationMessage.value = 'Current location is unavailable in this browser.'
    return
  }
  geolocationStatus.value = 'loading'
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      if (!mounted) return
      await store.submitDeviceLocation(position.coords.latitude, position.coords.longitude)
      if (!mounted) return
      if (store.saveStatus === 'success') {
        geolocationStatus.value = 'success'
        geolocationMessage.value = 'Current location detected.'
        editing.value = false
      } else {
        geolocationStatus.value = 'error'
        geolocationMessage.value = 'Your location was detected but could not be saved.'
      }
    },
    (error) => {
      if (!mounted) return
      geolocationStatus.value = 'error'
      if (error.code === error.PERMISSION_DENIED) {
        geolocationMessage.value = 'Location permission was denied. You can enter an address instead.'
      } else if (error.code === error.TIMEOUT) {
        geolocationMessage.value = 'Finding your current location timed out. Please try again or enter an address.'
      } else {
        geolocationMessage.value = 'Your current location is unavailable. You can enter an address instead.'
      }
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
  )
}

onBeforeUnmount(() => {
  mounted = false
  geolocationStatus.value = 'idle'
})

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
      <p class="saved-address">{{ store.location.location_source === 'device_location' ? 'Current location detected' : store.location.canonical_address || store.location.address }}</p>
      <p v-if="store.location.location_source === 'device_location'" class="verification status-text status-neutral">
        Device coordinates shared for local information. No postal address was verified.
      </p>
      <div v-if="store.location.location_source === 'device_location'" class="nearby-addresses">
        <p v-if="store.reverseStatus === 'loading'" class="hint">Looking for nearby official addresses...</p>
        <template v-else-if="store.nearbyAddresses.length">
          <strong>Detected nearby {{ store.nearbyAddresses.length === 1 ? 'address' : 'addresses' }}</strong>
          <p class="hint">Confirm only if this is your household address.</p>
          <div v-for="suggestion in store.nearbyAddresses" :key="suggestion.address" class="nearby-candidate">
            <span>{{ suggestion.address }}</span>
            <button class="btn btn-ghost btn-sm" type="button" @click="confirmNearbyAddress(suggestion)">Use this address</button>
          </div>
        </template>
        <p v-else-if="store.reverseStatus === 'empty'" class="hint">No nearby official address was found. Your coordinates can still be used for local information.</p>
        <p v-else-if="store.reverseStatus === 'unavailable'" class="hint">Nearby address lookup is temporarily unavailable. Your coordinates can still be used for local information.</p>
      </div>
      <p v-else class="verification status-text" :class="store.location.verification_status === 'verified' ? 'status-success' : 'status-neutral'">
        <span aria-hidden="true">{{ store.location.verification_status === 'verified' ? '✓' : '–' }}</span>
        {{ store.location.verification_status === 'verified' ? 'Verified address' : 'Address saved but not verified' }}
      </p>
      <p v-if="store.location.location_source !== 'device_location' && store.location.verification_status !== 'verified' && store.location.verification_message" class="hint">{{ store.location.verification_message }}</p>
    </template>
    <template v-else>
      <p v-if="!store.location" class="intro">Add your household address to view local bushfire and weather information for your area.</p>
      <form class="address-form" @submit.prevent="submit">
        <AddressAutocompleteInput v-model="draftAddress" class="field" label="Household address" placeholder="Start typing a Victorian street address" @select="selectSuggestion" />
        <button class="btn btn-accent" type="submit" :disabled="store.saveStatus === 'loading' || !draftAddress.trim()">{{ store.saveStatus === 'loading' ? 'Saving...' : 'Save address' }}</button>
      </form>
      <div class="location-option">
        <span>or</span>
        <button class="btn btn-ghost" type="button" :disabled="geolocationStatus === 'loading' || store.saveStatus === 'loading'" @click="useCurrentLocation">
          {{ geolocationStatus === 'loading' ? 'Finding current location...' : 'Use my current location' }}
        </button>
      </div>
      <p v-if="geolocationMessage" class="field-help" :class="geolocationStatus === 'success' ? 'status-success' : ''">{{ geolocationMessage }}</p>
    </template>
    <ErrorState v-if="store.saveStatus === 'error'" :message="store.contextError || 'Could not save the household location.'" @retry="geolocationStatus === 'error' ? useCurrentLocation() : submit()" />
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
        <dl v-if="store.context.weather">
          <div><dt>Temperature</dt><dd>{{ store.context.weather.temperature_c }}°C</dd></div>
          <div><dt>Humidity</dt><dd>{{ store.context.weather.relative_humidity }}%</dd></div>
          <div><dt>Wind</dt><dd>{{ store.context.weather.wind_speed_kmh }} km/h {{ store.context.weather.wind_direction }}</dd></div>
        </dl>
        <p v-if="!store.context.weather" class="state-message">Current weather is temporarily unavailable.</p>
        <p v-if="store.context.weather" class="hint">Bureau of Meteorology</p>
        <p v-if="store.context.weather" class="hint">Last updated: {{ formatAustralianDateTime(store.context.weather.observed_at) }}</p>
        <div class="fire-danger-forecast">
          <h3>Fire Danger Rating</h3>
          <template v-if="store.context.fire_danger?.availability === 'available'">
            <dl>
              <div><dt>Today</dt><dd>{{ store.context.fire_danger.today ?? 'Not available' }}</dd></div>
              <div><dt>Tomorrow</dt><dd>{{ store.context.fire_danger.tomorrow ?? 'Not available' }}</dd></div>
              <div><dt>Day 3</dt><dd>{{ store.context.fire_danger.day_3 ?? 'Not available' }}</dd></div>
              <div><dt>Day 4</dt><dd>{{ store.context.fire_danger.day_4 ?? 'Not available' }}</dd></div>
            </dl>
            <p v-if="hasMissingForecastPeriods(store.context.fire_danger)" class="hint">Some forecast periods are currently unavailable from the official source.</p>
            <p v-if="store.context.fire_danger.source_updated_at" class="hint">Forecast updated: {{ formatAustralianDateTime(store.context.fire_danger.source_updated_at) }}</p>
          </template>
          <p v-else class="state-message">Official fire danger forecast data is temporarily unavailable. Please try again later.</p>
        </div>
      </div>
    </div>
    <p v-else class="state-message">Add and verify your household address to view local information.</p>
  </section>
</template>

<style scoped>
.intro, .hint, .state-message { color: var(--color-text-muted); }
.saved-address { font-weight: 600; }
.verification { font-size: 0.9rem; margin-top: 0.25rem; }
.address-form { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 0.75rem; margin-top: 1rem; }
.field { min-width: 0; position: relative; }
.location-option { display: flex; align-items: center; gap: 0.65rem; margin-top: 0.75rem; color: var(--color-text-muted); }
.nearby-addresses { margin-top: 1rem; }
.nearby-candidate { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.65rem 0; border-bottom: 1px solid var(--color-border); }
.fire-danger-forecast { margin-top: 1.25rem; }
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
