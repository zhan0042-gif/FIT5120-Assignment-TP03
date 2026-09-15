<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useFireMapStore } from '../stores/fireMap'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import HistoricalFireMap from '../components/fireMap/HistoricalFireMap.vue'
import { formatAustralianDate } from '../utils/dateTime'

const store = useFireMapStore()
const historicalMap = ref(null)
const featuredLocations = reactive({
  nearest: { status: 'idle', address: null },
  mostRecent: { status: 'idle', address: null },
})

function recordedDate(record) {
  return record?.start_date ? formatAustralianDate(record.start_date) : 'Recorded date unavailable'
}

function distanceFromHome(record) {
  return `${record.distance_km.toFixed(1)} km from your home`
}

function locationText(state) {
  if (state.status === 'loading') return 'Finding approximate location...'
  return state.address
    ? `Approximate location: ${state.address}`
    : 'Approximate location unavailable'
}

async function loadFeaturedLocation(state, record) {
  if (!record) return
  state.status = 'loading'
  state.address = await store.resolveApproximateLocation(record)
  state.status = state.address ? 'success' : 'unavailable'
}

async function loadMap() {
  await store.loadFirePoints()
  if (store.status !== 'success') return
  await Promise.all([
    loadFeaturedLocation(featuredLocations.nearest, store.nearestFire),
    loadFeaturedLocation(featuredLocations.mostRecent, store.mostRecentFire),
  ])
}

function focusFire(record) {
  historicalMap.value?.focusPoint(record)
}

const recordCountText = computed(() => {
  if (!Number.isFinite(store.totalCount) || !Number.isFinite(store.searchRadiusKm)) return ''
  const radius = Number.isInteger(store.searchRadiusKm)
    ? store.searchRadiusKm
    : store.searchRadiusKm.toFixed(1)
  const noun = store.totalCount === 1 ? 'record' : 'records'
  return `${store.totalCount} historical fire ${noun} within ${radius} km`
})

onMounted(async () => {
  await loadMap()
})
</script>

<template>
  <div class="map-view">
    <header class="page-header">
      <h1>Historical Fire Map</h1>
      <p class="subhead">See past bushfire records near your home.</p>
    </header>

    <LoadingState v-if="store.status === 'loading'" message="Loading historical fire map..." />

    <p v-else-if="store.status === 'unverified'" class="state-message">
      This map needs a verified household address.
      <router-link to="/overview">Add and verify your address</router-link> to see nearby historical fire records.
    </p>

    <div v-else-if="store.status === 'unavailable'" class="state-message">
      Historical fire map data is temporarily unavailable. Please try again later.
    </div>

    <ErrorState
      v-else-if="store.status === 'error'"
      :message="store.error || 'Could not load the historical fire map.'"
      @retry="loadMap"
    />

    <div v-else-if="store.status === 'success'" class="map-layout">
      <HistoricalFireMap
        ref="historicalMap"
        :household-location="store.householdLocation"
        :points="store.points"
        :search-radius-km="store.searchRadiusKm"
        :resolve-location="store.resolveApproximateLocation"
      />

      <aside class="insight-panel" aria-label="Historical fire insights">
        <button
          v-if="store.nearestFire"
          class="card insight-card"
          type="button"
          @click="focusFire(store.nearestFire)"
        >
          <h2>Nearest historical fire</h2>
          <p class="insight-value">{{ distanceFromHome(store.nearestFire) }}</p>
          <p class="insight-detail">
            {{ store.nearestFire.start_date ? `Recorded: ${recordedDate(store.nearestFire)}` : recordedDate(store.nearestFire) }}
          </p>
          <p class="insight-detail">{{ locationText(featuredLocations.nearest) }}</p>
        </button>
        <section v-else class="card insight-card insight-card-empty">
          <h2>Nearest historical fire</h2>
          <p class="insight-empty">No record found within {{ store.searchRadiusKm }} km.</p>
        </section>

        <button
          v-if="store.mostRecentFire"
          class="card insight-card"
          type="button"
          @click="focusFire(store.mostRecentFire)"
        >
          <h2>Most recent historical fire</h2>
          <p class="insight-value">{{ recordedDate(store.mostRecentFire) }}</p>
          <p class="insight-detail">{{ distanceFromHome(store.mostRecentFire) }}</p>
          <p class="insight-detail">{{ locationText(featuredLocations.mostRecent) }}</p>
        </button>
        <section v-else class="card insight-card insight-card-empty">
          <h2>Most recent historical fire</h2>
          <p class="insight-empty">No record found within {{ store.searchRadiusKm }} km.</p>
        </section>

        <p v-if="recordCountText" class="record-count">{{ recordCountText }}</p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.map-view {
  width: 100%;
  min-width: 0;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-header h1 {
  font-size: clamp(2rem, 4vw, 2.25rem);
  line-height: 1.2;
}

.subhead {
  color: var(--color-text-muted);
  margin-top: 0.5rem;
}

.state-message {
  color: var(--color-text-muted);
}

.map-layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  align-items: start;
  gap: clamp(2rem, 5vw, 4rem);
}

.insight-panel {
  display: grid;
  align-content: start;
  gap: 1rem;
  padding-top: 0.25rem;
}

.insight-card {
  width: 100%;
  color: var(--color-text);
  text-align: left;
}

.insight-card + .insight-card {
  margin-top: 0;
}

.insight-card:not(.insight-card-empty) {
  cursor: pointer;
}

.insight-card:not(.insight-card-empty):hover {
  border-color: var(--color-border-strong);
  background: var(--color-bg-card-muted);
}

.insight-card:not(.insight-card-empty):focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.insight-card h2 {
  font-size: 1rem;
  line-height: 1.35;
  margin-bottom: 0.75rem;
}

.insight-value {
  color: var(--color-text);
  font-size: 1.25rem;
  font-weight: 650;
  line-height: 1.35;
}

.insight-detail,
.insight-empty {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  margin-top: 0.35rem;
}

.record-count {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

@media (max-width: 900px) {
  .map-layout {
    grid-template-columns: 1fr;
  }

  .insight-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.5rem;
    padding-top: 0;
  }

  .record-count {
    grid-column: 1 / -1;
  }
}

@media (max-width: 560px) {
  .insight-panel {
    grid-template-columns: 1fr;
  }
}
</style>
