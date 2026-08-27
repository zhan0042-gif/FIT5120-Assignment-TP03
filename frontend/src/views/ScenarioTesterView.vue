<script setup lang="ts">
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

onMounted(async () => {
  if (householdStore.planStatus === 'idle') await householdStore.loadPlan()
  if (scenarioStore.scenariosStatus === 'idle') await scenarioStore.loadScenarios()
})

const readyToTest = computed(() => (householdStore.plan?.members.length ?? 0) > 0)

const selectedScenario = computed(() =>
  scenarioStore.scenarios.find((s) => s.scenario_id === scenarioStore.selectedScenarioId) ?? null,
)
</script>

<template>
  <div class="scenario-tester">
    <p class="eyebrow">Epic 3 · US3.1-US3.3</p>
    <h1 class="headline">Break the plan on purpose</h1>
    <p class="subhead">Pick a disruption. See exactly which parts of your plan still hold — and which don't.</p>

    <LoadingState v-if="householdStore.planStatus === 'loading'" message="Loading your household plan…" />
    <ErrorState
      v-else-if="householdStore.planStatus === 'error'"
      :message="householdStore.planError ?? undefined"
      @retry="householdStore.loadPlan"
    />

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
          message="Could not load basic scenarios."
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
          :disabled="scenarioStore.testStatus === 'loading'"
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
          :message="scenarioStore.testError ?? undefined"
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
  max-width: 980px;
}

.headline {
  font-size: 1.9rem;
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

@media (max-width: 760px) {
  .tester-grid {
    grid-template-columns: 1fr;
  }
}
</style>
