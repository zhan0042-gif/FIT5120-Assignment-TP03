<script setup>
import { ref } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'
import { formatAustralianDateTime } from '../../utils/dateTime'
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'

const store = useLocalContextStore()
const draftAddress = ref(store.address)

function selectSuggestion(suggestion) {
  store.submitAddress(suggestion.address, suggestion.address)
}

function submit() {
  if (!draftAddress.value.trim()) return
  store.submitAddress(draftAddress.value.trim())
}

</script>

<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h3 class="card-title">Location & bushfire context</h3>
      </div>
    </div>

    <form class="address-form" @submit.prevent="submit">
      <AddressAutocompleteInput
        v-model="draftAddress"
        class="field"
        label="Household address"
        placeholder="Start typing a Victorian street address"
        @select="selectSuggestion"
      />
      <button class="btn btn-primary" type="submit" :disabled="store.saveStatus === 'loading' || !draftAddress.trim()">
        {{ store.saveStatus === 'loading' ? 'Saving…' : 'Save address' }}
      </button>
    </form>
    <p class="hint">Start typing your Victorian address.</p>

    <div v-if="store.location" class="address-status">
      <strong>Address saved</strong>
      <span v-if="store.location.verification_status === 'verified'">Verified</span>
      <span v-else>Location not yet verified</span>
    </div>

    <ErrorState
      v-if="store.saveStatus === 'error'"
      :message="store.contextError || 'Could not save the household address.'"
      @retry="submit"
    />

    <LoadingState v-if="store.contextStatus === 'loading'" message="Looking up local bushfire and fire-weather data…" />

    <p v-else-if="store.contextStatus === 'unverified'" class="hint">
      Local bushfire context will be available once this address is verified.
    </p>

    <div v-else-if="store.contextUnavailable" class="state-block">
      <p class="state-title">Local information is currently unavailable</p>
      <p>Your address is saved. Official local information is temporarily unavailable.</p>
    </div>

    <ErrorState
      v-else-if="store.contextStatus === 'error'"
      :message="store.contextError || 'Could not load local bushfire context.'"
      @retry="store.loadContext"
    />

    <template v-else-if="store.contextStatus === 'success'">
      <div v-if="store.context" class="context-results">
        <div class="context-row">
          <span class="badge" :class="store.context.bushfire_context.is_bushfire_prone_area ? 'badge-accent' : 'badge-neutral'">
            {{ store.context.bushfire_context.is_bushfire_prone_area ? 'Bushfire-prone area' : 'Not a bushfire-prone area' }}
          </span>
        </div>
        <p class="hint">CFA Fire District: {{ store.context.bushfire_context.fire_district }}. Used to match official fire danger information for your area.</p>

        <template v-if="store.context.fire_danger.availability === 'available'">
          <div class="fdr-grid">
            <div v-for="(level, day) in {
              Today: store.context.fire_danger.today,
              Tomorrow: store.context.fire_danger.tomorrow,
              'Day 3': store.context.fire_danger.day_3,
              'Day 4': store.context.fire_danger.day_4,
            }" :key="day" class="fdr-cell">
              <p class="eyebrow">{{ day }}</p>
              <p class="fdr-level">{{ level }}</p>
            </div>
          </div>
          <p class="hint">
            Fire Danger Rating issued {{ formatAustralianDateTime(store.context.fire_danger.source_updated_at) }}
            <template v-if="store.context.fire_danger.source_url">
              · <a :href="store.context.fire_danger.source_url" target="_blank" rel="noopener noreferrer">Bureau of Meteorology source</a>
            </template>
          </p>
        </template>
        <p v-else class="hint">{{ store.context.fire_danger.message }}</p>

        <div class="weather-grid">
          <div><span class="eyebrow">Temp</span><p>{{ store.context.weather.temperature_c }}°C</p></div>
          <div><span class="eyebrow">Humidity</span><p>{{ store.context.weather.relative_humidity }}%</p></div>
          <div><span class="eyebrow">Wind</span><p>{{ store.context.weather.wind_speed_kmh }} km/h {{ store.context.weather.wind_direction }}</p></div>
        </div>
        <p class="hint">
          <a href="http://www.bom.gov.au/other/copyright.shtml" target="_blank" rel="noopener noreferrer">Bureau of Meteorology observation</a>
          from {{ store.context.weather.station_name }} at
          {{ formatAustralianDateTime(store.context.weather.observed_at) }}
        </p>

        <p v-if="store.context.environmental_context.vegetation_context || store.context.environmental_context.terrain_context" class="hint">
          Environment: {{ [store.context.environmental_context.vegetation_context, store.context.environmental_context.terrain_context].filter(Boolean).join(' · ') }}
        </p>
      </div>
    </template>

    <p v-else class="hint">Enter your household address to see local bushfire and fire-weather information.</p>
  </section>
</template>

<style scoped>
.address-form {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}

.address-form .field {
  flex: 1;
  min-width: 240px;
  position: relative;
}

.address-status {
  display: flex;
  gap: 0.6rem;
  margin: 0.5rem 0;
  color: var(--color-text-muted);
}

.hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin-bottom: 1rem;
}

.context-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.35rem;
}

.fdr-grid,
.weather-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 0.75rem;
  margin: 0.75rem 0;
}

.fdr-cell,
.weather-grid > div {
  background: var(--color-bg-card-muted);
  border-radius: var(--radius);
  padding: 0.6rem 0.75rem;
}

.fdr-level {
  font-weight: 700;
  margin-top: 0.2rem;
}
</style>
