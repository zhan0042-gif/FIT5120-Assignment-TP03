<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../../api/client'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'
import { formatAustralianDateTime } from '../../utils/dateTime'

const store = useLocalContextStore()
const draftAddress = ref(store.address)
const suggestions = ref([])
const suggestionStatus = ref('idle')
const activeSuggestion = ref(-1)
let lookupTimer
let requestSequence = 0
let selectingSuggestion = false

function isMeaningfulAddressQuery(query) {
  return query.length >= 4 && /\d/.test(query) && /[a-z]/i.test(query)
}

watch(draftAddress, (next) => {
  if (selectingSuggestion) {
    selectingSuggestion = false
    return
  }
  if (lookupTimer) clearTimeout(lookupTimer)
  const query = next.trim()
  activeSuggestion.value = -1
  if (!isMeaningfulAddressQuery(query)) {
    requestSequence += 1
    suggestions.value = []
    suggestionStatus.value = 'idle'
    return
  }
  suggestionStatus.value = 'loading'
  const sequence = ++requestSequence
  lookupTimer = setTimeout(async () => {
    try {
      const results = await api.getAddressSuggestions(query)
      if (sequence !== requestSequence || draftAddress.value.trim() !== query) return
      suggestions.value = results
      suggestionStatus.value = results.length ? 'success' : 'empty'
    } catch {
      if (sequence !== requestSequence) return
      suggestions.value = []
      suggestionStatus.value = 'error'
    }
  }, 350)
})

onBeforeUnmount(() => {
  if (lookupTimer) clearTimeout(lookupTimer)
  requestSequence += 1
})

function selectSuggestion(suggestion) {
  selectingSuggestion = true
  requestSequence += 1
  draftAddress.value = suggestion.address
  suggestions.value = []
  suggestionStatus.value = 'idle'
  activeSuggestion.value = -1
  store.submitAddress(suggestion.address, suggestion.address)
}

function addressKeydown(event) {
  if (!suggestions.value.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeSuggestion.value = (activeSuggestion.value + 1) % suggestions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeSuggestion.value = activeSuggestion.value <= 0 ? suggestions.value.length - 1 : activeSuggestion.value - 1
  } else if (event.key === 'Enter' && activeSuggestion.value >= 0) {
    event.preventDefault()
    selectSuggestion(suggestions.value[activeSuggestion.value])
  } else if (event.key === 'Escape') {
    suggestions.value = []
    activeSuggestion.value = -1
  }
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
      <div class="field">
        <label for="address">Household address</label>
        <input
          id="address"
          v-model="draftAddress"
          type="text"
          placeholder="Start typing a Victorian street address"
          autocomplete="street-address"
          aria-autocomplete="list"
          :aria-expanded="suggestions.length > 0"
          :aria-activedescendant="activeSuggestion >= 0 ? `address-suggestion-${activeSuggestion}` : undefined"
          @keydown="addressKeydown"
        />
        <ul v-if="suggestions.length" class="suggestion-list" role="listbox" aria-label="Victorian address suggestions">
          <li v-for="(suggestion, index) in suggestions" :id="`address-suggestion-${index}`" :key="`${suggestion.address}-${suggestion.latitude}-${suggestion.longitude}`" role="option" :aria-selected="index === activeSuggestion">
            <button type="button" :class="{ 'is-active': index === activeSuggestion }" @mousedown.prevent="selectSuggestion(suggestion)">
              <span>{{ suggestion.address }}</span>
              <small>{{ suggestion.suburb_or_locality }} · {{ suggestion.state }} {{ suggestion.postcode }}</small>
            </button>
          </li>
        </ul>
        <span v-if="suggestionStatus === 'loading'" class="field-help">Finding official Victorian addresses…</span>
        <span v-else-if="suggestionStatus === 'empty'" class="field-help">No matching address yet. Add the street number, locality or postcode.</span>
        <span v-else-if="suggestionStatus === 'error'" class="field-error">Address suggestions are unavailable. You can still enter a complete address and check it.</span>
      </div>
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

.field-help {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.address-status {
  display: flex;
  gap: 0.6rem;
  margin: 0.5rem 0;
  color: var(--color-text-muted);
}

.suggestion-list {
  position: absolute;
  z-index: 20;
  top: 100%;
  width: 100%;
  max-height: 16rem;
  overflow-y: auto;
  list-style: none;
  margin: 0.25rem 0 0;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-card);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.14);
}

.suggestion-list li + li {
  border-top: 1px solid var(--color-border);
}

.suggestion-list button {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 0.15rem;
  border: 0;
  padding: 0.65rem 0.75rem;
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.suggestion-list button:hover,
.suggestion-list button.is-active {
  background: var(--color-bg-card-muted);
}

.suggestion-list small {
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
