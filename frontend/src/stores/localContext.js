import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ApiError, api } from '../api/client'
import { useHouseholdStore } from './household'

export const useLocalContextStore = defineStore('localContext', () => {
  // Address persistence, static context, live conditions, and preparation
  // advice have separate states so one unavailable source does not erase others.
  const householdStore = useHouseholdStore()
  const address = ref('')
  const submittedAddress = ref('')
  const location = ref(null)
  const saveStatus = ref('idle')

  const context = ref(null)
  const contextStatus = ref('idle')
  const contextError = ref(null)
  const contextUnavailable = ref(false)

  const prepSupport = ref(null)
  const prepStatus = ref('idle')

  async function submitAddress(next, selectedAddress = null) {
    // Free text remains saveable. `selectedAddress` only records that the user
    // deliberately chose an official autocomplete candidate for verification.
    address.value = next
    submittedAddress.value = next
    saveStatus.value = 'loading'
    contextStatus.value = 'idle'
    contextError.value = null
    contextUnavailable.value = false
    try {
      const householdId = await householdStore.ensureHousehold()
      const saved = await api.saveLocation(householdId, {
        address: next,
        selected_address: selectedAddress,
      })
      location.value = saved
      address.value = saved.address
      submittedAddress.value = saved.address
      saveStatus.value = 'success'
      if (saved.verification_status === 'verified') await loadContext()
      else contextStatus.value = 'unverified'
    } catch (err) {
      saveStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not save the household address.'
    }
  }

  async function loadContext() {
    contextStatus.value = 'loading'
    contextError.value = null
    contextUnavailable.value = false
    try {
      const householdId = await householdStore.ensureHousehold()
      context.value = await api.getLocalContext(householdId)
      contextStatus.value = 'success'
      // Preparation advice depends on FDR and saved-plan completion, but is kept
      // as a separate response because local weather/context can still display.
      await loadPreparationSupport()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        contextStatus.value = 'unverified'
        return
      }
      contextStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Local context is temporarily unavailable.'
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
    try {
      const householdId = await householdStore.ensureHousehold()
      location.value = await api.getLocation(householdId)
      address.value = location.value.address
      submittedAddress.value = location.value.address
      saveStatus.value = 'success'
      if (location.value.verification_status === 'verified') await loadContext()
      else contextStatus.value = 'unverified'
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
    location,
    saveStatus,
    context,
    contextStatus,
    contextError,
    contextUnavailable,
    prepSupport,
    prepStatus,
    submitAddress,
    loadContext,
    loadPreparationSupport,
    init,
  }
})
