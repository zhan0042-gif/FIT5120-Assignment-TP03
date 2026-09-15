import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'

export const useRendezvousStore = defineStore('rendezvous', () => {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)
  const explanation = ref(null)
  const explanationStatus = ref('idle')

  async function runSimulation(householdId) {
    // not_applicable and unavailable are answers, not failures: each carries the
    // reason the user needs to read. Only a thrown request is an error here.
    if (!householdId) {
      status.value = 'error'
      error.value = 'No household is loaded yet.'
      return
    }
    status.value = 'loading'
    error.value = null
    // A passage must never outlive the figures it described.
    explanation.value = null
    explanationStatus.value = 'idle'
    try {
      result.value = await api.simulateRendezvous(householdId)
      status.value = 'success'
    } catch (thrown) {
      // Drop any earlier result: a stale figure beside a failure reads as current.
      result.value = null
      status.value = 'error'
      error.value =
        thrown instanceof Error ? thrown.message : 'The simulation could not run.'
    }
  }

  async function requestExplanation(householdId) {
    // The result goes up with the request: the passage must describe the figures
    // on screen, not figures fetched again a moment later.
    if (!householdId || !result.value || result.value.status !== 'ready') return
    explanationStatus.value = 'loading'
    try {
      const body = await api.explainRendezvous(householdId, result.value)
      // A null explanation is an answer, not a failure: the passage was rejected
      // or the model was unavailable, and the panel simply shows nothing.
      explanation.value = body.explanation ?? null
      explanationStatus.value = 'success'
    } catch {
      explanation.value = null
      explanationStatus.value = 'error'
    }
  }

  return {
    result,
    status,
    error,
    explanation,
    explanationStatus,
    runSimulation,
    requestExplanation,
  }
})
