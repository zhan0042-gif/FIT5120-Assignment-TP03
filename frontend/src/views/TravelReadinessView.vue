<script setup>
import { computed, onMounted, ref } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useTravelDisruptionsStore } from '../stores/travelDisruptions'
import TravelDisruptionMap from '../components/scenario/TravelDisruptionMap.vue'
import TravelDisruptionPanel from '../components/scenario/TravelDisruptionPanel.vue'
import { api } from '../api/client.js'
import { buildTravelMapData, hasMapCoordinates } from '../utils/travelMapData'

const householdStore = useHouseholdStore()
const disruptionStore = useTravelDisruptionsStore()
const householdLocation = ref(null)
const mapData = computed(() => buildTravelMapData(disruptionStore.result))

onMounted(async () => {
  if (householdStore.planStatus === 'idle') {
    void householdStore.loadPlan()
  }
  try {
    const householdId = await householdStore.ensureHousehold()
    // Home provides spatial context only; its absence must not hide results.
    void api.getLocation(householdId).then((location) => {
      householdLocation.value = hasMapCoordinates(location)
        ? { ...location, address: location.canonical_address || location.address }
        : null
    }).catch(() => { householdLocation.value = null })
    if (disruptionStore.status === 'idle') await disruptionStore.load(householdId, 10)
  } catch {
    if (disruptionStore.status === 'idle') await disruptionStore.load(null)
  }
})
</script>

<template>
  <div class="travel-readiness">
    <header class="page-header">
      <h1>Travel Readiness</h1>
      <p>Check currently reported road disruptions near your saved evacuation destinations.</p>
      <p class="safety-note">Search areas are centred on saved destinations, not travel routes. This is not route-intersection analysis. Nearby reported disruptions do not necessarily mean your evacuation route is blocked or unsafe.</p>
    </header>

    <div class="travel-layout">
      <section class="map-section" aria-label="Destination and disruption map">
        <TravelDisruptionMap
          v-if="mapData.destinations.length"
          :key="disruptionStore.result.checked_at"
          :destinations="mapData.destinations"
          :disruptions="mapData.disruptions"
          :household-location="householdLocation"
        />
        <p v-else-if="disruptionStore.result?.status === 'available'" class="map-empty">
          No verified destination coordinates are available for the map. Reported disruption details remain available.
        </p>
        <p v-else class="map-empty">The destination map will appear when disruption results are available.</p>
      </section>

      <aside class="results-column" aria-label="Reported disruptions">
        <TravelDisruptionPanel />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.travel-readiness { width: 100%; min-width: 0; }
.page-header { margin-bottom: 1.5rem; }
.page-header h1 { font-size: clamp(2rem, 4vw, 2.25rem); }
.page-header p, .safety-note { color: var(--color-text-muted); line-height: 1.5; }
.page-header p { margin-top: 0.5rem; }
.page-header .safety-note { font-size: 0.875rem; margin-top: 0.75rem; max-width: 65rem; }
.travel-layout { align-items: start; display: grid; gap: 1.25rem; grid-template-columns: minmax(0, 11fr) minmax(19rem, 9fr); min-width: 0; }
.map-section { min-width: 0; }
.map-empty { align-items: center; background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: var(--radius); color: var(--color-text-muted); display: flex; justify-content: center; min-height: 16rem; padding: 1.5rem; text-align: center; }
.results-column { min-width: 0; }
@media (max-width: 1100px) {
  .travel-layout { grid-template-columns: minmax(0, 1fr); }
}
</style>
