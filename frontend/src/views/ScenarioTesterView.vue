<script setup>
import { computed, onMounted } from 'vue'
import { useHouseholdStore } from '../stores/household'
import { useScenarioStore } from '../stores/scenario'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ScenarioList from '../components/scenario/ScenarioList.vue'
import TestResultPanel from '../components/scenario/TestResultPanel.vue'

const householdStore = useHouseholdStore()
const scenarioStore = useScenarioStore()

const readyToTest = computed(() => householdStore.plan !== null)

const noSavedPlan = computed(
  () =>
    householdStore.planStatus === 'success' &&
    householdStore.completion === null &&
    householdStore.completionStatus === 'idle',
)

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  if (!noSavedPlan.value) await scenarioStore.loadScenarios()
})

async function retryPlanAvailability() {
  await householdStore.loadPlan()
  if (!noSavedPlan.value) await scenarioStore.loadScenarios()
}

const selectedScenario = computed(() =>
  scenarioStore.scenarios.find((s) => s.scenario_id === scenarioStore.selectedScenarioId) ?? null,
)
</script>

<template>
  <div class="scenario-tester">
    <h1 class="headline">Break the plan on purpose</h1>
    <p class="subhead">Pick a disruption. See exactly which parts of your plan still hold — and which don't.</p>

    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan…" />
    <ErrorState
      v-else-if="householdStore.planStatus === 'error'"
      message="Could not load your household plan."
      @retry="householdStore.loadPlan"
    />

    <EmptyState
      v-else-if="noSavedPlan"
      title="No saved plan found"
      message="Build and save your plan before testing scenarios."
    >
      <div class="state-actions">
        <router-link class="btn btn-primary btn-sm" to="/plan">Go to Plan builder</router-link>
        <button class="btn btn-ghost btn-sm" type="button" @click="retryPlanAvailability">Retry</button>
      </div>
    </EmptyState>

    <EmptyState
      v-else-if="!readyToTest"
      title="Add household information first"
      message="Basic testing needs at least one household member recorded in your plan."
    >
      <router-link class="btn btn-primary btn-sm" to="/plan">Go to Plan builder</router-link>
    </EmptyState>

    <div v-else class="tester-grid">
      <div class="scenario-column">
        <LoadingState v-if="scenarioStore.scenariosStatus === 'loading'" message="Loading scenarios…" />
        <ErrorState
          v-else-if="scenarioStore.scenariosStatus === 'error'"
          message="Could not load scenarios. Please try again."
          @retry="scenarioStore.loadScenarios"
        />
        <ScenarioList
          v-else
          :scenarios="scenarioStore.scenarios"
          :selected-id="scenarioStore.selectedScenarioId"
          @select="scenarioStore.selectScenario"
        />

        <button
          v-if="scenarioStore.selectedScenarioId"
          class="btn btn-accent run-btn"
          type="button"
          :disabled="scenarioStore.testStatus === 'loading' || !selectedScenario?.enabled"
          @click="scenarioStore.runTest"
        >
          {{ scenarioStore.testStatus === 'loading' ? 'Running test…' : `Start test: ${selectedScenario?.title}` }}
        </button>
      </div>

      <section class="card result-column">
        <EmptyState v-if="!scenarioStore.selectedScenarioId" title="Choose a scenario to test" message="Select a scenario on the left to see what it will check." />
        <LoadingState v-else-if="scenarioStore.testStatus === 'loading'" message="Testing your current plan…" />
        <ErrorState
          v-else-if="scenarioStore.testStatus === 'error'"
          message="The scenario test could not be completed. Check that your plan has been saved, then try again."
          @retry="scenarioStore.runTest"
        />
        <EmptyState
          v-else-if="scenarioStore.testStatus === 'idle'"
          title="Ready to test"
          :message="selectedScenario?.description"
        />
        <TestResultPanel v-else-if="scenarioStore.result" :result="scenarioStore.result" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.scenario-tester {
  width: 100%;
  min-width: 0;
}

.headline {
  font-size: 2rem;
  margin: 0.4rem 0 0.5rem;
}

.subhead {
  color: var(--color-text-muted);
  margin-bottom: 1.75rem;
}

.tester-grid {
  display: grid;
  grid-template-columns: minmax(220px, 320px) 1fr;
  gap: 1.5rem;
  align-items: start;
}

.scenario-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.run-btn {
  width: 100%;
}

.state-actions {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

@media (max-width: 760px) {
  .tester-grid {
    grid-template-columns: 1fr;
  }
}
</style>
