<script setup>
import { onMounted } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useLocalContextStore } from '../stores/localContext'
import CompletionOverview from '../components/completion/CompletionOverview.vue'
import PreparationSupportBanner from '../components/localContext/PreparationSupportBanner.vue'
import LocalContextCard from '../components/localContext/LocalContextCard.vue'
const householdStore = useHouseholdStore()
const localContextStore = useLocalContextStore()
onMounted(async () => {
  // Overview orchestrates independent plan, address/static-context, live BOM,
  // and preparation-advice states. Their stores keep partial failures isolated.
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  await localContextStore.init()
})
</script>
<template>
  <div class="overview">
    <header class="page-header"><h1>Your area today</h1></header>
    <div class="top-grid">
      <CompletionOverview :completion="householdStore.completion" :loading="householdStore.completionStatus === 'loading'" />
      <PreparationSupportBanner />
    </div>
    <LocalContextCard />
  </div>
</template>
<style scoped>
.overview { width: 100%; min-width: 0; }
.page-header { margin-bottom: 1.75rem; }.page-header h1 { font-size: clamp(2rem, 4vw, 2.25rem); line-height: 1.2; }
.top-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.25rem; align-items: start; }
.top-grid :deep(.card + .card) { margin-top: 0; }
@media (max-width: 800px) { .top-grid { grid-template-columns: 1fr; } }
</style>
