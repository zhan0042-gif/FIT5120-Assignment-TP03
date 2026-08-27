import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, loadSavedAddress } from '../api/client'
import type { LocalContext, PreparationSupport } from '../types/localContext'
import type { AsyncStatus } from '../types/async'

export const useLocalContextStore = defineStore('localContext', () => {
  const address = ref(loadSavedAddress())
  const submittedAddress = ref(address.value)

  const context = ref<LocalContext | null>(null)
  // 'success' + context === null means "data unavailable" (AC4, US2.1), distinct from 'error'.
  const contextStatus = ref<AsyncStatus>('idle')
  const contextError = ref<string | null>(null)

  const prepSupport = ref<PreparationSupport | null>(null)
  const prepStatus = ref<AsyncStatus>('idle')

  async function submitAddress(next: string) {
    address.value = next
    submittedAddress.value = next
    contextStatus.value = 'loading'
    contextError.value = null
    try {
      await api.saveLocation(next)
      context.value = await api.getLocalContext(next)
      contextStatus.value = 'success'
      await loadPreparationSupport()
    } catch (err) {
      contextStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not reach the local context service.'
    }
  }

  async function loadPreparationSupport() {
    prepStatus.value = 'loading'
    try {
      prepSupport.value = await api.getPreparationSupport()
      prepStatus.value = 'success'
    } catch {
      prepStatus.value = 'error'
    }
  }

  async function init() {
    if (submittedAddress.value) {
      await submitAddress(submittedAddress.value)
    }
  }

  return {
    address,
    submittedAddress,
    context,
    contextStatus,
    contextError,
    prepSupport,
    prepStatus,
    submitAddress,
    loadPreparationSupport,
    init,
  }
})
