import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Scenario, TestResult } from '../types/scenario'
import type { AsyncStatus } from '../types/async'

export const useScenarioStore = defineStore('scenario', () => {
  const scenarios = ref<Scenario[]>([])
  const scenariosStatus = ref<AsyncStatus>('idle')

  const selectedScenarioId = ref<string | null>(null)
  const result = ref<TestResult | null>(null)
  const testStatus = ref<AsyncStatus>('idle')
  const testError = ref<string | null>(null)

  async function loadScenarios() {
    scenariosStatus.value = 'loading'
    try {
      scenarios.value = await api.getBasicScenarios()
      scenariosStatus.value = 'success'
    } catch {
      scenariosStatus.value = 'error'
    }
  }

  function selectScenario(scenarioId: string) {
    selectedScenarioId.value = scenarioId
    result.value = null
    testStatus.value = 'idle'
  }

  async function runTest() {
    if (!selectedScenarioId.value) return
    testStatus.value = 'loading'
    testError.value = null
    try {
      result.value = await api.runBasicTest(selectedScenarioId.value)
      testStatus.value = 'success'
    } catch (err) {
      testStatus.value = 'error'
      testError.value = err instanceof Error ? err.message : 'Failed to run the test.'
    }
  }

  return {
    scenarios,
    scenariosStatus,
    selectedScenarioId,
    result,
    testStatus,
    testError,
    loadScenarios,
    selectScenario,
    runTest,
  }
})
