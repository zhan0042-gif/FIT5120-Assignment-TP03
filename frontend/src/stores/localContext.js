import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { ApiError, api } from '../api/client.js'
import { useHouseholdStore } from './household.js'

// Local context includes dynamic BOM weather/FDR. Keep successful responses
// briefly across route changes, independently from the Backend's 24-hour
// static spatial cache.
export const DYNAMIC_DATA_MAX_AGE_MS = 5 * 60 * 1000

export function isDynamicDataFresh(loadedAt, now = Date.now()) {
  return Number.isFinite(loadedAt) && loadedAt <= now && now - loadedAt <= DYNAMIC_DATA_MAX_AGE_MS
}

export const useLocalContextStore = defineStore('localContext', () => {
  const householdStore = useHouseholdStore()
  const address = ref('')
  const submittedAddress = ref('')
  const location = ref(null)
  const locationStatus = ref('idle')
  const saveStatus = ref('idle')
  const nearbyAddresses = ref([])
  const reverseStatus = ref('idle')

  const context = ref(null)
  const contextStatus = ref('idle')
  const contextError = ref(null)
  const contextUnavailable = ref(false)
  const contextLoadedAt = ref(null)

  const prepSupport = ref(null)
  const prepStatus = ref('idle')
  const prepLoadedAt = ref(null)

  let initRequest = null
  let contextRequest = null
  let preparationRequest = null
  let saveRevision = 0
  let contextRevision = 0
  let preparationRevision = 0

  function canLoadContext(saved) {
    return (
      saved &&
      saved.latitude !== null &&
      saved.longitude !== null &&
      (saved.verification_status === 'verified' || saved.location_source === 'device_location')
    )
  }

  function invalidatePreparationSupport() {
    preparationRevision += 1
    preparationRequest = null
    prepSupport.value = null
    prepStatus.value = 'idle'
    prepLoadedAt.value = null
  }

  function invalidateDerivedLocationState() {
    contextRevision += 1
    contextRequest = null
    context.value = null
    contextStatus.value = 'idle'
    contextError.value = null
    contextUnavailable.value = false
    contextLoadedAt.value = null
    invalidatePreparationSupport()
  }

  function resetForHouseholdChange() {
    saveRevision += 1
    address.value = ''
    submittedAddress.value = ''
    location.value = null
    locationStatus.value = 'idle'
    saveStatus.value = 'idle'
    nearbyAddresses.value = []
    reverseStatus.value = 'idle'
    invalidateDerivedLocationState()
    initRequest = null
  }

  function setSavedLocation(saved) {
    location.value = saved
    locationStatus.value = 'success'
    const isDeviceLocation = saved.location_source === 'device_location'
    address.value = isDeviceLocation ? '' : saved.canonical_address || saved.address
    submittedAddress.value = isDeviceLocation
      ? 'Current location'
      : saved.canonical_address || saved.address
  }

  async function loadContext({ force = false } = {}) {
    if (!canLoadContext(location.value)) {
      context.value = null
      contextStatus.value = location.value ? 'unverified' : 'idle'
      contextLoadedAt.value = null
      invalidatePreparationSupport()
      return null
    }
    if (!force && contextStatus.value === 'success' && isDynamicDataFresh(contextLoadedAt.value)) {
      return context.value
    }
    if (contextRequest) return contextRequest

    const request = (async () => {
      const revision = contextRevision
      contextStatus.value = 'loading'
      contextError.value = null
      contextUnavailable.value = false
      let householdId = null
      try {
        householdId = await householdStore.ensureHousehold()
        const loaded = await api.getLocalContext(householdId)
        if (householdStore.householdId !== householdId || revision !== contextRevision) return null
        context.value = loaded
        contextStatus.value = 'success'
        contextLoadedAt.value = Date.now()
        return loaded
      } catch (err) {
        if (
          (householdId !== null && householdStore.householdId !== householdId) ||
          revision !== contextRevision
        ) return null
        context.value = null
        contextLoadedAt.value = null
        invalidatePreparationSupport()
        if (err instanceof ApiError && err.status === 409) {
          contextStatus.value = 'unverified'
          return null
        }
        contextStatus.value = 'error'
        contextError.value = err instanceof Error ? err.message : 'Local context is temporarily unavailable.'
        contextUnavailable.value = err instanceof ApiError && err.status === 503
        return null
      }
    })()
    contextRequest = request
    try {
      return await request
    } finally {
      if (contextRequest === request) contextRequest = null
    }
  }

  async function loadPreparationSupport({ force = false } = {}) {
    if (!canLoadContext(location.value) || contextStatus.value !== 'success') {
      invalidatePreparationSupport()
      return null
    }
    if (!force && prepStatus.value === 'success' && isDynamicDataFresh(prepLoadedAt.value)) {
      return prepSupport.value
    }
    if (preparationRequest) return preparationRequest

    const request = (async () => {
      const revision = preparationRevision
      prepStatus.value = 'loading'
      let householdId = null
      try {
        householdId = await householdStore.ensureHousehold()
        const loaded = await api.getPreparationSupport(householdId)
        if (
          householdStore.householdId !== householdId ||
          revision !== preparationRevision
        ) return null
        prepSupport.value = loaded
        prepStatus.value = 'success'
        prepLoadedAt.value = Date.now()
        return loaded
      } catch {
        if (
          (householdId !== null && householdStore.householdId !== householdId) ||
          revision !== preparationRevision
        ) return null
        prepSupport.value = null
        prepStatus.value = 'error'
        prepLoadedAt.value = null
        return null
      }
    })()
    preparationRequest = request
    try {
      return await request
    } finally {
      if (preparationRequest === request) preparationRequest = null
    }
  }

  // One rule owns dependent Overview data: usable location, successful
  // context, then Backend-authoritative preparation support.
  async function loadContextAndPreparation({ force = false } = {}) {
    await loadContext({ force })
    if (contextStatus.value === 'success') {
      await loadPreparationSupport({ force })
    }
  }

  async function submitAddress(next, selectedAddress = null, providerReference = null) {
    // Clear advice before starting the mutation so old-district guidance can
    // never be presented as current for the replacement address.
    const revision = ++saveRevision
    address.value = next
    submittedAddress.value = next
    saveStatus.value = 'loading'
    locationStatus.value = 'loading'
    invalidateDerivedLocationState()
    try {
      const householdId = await householdStore.ensureHousehold()
      const saved = await api.saveLocation(householdId, {
        address: next,
        selected_address: selectedAddress,
        provider_reference: providerReference,
      })
      if (householdStore.householdId !== householdId || revision !== saveRevision) return null
      setSavedLocation(saved)
      saveStatus.value = 'success'
      // PUT completion owns the save indicator. Spatial context, BOM/FDR, and
      // preparation support continue independently in their own loading states.
      if (canLoadContext(saved)) void loadContextAndPreparation({ force: true })
      else contextStatus.value = 'unverified'
      return saved
    } catch (err) {
      if (revision !== saveRevision) return null
      saveStatus.value = 'error'
      locationStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not save the household address.'
    }
  }

  async function submitDeviceLocation(latitude, longitude) {
    const revision = ++saveRevision
    saveStatus.value = 'loading'
    locationStatus.value = 'loading'
    invalidateDerivedLocationState()
    nearbyAddresses.value = []
    reverseStatus.value = 'idle'
    try {
      const householdId = await householdStore.ensureHousehold()
      const saved = await api.saveDeviceLocation(householdId, { latitude, longitude })
      if (householdStore.householdId !== householdId || revision !== saveRevision) return null
      setSavedLocation(saved)
      saveStatus.value = 'success'
      // Keep geolocation capture responsive while provider-backed context and
      // preparation load independently.
      void loadContextAndPreparation({ force: true })
      reverseStatus.value = 'loading'
      try {
        nearbyAddresses.value = await api.getNearbyAddresses(latitude, longitude)
        reverseStatus.value = nearbyAddresses.value.length ? 'success' : 'empty'
      } catch {
        if (revision !== saveRevision) return null
        nearbyAddresses.value = []
        reverseStatus.value = 'unavailable'
      }
      return saved
    } catch (err) {
      if (revision !== saveRevision) return null
      saveStatus.value = 'error'
      locationStatus.value = 'error'
      contextError.value = err instanceof Error ? err.message : 'Could not save the current location.'
    }
  }

  async function init() {
    if (initRequest) return initRequest
    const request = (async () => {
      locationStatus.value = 'loading'
      let householdId = null
      try {
        householdId = await householdStore.ensureHousehold()
        const saved = await api.getLocation(householdId)
        if (householdStore.householdId !== householdId) return
        setSavedLocation(saved)
        if (canLoadContext(saved)) await loadContextAndPreparation()
        else {
          context.value = null
          contextStatus.value = 'unverified'
          contextLoadedAt.value = null
          invalidatePreparationSupport()
        }
        if (saved.location_source === 'device_location') {
          reverseStatus.value = 'loading'
          try {
            nearbyAddresses.value = await api.getNearbyAddresses(saved.latitude, saved.longitude)
            reverseStatus.value = nearbyAddresses.value.length ? 'success' : 'empty'
          } catch {
            reverseStatus.value = 'unavailable'
          }
        }
      } catch (err) {
        if (householdId !== null && householdStore.householdId !== householdId) return
        if (err instanceof ApiError && err.status === 404) {
          location.value = null
          locationStatus.value = 'empty'
          address.value = ''
          submittedAddress.value = ''
          invalidateDerivedLocationState()
          return
        }
        locationStatus.value = 'error'
        invalidateDerivedLocationState()
        contextStatus.value = 'error'
        contextError.value =
          err instanceof Error ? err.message : 'Could not reach the local context service.'
        contextUnavailable.value = err instanceof ApiError && err.status === 503
      }
    })()
    initRequest = request
    try {
      return await request
    } finally {
      if (initRequest === request) initRequest = null
    }
  }

  watch(
    () => householdStore.householdId,
    (next, previous) => {
      if (next !== previous) resetForHouseholdChange()
    },
    { flush: 'sync' },
  )

  watch(
    () => householdStore.planRevision,
    (next, previous) => {
      if (next !== previous) invalidatePreparationSupport()
    },
    { flush: 'sync' },
  )

  return {
    address,
    submittedAddress,
    location,
    locationStatus,
    saveStatus,
    nearbyAddresses,
    reverseStatus,
    context,
    contextStatus,
    contextError,
    contextUnavailable,
    contextLoadedAt,
    prepSupport,
    prepStatus,
    prepLoadedAt,
    canLoadContext,
    invalidatePreparationSupport,
    resetForHouseholdChange,
    submitAddress,
    submitDeviceLocation,
    loadContext,
    loadPreparationSupport,
    loadContextAndPreparation,
    init,
  }
})
