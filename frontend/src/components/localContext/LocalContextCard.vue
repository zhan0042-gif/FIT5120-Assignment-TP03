<script setup lang="ts">
import { ref } from 'vue'
import { useLocalContextStore } from '../../stores/localContext'
import LoadingState from '../common/LoadingState.vue'
import ErrorState from '../common/ErrorState.vue'

const store = useLocalContextStore()
const draftAddress = ref(store.address)

function submit() {
  if (!draftAddress.value.trim()) return
  store.submitAddress(draftAddress.value.trim())
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
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
        <input id="address" v-model="draftAddress" type="text" placeholder="e.g. 84 Wattle Track, Wattlebrook VIC" />
      </div>
      <button class="btn btn-primary" type="submit" :disabled="store.contextStatus === 'loading' || !draftAddress.trim()">
        {{ store.contextStatus === 'loading' ? 'Checking…' : 'Check location' }}
      </button>
    </form>
    <p class="hint">Enter a Victorian household address.</p>

    <LoadingState v-if="store.contextStatus === 'loading'" message="Looking up local bushfire and fire-weather data…" />

    <div v-else-if="store.contextUnavailable" class="state-block">
      <p class="state-title">Local information is currently unavailable</p>
      <p>We couldn't match this address to official Victorian bushfire data, or the latest data isn't available right now.</p>
    </div>

    <ErrorState v-else-if="store.contextStatus === 'error'" :message="store.contextError ?? undefined" @retry="submit" />

    <template v-else-if="store.contextStatus === 'success'">
      <div v-if="store.context" class="context-results">
        <div class="context-row">
          <span class="badge" :class="store.context.bushfire_context.is_bushfire_prone_area ? 'badge-accent' : 'badge-neutral'">
            {{ store.context.bushfire_context.is_bushfire_prone_area ? 'Bushfire-prone area' : 'Not a bushfire-prone area' }}
          </span>
          <span>Temporary spatial context pending DS integration</span>
        </div>
        <p class="hint">Temporary fire district: {{ store.context.bushfire_context.fire_district }}. This spatial classification currently uses development data.</p>

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
            Fire Danger Rating issued {{ formatTime(store.context.fire_danger.source_updated_at) }}
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
          {{ formatTime(store.context.weather.observed_at) }}
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
}

.hint {
  font-size: 0.8rem;
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
