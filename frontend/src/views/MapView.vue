<script setup>
import { onMounted } from 'vue'
import { useFireMapStore } from '../stores/fireMap'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import HistoricalFireMap from '../components/fireMap/HistoricalFireMap.vue'

const store = useFireMapStore()

onMounted(async () => {
  await store.loadFirePoints()
})
</script>

<template>
  <div class="map-view">
    <header class="page-header">
      <h1>Historical fire map</h1>
      <p class="subhead">Historical bushfire records near your household. This shows past activity, not a risk prediction.</p>
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
      @retry="store.loadFirePoints"
    />

    <template v-else-if="store.status === 'success'">
      <p class="summary">
        Showing {{ store.returnedCount }} of {{ store.totalCount }} historical fire
        {{ store.totalCount === 1 ? 'record' : 'records' }} within {{ store.searchRadiusKm }} km.
        <span v-if="store.truncated" class="hint">Some records are not shown.</span>
      </p>
      <HistoricalFireMap
        :household-location="store.householdLocation"
        :points="store.points"
        :search-radius-km="store.searchRadiusKm"
      />
    </template>
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

.summary {
  color: var(--color-text-muted);
  margin-bottom: 1rem;
}

.hint {
  color: var(--color-warning);
}
</style>
