import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import { useHouseholdStore } from './household'

export const useScenarioStore = defineStore('scenario', () => {
  const householdStore = useHouseholdStore()
  const scenarios = ref([])
  const scenariosStatus = ref('idle')
  const scenariosError = ref(null)

  const selectedScenarioId = ref(null)
  const result = ref(null)
  const testStatus = ref('idle')
  const testError = ref(null)

  async function loadScenarios() {
    scenariosStatus.value = 'loading'
    scenariosError.value = null
    try {
      const householdId = await householdStore.ensureHousehold()
      scenarios.value = await api.getBasicScenarios(householdId)
      const selected = scenarios.value.find(
        (scenario) => scenario.scenario_id === selectedScenarioId.value,
      )
      if (!selected?.enabled) {
        selectedScenarioId.value = null
        result.value = null
        testStatus.value = 'idle'
      }
      scenariosStatus.value = 'success'
    } catch (err) {
      scenariosStatus.value = 'error'
      scenariosError.value =
        err instanceof Error ? err.message : 'Could not load basic scenarios.'
    }
  }

  function selectScenario(scenarioId) {
    const scenario = scenarios.value.find((item) => item.scenario_id === scenarioId)
    if (!scenario?.enabled) return
    selectedScenarioId.value = scenarioId
    result.value = null
    testStatus.value = 'idle'
  }

  async function runTest() {
    if (!selectedScenarioId.value) return
    const scenario = scenarios.value.find(
      (item) => item.scenario_id === selectedScenarioId.value,
    )
    if (!scenario?.enabled) return
    testStatus.value = 'loading'
    testError.value = null
    try {
      const householdId = await householdStore.ensureHousehold()
      result.value = await api.runBasicTest(householdId, selectedScenarioId.value)
      testStatus.value = 'success'
    } catch (err) {
      testStatus.value = 'error'
      testError.value = err instanceof Error ? err.message : 'Failed to run the test.'
    }
  }

  return {
    scenarios,
    scenariosStatus,
    scenariosError,
    selectedScenarioId,
    result,
    testStatus,
    testError,
    loadScenarios,
    selectScenario,
    runTest,
  }
})
