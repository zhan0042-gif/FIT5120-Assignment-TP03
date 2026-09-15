import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ApiError, api } from '../api/client.js'
import { useHouseholdStore } from './household.js'

export const useFireMapStore = defineStore('fireMap', () => {
  const householdStore = useHouseholdStore()

  const householdLocation = ref(null)
  const searchRadiusKm = ref(null)
  const totalCount = ref(0)
  const returnedCount = ref(0)
  const truncated = ref(false)
  const points = ref([])
  const mostRecentFire = ref(null)
  const nearestFire = ref(null)
  const approximateLocations = ref({})
  const locationLookups = new Map()

  const status = ref('idle')
  const error = ref(null)

  async function loadFirePoints() {
    status.value = 'loading'
    error.value = null
    try {
      const householdId = await householdStore.ensureHousehold()
      const data = await api.getHistoricalFirePoints(householdId)
      householdLocation.value = data.household_location
      searchRadiusKm.value = data.search_radius_km
      totalCount.value = data.total_count
      returnedCount.value = data.returned_count
      truncated.value = data.truncated
      points.value = data.points
      mostRecentFire.value = data.most_recent_fire ?? null
      nearestFire.value = data.nearest_fire ?? null
      status.value = 'success'
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        status.value = 'unverified'
        return
      }
      status.value = err instanceof ApiError && err.status === 503 ? 'unavailable' : 'error'
      error.value = err instanceof Error ? err.message : 'Could not load the historical fire map.'
    }
  }

  async function resolveApproximateLocation(point) {
    const key = `${point.latitude},${point.longitude}`
    if (Object.hasOwn(approximateLocations.value, key)) {
      return approximateLocations.value[key]
    }
    if (locationLookups.has(key)) return locationLookups.get(key)

    const lookup = (async () => {
      try {
        const candidates = await api.getNearbyAddresses(point.latitude, point.longitude)
        const first = candidates[0]
        const address = first?.canonical_address || first?.address || null
        approximateLocations.value = { ...approximateLocations.value, [key]: address }
        return address
      } catch {
        approximateLocations.value = { ...approximateLocations.value, [key]: null }
        return null
      } finally {
        locationLookups.delete(key)
      }
    })()

    locationLookups.set(key, lookup)
    return lookup
  }

  return {
    householdLocation,
    searchRadiusKm,
    totalCount,
    returnedCount,
    truncated,
    points,
    mostRecentFire,
    nearestFire,
    approximateLocations,
    status,
    error,
    loadFirePoints,
    resolveApproximateLocation,
  }
})
