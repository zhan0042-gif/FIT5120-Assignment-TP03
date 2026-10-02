import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'

export const useTravelRoutesStore = defineStore('travelRoutes', () => {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)
  let revision = 0

  async function load(householdId) {
    const requestRevision = ++revision
    result.value = null
    error.value = null
    if (!householdId) {
      status.value = 'unavailable'
      error.value = 'No household is loaded yet.'
      return
    }
    status.value = 'loading'
    try {
      const response = await api.getTravelRoutes(householdId)
      if (requestRevision !== revision) return
      result.value = response
      status.value = ['available', 'partial'].includes(response.status) ? response.status : 'unavailable'
    } catch {
      if (requestRevision !== revision) return
      status.value = 'unavailable'
      error.value = 'Road routes could not be loaded. Saved destinations and reported disruptions remain available.'
    }
  }

  function reset() {
    revision += 1
    result.value = null
    status.value = 'idle'
    error.value = null
  }

  return { result, status, error, load, reset }
})
