import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'

export const useTravelDisruptionsStore = defineStore('travelDisruptions', () => {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)

  async function load(householdId, radiusKm = 10) {
    if (!householdId) {
      result.value = null
      status.value = 'error'
      error.value = 'No household is loaded yet.'
      return
    }

    status.value = 'loading'
    error.value = null

    try {
      result.value = await api.getTravelDisruptions(
        householdId,
        radiusKm,
      )
      status.value = 'success'
    } catch (thrown) {
      result.value = null
      status.value = 'error'
      error.value =
        thrown instanceof Error
          ? thrown.message
          : 'Road-disruption information could not be loaded.'
    }
  }

  function reset() {
    result.value = null
    status.value = 'idle'
    error.value = null
  }

  return {
    result,
    status,
    error,
    load,
    reset,
  }
})