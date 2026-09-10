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
const {
  DYNAMIC_DATA_MAX_AGE_MS,
  isDynamicDataFresh,
  useLocalContextStore,
} = await import('../src/stores/localContext.js')

const originalApi = { ...api }
const verifiedLocation = {
  address: '84 WATTLE TRACK WARRANDYTE VIC 3113',
  canonical_address: '84 WATTLE TRACK WARRANDYTE VIC 3113',
  latitude: -37.738,
  longitude: 145.223,
  verification_status: 'verified',
  location_source: 'address',
}
const contextResponse = {
  bushfire_context: { is_bushfire_prone_area: true, fire_district: 'Central' },
  environmental_context: { fire_history_summary: null },
  fire_danger: { availability: 'available' },
  weather: null,
}
const preparationResponse = {
  status: 'review_recommended',
  message: 'Review the plan.',
  sections_to_review: ['transport'],
}

function createStores() {
  localStorage.setItem('firebreak.household-id.v1', 'hh_test')
  setActivePinia(createPinia())
  const householdStore = useHouseholdStore()
  const localContextStore = useLocalContextStore()
  return { householdStore, localContextStore }
}

function stubSuccessfulOverview() {
  const calls = { location: 0, context: 0, preparation: 0 }
  api.getLocation = async () => {
    calls.location += 1
    return { ...verifiedLocation }
  }
  api.getLocalContext = async () => {
    calls.context += 1
    return contextResponse
  }
  api.getPreparationSupport = async () => {
    calls.preparation += 1
    return preparationResponse
  }
  return calls
}

afterEach(() => {
  Object.assign(api, originalApi)
  localStorage.clear()
})

test('five-minute freshness includes the exact boundary and rejects stale/future values', () => {
  const now = 1_000_000
  assert.equal(isDynamicDataFresh(now - DYNAMIC_DATA_MAX_AGE_MS, now), true)
  assert.equal(isDynamicDataFresh(now - DYNAMIC_DATA_MAX_AGE_MS - 1, now), false)
  assert.equal(isDynamicDataFresh(now + 1, now), false)
  assert.equal(isDynamicDataFresh(null, now), false)
})

test('missing location does not request context or preparation', async () => {
  const { localContextStore } = createStores()
  let contextCalls = 0
  let preparationCalls = 0
  api.getLocation = async () => {
    throw new ApiError(404, 'Household location was not found.')
  }
  api.getLocalContext = async () => { contextCalls += 1 }
  api.getPreparationSupport = async () => { preparationCalls += 1 }

  await localContextStore.init()

  assert.equal(localContextStore.locationStatus, 'empty')
  assert.equal(localContextStore.contextStatus, 'idle')
  assert.equal(localContextStore.prepStatus, 'idle')
  assert.equal(contextCalls, 0)
  assert.equal(preparationCalls, 0)
})

test('unverified location does not request context or preparation', async () => {
  const { localContextStore } = createStores()
  let contextCalls = 0
  let preparationCalls = 0
  api.getLocation = async () => ({
    address: 'Unverified address',
    latitude: null,
    longitude: null,
    verification_status: 'unverified',
    location_source: 'address',
  })
  api.getLocalContext = async () => { contextCalls += 1 }
  api.getPreparationSupport = async () => { preparationCalls += 1 }

  await localContextStore.init()

  assert.equal(localContextStore.contextStatus, 'unverified')
  assert.equal(localContextStore.prepStatus, 'idle')
  assert.equal(contextCalls, 0)
  assert.equal(preparationCalls, 0)
})

test('fresh re-entry reuses dynamic responses and stale re-entry refreshes both', async () => {
  const { localContextStore } = createStores()
  const calls = stubSuccessfulOverview()

  await localContextStore.init()
  await localContextStore.init()
  assert.deepEqual(calls, { location: 2, context: 1, preparation: 1 })

  localContextStore.contextLoadedAt = Date.now() - DYNAMIC_DATA_MAX_AGE_MS - 1
  localContextStore.prepLoadedAt = Date.now() - DYNAMIC_DATA_MAX_AGE_MS - 1
  await localContextStore.init()
  assert.deepEqual(calls, { location: 3, context: 2, preparation: 2 })
})

