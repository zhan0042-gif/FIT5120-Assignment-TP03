<script setup>
import { computed, onMounted, ref } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useTravelRoutesStore } from '../stores/travelRoutes'
import { useTravelDisruptionsStore } from '../stores/travelDisruptions'
import TravelDisruptionMap from '../components/scenario/TravelDisruptionMap.vue'
import TravelDisruptionPanel from '../components/scenario/TravelDisruptionPanel.vue'
import { api } from '../api/client.js'
import { buildTravelMapData, hasMapCoordinates } from '../utils/travelMapData'

const householdStore = useHouseholdStore()
const disruptionStore = useTravelDisruptionsStore()
const routeStore = useTravelRoutesStore()
const householdLocation = ref(null)
const mapData = computed(() => buildTravelMapData(disruptionStore.result, householdStore.plan))

onMounted(async () => {
  if (householdStore.planStatus === 'idle') {
    void householdStore.loadPlan()
  }
  try {
    const householdId = await householdStore.ensureHousehold()
    void routeStore.load(householdId)
    // Home provides spatial context only; its absence must not hide results.
    void api.getLocation(householdId).then((location) => {
      householdLocation.value = hasMapCoordinates(location)
        ? { ...location, address: location.canonical_address || location.address }
        : null
    }).catch(() => { householdLocation.value = null })
    if (disruptionStore.status === 'idle') await disruptionStore.load(householdId, 10)
  } catch {
    void routeStore.load(null)
    if (disruptionStore.status === 'idle') await disruptionStore.load(null)
  }
})
</script>

<template>
  <div class="travel-readiness">
    <header class="page-header">
      <h1>Travel Readiness</h1>
      <p>Check currently reported road disruptions near your saved evacuation destinations.</p>
      <p class="safety-note">Routes show road travel from your home to saved destinations. Reported disruptions are identified within 10 km of each destination and are not currently matched against the route. This is not route-intersection analysis. Nearby reported disruptions do not necessarily mean your evacuation route is blocked or unsafe.</p>
    </header>

    <div class="travel-layout">
      <section class="map-section" aria-label="Destination and disruption map" data-voice-section="travel-map">
        <TravelDisruptionMap
          v-if="mapData.destinations.length || householdLocation"
          :destinations="mapData.destinations"
          :disruptions="mapData.disruptions"
          :household-location="householdLocation"
          :routes="routeStore.result?.routes ?? []"
        />
        <p v-else-if="disruptionStore.result?.status === 'available'" class="map-empty">
          No verified destination coordinates are available for the map. Reported disruption details remain available.
        </p>
        <p v-else class="map-empty">The map will appear when saved home or verified destination coordinates are available.</p>
        <p v-if="routeStore.status === 'loading'" class="route-note" role="status">Loading road routes...</p>
        <p v-else-if="routeStore.status === 'partial'" class="route-note" role="status">Some road routes are unavailable. Available routes are shown.</p>
        <p v-else-if="routeStore.status === 'unavailable'" class="route-note" role="status">{{ routeStore.result?.unavailable_reason || routeStore.error || 'Road routes are currently unavailable.' }}</p>
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
.route-note { color: var(--color-text-muted); font-size: 0.875rem; line-height: 1.5; }
.map-section { min-width: 0; }
.map-empty { align-items: center; background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: var(--radius); color: var(--color-text-muted); display: flex; justify-content: center; min-height: 16rem; padding: 1.5rem; text-align: center; }
.results-column { min-width: 0; }
@media (max-width: 1100px) {
  .travel-layout { grid-template-columns: minmax(0, 1fr); }
}
</style>
