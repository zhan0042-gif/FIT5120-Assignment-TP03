<script setup>
import { computed, onMounted } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useScenarioStore } from '../stores/scenario'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ScenarioList from '../components/scenario/ScenarioList.vue'
import TestResultPanel from '../components/scenario/TestResultPanel.vue'
import RendezvousPanel from '../components/scenario/RendezvousPanel.vue'
const householdStore = useHouseholdStore()
const scenarioStore = useScenarioStore()
const readyToTest = computed(() => householdStore.plan !== null)
const noSavedPlan = computed(() => householdStore.planStatus === 'success' && householdStore.completion === null && householdStore.completionStatus === 'idle')
const selectedScenario = computed(() => scenarioStore.scenarios.find((item) => item.scenario_id === scenarioStore.selectedScenarioId) ?? null)
// Titles and explanations are presentation mappings only. Availability and the
// actual scenario outcome remain authoritative backend decisions.
const selectedDescription = computed(() => ({
  vehicle_unavailable: 'Check whether another recorded transport option and an eligible driver are available.',
  person_unavailable: 'Check whether important responsibilities have a different backup person.',
  destination_unavailable: 'Check whether another recorded destination is available.',
})[selectedScenario.value?.scenario_id] ?? selectedScenario.value?.description)
onMounted(async () => { if (householdStore.planStatus === 'idle') await householdStore.loadPlan(); if (!noSavedPlan.value) await scenarioStore.loadScenarios() })
async function retryPlanAvailability() { await householdStore.loadPlan(); if (!noSavedPlan.value) await scenarioStore.loadScenarios() }
</script>
<template>
  <div class="scenario-tester">
    <h1>What happens if?</h1>
    <p class="subhead">Each scenario checks your saved plan for a backup you can actually use.</p>
    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan..." />
    <ErrorState v-else-if="householdStore.planStatus === 'error'" message="Could not load your household plan." @retry="householdStore.loadPlan" />
    <EmptyState v-else-if="noSavedPlan" title="No saved plan found" message="Build and save your plan before testing scenarios."><div class="state-actions"><router-link class="btn btn-primary btn-sm" to="/plan">Go to My Plan</router-link><button class="btn btn-ghost btn-sm" type="button" @click="retryPlanAvailability">Retry</button></div></EmptyState>
    <EmptyState v-else-if="!readyToTest" title="Add household information first" message="Basic testing needs at least one household member recorded in your plan."><router-link class="btn btn-primary btn-sm" to="/plan">Go to My Plan</router-link></EmptyState>
    <div v-else class="tester-grid">
      <div class="scenario-column">
        <LoadingState v-if="scenarioStore.scenariosStatus === 'loading'" message="Loading scenarios..." />
        <ErrorState v-else-if="scenarioStore.scenariosStatus === 'error'" message="Could not load scenarios. Please try again." @retry="scenarioStore.loadScenarios" />
        <ScenarioList v-else :scenarios="scenarioStore.scenarios" :selected-id="scenarioStore.selectedScenarioId" @select="scenarioStore.selectScenario" />
        <p class="scenario-caveat">Hypothetical planning exercises. Not evacuation advice — for that, follow the CFA.</p>
        <button v-if="scenarioStore.selectedScenarioId" class="btn btn-accent run-btn" type="button" :disabled="scenarioStore.testStatus === 'loading' || !selectedScenario?.enabled" @click="scenarioStore.runTest">{{ scenarioStore.testStatus === 'loading' ? 'Running test...' : 'Run test' }}</button>
      </div>
      <section class="card result-column">
        <EmptyState v-if="!scenarioStore.selectedScenarioId" title="How to test your plan">
          <ol class="test-steps">
            <li><span class="step-number">1</span><span><strong>Pick a scenario</strong> from the list, such as your car being unavailable.</span></li>
            <li><span class="step-number">2</span><span><strong>Click "Run test"</strong>, the button that appears under the list.</span></li>
            <li><span class="step-number">3</span><span><strong>Read the result here.</strong> It shows whether your saved plan still has a backup that works.</span></li>
          </ol>
        </EmptyState>
        <LoadingState v-else-if="scenarioStore.testStatus === 'loading'" message="Testing your current plan..." />
        <ErrorState v-else-if="scenarioStore.testStatus === 'error'" message="The scenario test could not be completed. Check that your plan has been saved, then try again." @retry="scenarioStore.runTest" />
        <EmptyState v-else-if="scenarioStore.testStatus === 'idle'" title="Ready to test" :message="selectedDescription" />
        <TestResultPanel v-else-if="scenarioStore.result" :result="scenarioStore.result" />
      </section>
    </div>
    <RendezvousPanel
      v-if="!noSavedPlan && readyToTest"
    />

  </div>
</template>
<style scoped>
.scenario-tester { width: 100%; min-width: 0; }.scenario-tester > h1 { font-size: clamp(2rem, 4vw, 2.25rem); line-height: 1.2; }.subhead { color: var(--color-text-muted); margin: 0.5rem 0 1.75rem; }
.tester-grid { display: grid; grid-template-columns: minmax(250px, 340px) 1fr; gap: 1.5rem; align-items: start; }.scenario-column { display: flex; flex-direction: column; gap: 1rem; }.run-btn { width: 100%; }.state-actions { display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap; }
.test-steps { display: inline-grid; gap: 0.85rem; list-style: none; margin: 0.5rem 0 0; padding: 0; text-align: left; max-width: 30rem; }
.test-steps li { align-items: flex-start; display: flex; gap: 0.75rem; line-height: 1.5; }
.test-steps strong { color: var(--color-text); }
.step-number { align-items: center; background: var(--color-accent-soft); border-radius: 50%; color: var(--color-accent-ink); display: inline-flex; flex: none; font-size: 0.85rem; font-weight: 700; height: 1.6rem; justify-content: center; width: 1.6rem; }
.scenario-caveat { color: var(--color-text-muted); font-size: 0.8125rem; line-height: 1.5; margin: 0; }
@media (max-width: 760px) { .tester-grid { grid-template-columns: 1fr; } }
</style>