test('a context error retries on re-entry and preparation waits for success', async () => {
  const { localContextStore } = createStores()
  let contextCalls = 0
  let preparationCalls = 0
  api.getLocation = async () => ({ ...verifiedLocation })
  api.getLocalContext = async () => {
    contextCalls += 1
    if (contextCalls === 1) throw new Error('network unavailable')
    return contextResponse
  }
  api.getPreparationSupport = async () => {
    preparationCalls += 1
    return preparationResponse
  }

  await localContextStore.init()
  assert.equal(localContextStore.contextStatus, 'error')
  assert.equal(preparationCalls, 0)

  await localContextStore.init()
  assert.equal(localContextStore.contextStatus, 'success')
  assert.equal(localContextStore.prepStatus, 'success')
  assert.equal(contextCalls, 2)
  assert.equal(preparationCalls, 1)
})

test('household creation failure becomes a retryable store error', async () => {
  const { householdStore, localContextStore } = createStores()
  householdStore.householdId = null
  api.createHousehold = async () => {
    throw new Error('network unavailable')
  }

  await assert.doesNotReject(localContextStore.init())

  assert.equal(localContextStore.locationStatus, 'error')
  assert.equal(localContextStore.contextStatus, 'error')
  assert.equal(localContextStore.prepStatus, 'idle')
})

