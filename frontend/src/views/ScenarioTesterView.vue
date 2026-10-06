<script setup>
import { computed, onMounted } from 'vue'
import { useHouseholdStore } from '../stores/household'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import RendezvousPanel from '../components/scenario/RendezvousPanel.vue'
const householdStore = useHouseholdStore()
const readyToTest = computed(() => householdStore.plan !== null)
const noSavedPlan = computed(() => householdStore.planStatus === 'success' && householdStore.completion === null && householdStore.completionStatus === 'idle')
onMounted(async () => { if (householdStore.planStatus === 'idle') await householdStore.loadPlan() })
</script>
<template>
  <div class="scenario-tester">
    <h1 class="sr-only">Test my plan</h1>
    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan..." />
    <ErrorState v-else-if="householdStore.planStatus === 'error'" message="Could not load your household plan." @retry="householdStore.loadPlan" />
    <EmptyState v-else-if="noSavedPlan" title="No saved plan found" message="Build and save your plan before running the simulation."><div class="state-actions"><router-link class="btn btn-primary btn-sm" to="/plan">Go to My Plan</router-link><button class="btn btn-ghost btn-sm" type="button" @click="householdStore.loadPlan">Retry</button></div></EmptyState>
    <EmptyState v-else-if="!readyToTest" title="Add household information first" message="The simulation needs at least one household member recorded in your plan."><router-link class="btn btn-primary btn-sm" to="/plan">Go to My Plan</router-link></EmptyState>
    <RendezvousPanel v-else />
  </div>
</template>
<style scoped>
.scenario-tester { width: 100%; min-width: 0; }
.state-actions { display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap; }
</style>
