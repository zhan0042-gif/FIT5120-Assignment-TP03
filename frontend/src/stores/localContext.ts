import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ApiError, api } from '../api/client'
import { useHouseholdStore } from './household'
import type { LocalContext, PreparationSupport } from '../types/localContext'
import type { AsyncStatus } from '../types/async'

export const useLocalContextStore = defineStore('localContext', () => {
  const householdStore = useHouseholdStore()
  const address = ref('')
  const submittedAddress = ref('')

  const context = ref<LocalContext | null>(null)
  const contextStatus = ref<AsyncStatus>('idle')
  const contextError = ref<string | null>(null)
  const contextUnavailable = ref(false)

  const prepSupport = ref<PreparationSupport | null>(null)
  const prepStatus = ref<AsyncStatus>('idle')

  async function submitAddress(next: string) {
    address.value = next
    submittedAddress.value = next
    contextStatus.value = 'loading'
    contextError.value = null
    contextUnavailable.value = false
    try {
      const householdId = await householdStore.ensureHousehold()
      const resolved = await api.saveLocation(householdId, { address: next })
      address.value = resolved.address
      submittedAddress.value = resolved.address
      context.value = await api.getLocalContext(householdId)
      contextStatus.value = 'success'
      await loadPreparationSupport()
    } catch (err) {
      contextStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not reach the local context service.'
      contextUnavailable.value = err instanceof ApiError && err.status === 503
    }
  }

  async function loadPreparationSupport() {
    prepStatus.value = 'loading'
    try {
      const householdId = await householdStore.ensureHousehold()
      prepSupport.value = await api.getPreparationSupport(householdId)
      prepStatus.value = 'success'
    } catch {
      prepStatus.value = 'error'
    }
  }

  async function init() {
    contextStatus.value = 'loading'
    contextError.value = null
    contextUnavailable.value = false
    try {
      const householdId = await householdStore.ensureHousehold()
      context.value = await api.getLocalContext(householdId)
      address.value = context.value.location.address
      submittedAddress.value = context.value.location.address
      contextStatus.value = 'success'
      await loadPreparationSupport()
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        context.value = null
        contextStatus.value = 'idle'
        return
      }
      contextStatus.value = 'error'
      contextError.value =
        err instanceof Error ? err.message : 'Could not reach the local context service.'
      contextUnavailable.value = err instanceof ApiError && err.status === 503
    }
  }

  return {
    address,
    submittedAddress,
    context,
    contextStatus,
    contextError,
    contextUnavailable,
    prepSupport,
    prepStatus,
    submitAddress,
    loadPreparationSupport,
    init,
  }
})