test('concurrent context and preparation calls share their in-flight requests', async () => {
  const { localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  let resolveContext
  let contextCalls = 0
  api.getLocalContext = () => {
    contextCalls += 1
    return new Promise((resolve) => { resolveContext = resolve })
  }

  const firstContext = localContextStore.loadContext({ force: true })
  const secondContext = localContextStore.loadContext({ force: true })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(contextCalls, 1)
  resolveContext(contextResponse)
  await Promise.all([firstContext, secondContext])

  let resolvePreparation
  let preparationCalls = 0
  api.getPreparationSupport = () => {
    preparationCalls += 1
    return new Promise((resolve) => { resolvePreparation = resolve })
  }
  const firstPreparation = localContextStore.loadPreparationSupport({ force: true })
  const secondPreparation = localContextStore.loadPreparationSupport({ force: true })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(preparationCalls, 1)
  resolvePreparation(preparationResponse)
  await Promise.all([firstPreparation, secondPreparation])
})

test('location mutation clears old preparation before the save completes', async () => {
  const { localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  localContextStore.context = contextResponse
  localContextStore.contextStatus = 'success'
  localContextStore.prepSupport = preparationResponse
  localContextStore.prepStatus = 'success'
  let resolveSave
  api.saveLocation = () => new Promise((resolve) => { resolveSave = resolve })
  api.getLocalContext = async () => contextResponse
  api.getPreparationSupport = async () => preparationResponse

  const saving = localContextStore.submitAddress('12 HIGH STREET WARBURTON VIC 3799')
  assert.equal(localContextStore.context, null)
  assert.equal(localContextStore.prepSupport, null)
  assert.equal(localContextStore.prepStatus, 'idle')
  await new Promise((resolve) => setImmediate(resolve))
  resolveSave({ ...verifiedLocation, address: '12 HIGH STREET WARBURTON VIC 3799' })
  await saving
  assert.equal(localContextStore.prepStatus, 'success')
})

test('device-location mutation also clears old preparation immediately', async () => {
  const { localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  localContextStore.context = contextResponse
  localContextStore.contextStatus = 'success'
  localContextStore.prepSupport = preparationResponse
  localContextStore.prepStatus = 'success'
  let resolveSave
  api.saveDeviceLocation = () => new Promise((resolve) => { resolveSave = resolve })
  api.getLocalContext = async () => contextResponse
  api.getPreparationSupport = async () => preparationResponse
  api.getNearbyAddresses = async () => []

  const saving = localContextStore.submitDeviceLocation(-37.8, 144.9)
  assert.equal(localContextStore.context, null)
  assert.equal(localContextStore.prepSupport, null)
  assert.equal(localContextStore.prepStatus, 'idle')
  await new Promise((resolve) => setImmediate(resolve))
  resolveSave({
    ...verifiedLocation,
    address: '',
    canonical_address: null,
    latitude: -37.8,
    longitude: 144.9,
    location_source: 'device_location',
    verification_status: 'unverified',
  })
  await saving
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(localContextStore.prepStatus, 'success')
})

test('successful plan save invalidates old preparation', async () => {
  const { householdStore, localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  localContextStore.context = contextResponse
  localContextStore.contextStatus = 'success'
  localContextStore.contextLoadedAt = Date.now()
  localContextStore.prepSupport = preparationResponse
  localContextStore.prepStatus = 'success'
  localContextStore.prepLoadedAt = Date.now()
  let preparationCalls = 0
  api.saveHouseholdPlan = async (_householdId, plan) => plan
  api.getCompletion = async () => ({ overall_status: 'complete', sections: [] })
  api.getLocation = async () => ({ ...verifiedLocation })
  api.getPreparationSupport = async () => {
    preparationCalls += 1
    return { ...preparationResponse, sections_to_review: [] }
  }

  await householdStore.savePlan({ members: [] })

  assert.equal(localContextStore.prepSupport, null)
  assert.equal(localContextStore.prepStatus, 'idle')
  assert.equal(localContextStore.prepLoadedAt, null)

  await localContextStore.init()
  assert.equal(preparationCalls, 1)
  assert.equal(localContextStore.prepStatus, 'success')
  assert.deepEqual(localContextStore.prepSupport.sections_to_review, [])
})

test('plan invalidation prevents an older in-flight preparation response from returning', async () => {
  const { householdStore, localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  localContextStore.context = contextResponse
  localContextStore.contextStatus = 'success'
  let resolvePreparation
  api.getPreparationSupport = () => new Promise((resolve) => { resolvePreparation = resolve })

  const loading = localContextStore.loadPreparationSupport({ force: true })
  await new Promise((resolve) => setImmediate(resolve))
  householdStore.planRevision += 1
  resolvePreparation(preparationResponse)
  await loading

  assert.equal(localContextStore.prepSupport, null)
  assert.equal(localContextStore.prepStatus, 'idle')
})

test('location mutation prevents an older in-flight context response from returning', async () => {
  const { localContextStore } = createStores()
  localContextStore.location = { ...verifiedLocation }
  const replacementContext = {
    ...contextResponse,
    bushfire_context: { is_bushfire_prone_area: false, fire_district: 'East Gippsland' },
  }
  let resolveOldContext
  let contextCalls = 0
  api.getLocalContext = () => {
    contextCalls += 1
    if (contextCalls === 1) {
      return new Promise((resolve) => { resolveOldContext = resolve })
    }
    return Promise.resolve(replacementContext)
  }
  api.saveLocation = async () => ({
    ...verifiedLocation,
    address: '12 HIGH STREET WARBURTON VIC 3799',
    canonical_address: '12 HIGH STREET WARBURTON VIC 3799',
  })
  api.getPreparationSupport = async () => preparationResponse

  const oldLoading = localContextStore.loadContext({ force: true })
  await new Promise((resolve) => setImmediate(resolve))
  await localContextStore.submitAddress('12 HIGH STREET WARBURTON VIC 3799')
  resolveOldContext(contextResponse)
  await oldLoading

  assert.equal(contextCalls, 2)
  assert.equal(localContextStore.context.bushfire_context.fire_district, 'East Gippsland')
})

test('household replacement resets all household-bound local state', () => {
  const { householdStore, localContextStore } = createStores()
  localContextStore.address = 'Old address'
  localContextStore.location = { ...verifiedLocation }
  localContextStore.context = contextResponse
  localContextStore.contextStatus = 'success'
  localContextStore.contextLoadedAt = Date.now()
  localContextStore.prepSupport = preparationResponse
  localContextStore.prepStatus = 'success'
  localContextStore.prepLoadedAt = Date.now()

  householdStore.householdId = 'hh_replacement'

  assert.equal(localContextStore.address, '')
  assert.equal(localContextStore.location, null)
  assert.equal(localContextStore.context, null)
  assert.equal(localContextStore.contextStatus, 'idle')
  assert.equal(localContextStore.contextLoadedAt, null)
  assert.equal(localContextStore.prepSupport, null)
  assert.equal(localContextStore.prepStatus, 'idle')
  assert.equal(localContextStore.prepLoadedAt, null)
})
