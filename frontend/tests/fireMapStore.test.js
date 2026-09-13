import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  getItem(key) {
    return this.values.get(key) ?? null
  }

  setItem(key, value) {
    this.values.set(key, String(value))
  }

  removeItem(key) {
    this.values.delete(key)
  }

  clear() {
    this.values.clear()
  }
}

globalThis.localStorage = new MemoryStorage()

const { createPinia, setActivePinia } = await import('pinia')
const { ApiError, api } = await import('../src/api/client.js')
const { useHouseholdStore } = await import('../src/stores/household.js')
const { useFireMapStore } = await import('../src/stores/fireMap.js')

const originalApi = { ...api }
const successResponse = {
  household_location: { latitude: -37.738, longitude: 145.223 },
  search_radius_km: 20,
  total_count: 2,
  returned_count: 2,
  truncated: false,
  points: [
    { latitude: -37.71, longitude: 145.19, season: 2020, start_date: '2020-01-15' },
    { latitude: -37.72, longitude: 145.2, season: null, start_date: null },
  ],
}

function createStore() {
  localStorage.setItem('firebreak.household-id.v1', 'hh_test')
  setActivePinia(createPinia())
  useHouseholdStore()
  return useFireMapStore()
}

afterEach(() => {
  Object.assign(api, originalApi)
  localStorage.clear()
})

test('successful load stores every field from the response', async () => {
  const fireMapStore = createStore()
  api.getHistoricalFirePoints = async () => successResponse

  await fireMapStore.loadFirePoints()

  assert.equal(fireMapStore.status, 'success')
  assert.deepEqual(fireMapStore.householdLocation, successResponse.household_location)
  assert.equal(fireMapStore.searchRadiusKm, 20)
  assert.equal(fireMapStore.totalCount, 2)
  assert.equal(fireMapStore.returnedCount, 2)
  assert.equal(fireMapStore.truncated, false)
  assert.equal(fireMapStore.points.length, 2)
})

test('an unverified address (409) is a distinct status, not an error', async () => {
  const fireMapStore = createStore()
  api.getHistoricalFirePoints = async () => {
    throw new ApiError(409, 'Household location has not been verified.')
  }

  await fireMapStore.loadFirePoints()

  assert.equal(fireMapStore.status, 'unverified')
  assert.equal(fireMapStore.error, null)
})

test('an upstream data outage (503) is a distinct status, not a generic error', async () => {
  const fireMapStore = createStore()
  api.getHistoricalFirePoints = async () => {
    throw new ApiError(503, 'Historical fire map data is unavailable.')
  }

  await fireMapStore.loadFirePoints()

  assert.equal(fireMapStore.status, 'unavailable')
  assert.equal(fireMapStore.error, 'Historical fire map data is unavailable.')
})

test('any other failure falls back to a generic error state', async () => {
  const fireMapStore = createStore()
  api.getHistoricalFirePoints = async () => {
    throw new ApiError(500, 'Something went wrong.')
  }

  await fireMapStore.loadFirePoints()

  assert.equal(fireMapStore.status, 'error')
  assert.equal(fireMapStore.error, 'Something went wrong.')
})
