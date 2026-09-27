<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import ErrorState from '../common/ErrorState.vue'
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'

const store = useLocalContextStore()
const draftAddress = ref(store.address)
const editing = ref(!store.submittedAddress)
const geolocationStatus = ref('idle')
const geolocationMessage = ref('')
let mounted = true

watch(() => store.address, (value) => { draftAddress.value = value })
watch(() => store.submittedAddress, (value) => {
  // A GET-loaded saved location should render as saved, not as a fresh edit.
  if (value && store.locationStatus === 'success') editing.value = false
})

async function selectSuggestion(suggestion) {
  const unit = draftAddress.value.match(/^\s*(?:unit\s+)?([a-z0-9]+)\s*\/\s*/i)?.[1]
  const selectedAddress = unit ? `${unit}/${suggestion.address}` : suggestion.address
  await store.submitAddress(selectedAddress, selectedAddress, suggestion.provider_reference)
  if (store.saveStatus === 'success') editing.value = false
}

async function submit() {
  if (!draftAddress.value.trim()) return
  await store.submitAddress(draftAddress.value.trim())
  if (store.saveStatus === 'success') editing.value = false
}

async function confirmNearbyAddress(suggestion) {
  await store.submitAddress(suggestion.address, suggestion.address, suggestion.provider_reference)
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
</script>

<template>
  <section class="card address-card">
    <div class="card-header">
      <h2 class="card-title">Household address</h2>
      <button v-if="store.location && !editing" class="btn btn-ghost btn-sm" type="button" @click="editing = true">Edit address</button>
    </div>
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
</template>

<style scoped>
.intro, .hint { color: var(--color-text-muted); }
.saved-address { font-weight: 600; }
.verification { font-size: 0.9rem; margin-top: 0.25rem; }
.address-form { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 0.75rem; margin-top: 1rem; }
.field { min-width: 0; position: relative; }
.location-option { display: flex; align-items: center; gap: 0.65rem; margin-top: 0.75rem; color: var(--color-text-muted); }
.nearby-addresses { margin-top: 1rem; }
.nearby-candidate { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.65rem 0; border-bottom: 1px solid var(--color-border); }
.hint { font-size: 0.875rem; margin-top: 0.65rem; }
@media (max-width: 700px) { .address-form { grid-template-columns: 1fr; } .address-form .btn { width: 100%; } }
</style>
