import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'

export const useRendezvousStore = defineStore('rendezvous', () => {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)

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

  return { result, status, error, runSimulation }
})
