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
  const nearbyAddresses = ref([])
  const reverseStatus = ref('idle')

  const context = ref(null)
  const contextStatus = ref('idle')
  const contextError = ref(null)
  const contextUnavailable = ref(false)

  const prepSupport = ref(null)
  const prepStatus = ref('idle')

  function canLoadContext(saved) {
    return (
      saved &&
      saved.latitude !== null &&
      saved.longitude !== null &&
      (saved.verification_status === 'verified' || saved.location_source === 'device_location')
    )
  }

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
      address.value = saved.canonical_address || saved.address
      submittedAddress.value = saved.canonical_address || saved.address
      saveStatus.value = 'success'
      if (canLoadContext(saved)) await loadContext()
      else contextStatus.value = 'unverified'
    } catch (err) {
      saveStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not save the household address.'
    }
  }

  async function submitDeviceLocation(latitude, longitude) {
    saveStatus.value = 'loading'
    contextStatus.value = 'idle'
    contextError.value = null
    contextUnavailable.value = false
    nearbyAddresses.value = []
    reverseStatus.value = 'idle'
    try {
      const householdId = await householdStore.ensureHousehold()
      const saved = await api.saveDeviceLocation(householdId, { latitude, longitude })
      location.value = saved
      address.value = ''
      submittedAddress.value = 'Current location'
      saveStatus.value = 'success'
      // Coordinate capture/save is complete at this point. Load provider-backed
      // context independently so the geolocation control cannot remain busy on it.
      void loadContext()
      reverseStatus.value = 'loading'
      try {
        nearbyAddresses.value = await api.getNearbyAddresses(latitude, longitude)
        reverseStatus.value = nearbyAddresses.value.length ? 'success' : 'empty'
      } catch {
        nearbyAddresses.value = []
        reverseStatus.value = 'unavailable'
      }
    } catch (err) {
      saveStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not save the current location.'
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
      const isDeviceLocation = location.value.location_source === 'device_location'
      address.value = isDeviceLocation
        ? ''
        : location.value.canonical_address || location.value.address
      submittedAddress.value = isDeviceLocation
        ? 'Current location'
        : location.value.canonical_address || location.value.address
      saveStatus.value = 'success'
      if (canLoadContext(location.value)) await loadContext()
      else contextStatus.value = 'unverified'
      if (isDeviceLocation) {
        reverseStatus.value = 'loading'
        try {
          nearbyAddresses.value = await api.getNearbyAddresses(
            location.value.latitude,
            location.value.longitude,
          )
          reverseStatus.value = nearbyAddresses.value.length ? 'success' : 'empty'
        } catch {
          reverseStatus.value = 'unavailable'
        }
      }
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
    nearbyAddresses,
    reverseStatus,
    context,
    contextStatus,
    contextError,
    contextUnavailable,
    prepSupport,
    prepStatus,
    submitAddress,
    submitDeviceLocation,
    loadContext,
    loadPreparationSupport,
    init,
  }
})
