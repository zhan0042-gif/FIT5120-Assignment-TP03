import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
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
  household_location: {
    latitude: -37.738,
    longitude: 145.223,
    address: '84 Yarra Street, Warrandyte VIC 3113',
  },
  search_radius_km: 20,
  total_count: 2,
  returned_count: 2,
  truncated: false,
  most_recent_fire: {
    latitude: -37.71,
    longitude: 145.19,
    season: 2020,
    start_date: '2020-01-15',
  },
  nearest_fire: {
    latitude: -37.72,
    longitude: 145.2,
    season: null,
    start_date: null,
    distance_km: 1.25,
  },
  points: [
    { latitude: -37.71, longitude: 145.19, season: 2020, start_date: '2020-01-15', distance_km: 4.5 },
    { latitude: -37.72, longitude: 145.2, season: null, start_date: null, distance_km: 1.25 },
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
  assert.deepEqual(fireMapStore.mostRecentFire, successResponse.most_recent_fire)
  assert.deepEqual(fireMapStore.nearestFire, successResponse.nearest_fire)
})

test('an older response without insight fields remains compatible', async () => {
  const fireMapStore = createStore()
  api.getHistoricalFirePoints = async () => ({
    ...successResponse,
    most_recent_fire: undefined,
    nearest_fire: undefined,
  })

  await fireMapStore.loadFirePoints()

  assert.equal(fireMapStore.status, 'success')
  assert.equal(fireMapStore.mostRecentFire, null)
  assert.equal(fireMapStore.nearestFire, null)
})

test('the map page uses distinct icons, a radius-aware viewport and concise insights', async () => {
  const mapSource = await readFile(
    new URL('../src/components/fireMap/HistoricalFireMap.vue', import.meta.url),
    'utf8',
  )
  const viewSource = await readFile(new URL('../src/views/MapView.vue', import.meta.url), 'utf8')

  assert.match(mapSource, /const houseIcon = L\.divIcon/)
  assert.match(mapSource, /const fireIcon = L\.divIcon/)
  assert.match(mapSource, /L\.latLng\(householdLatLng\)\.toBounds\(props\.searchRadiusKm \* 2000\)/)
  assert.doesNotMatch(mapSource, /searchArea\.getBounds\(\)/)
  assert.match(mapSource, /map\.invalidateSize\(\)/)
  assert.match(mapSource, /mix-blend-mode: normal/)
  assert.match(mapSource, /householdLocation\.address/)
  assert.match(mapSource, /Historical fire/)
  assert.match(mapSource, /Recorded date unavailable/)
  assert.match(mapSource, /Distance from your home/)
  assert.match(mapSource, /marker\.on\('popupopen'/)
  assert.match(mapSource, /defineExpose\(\{ focusPoint \}\)/)
  assert.match(mapSource, /map\.panTo\(marker\.getLatLng\(\)\)/)
  assert.match(mapSource, /marker\.openPopup\(\)/)
  assert.doesNotMatch(mapSource, /Season/)
  assert.match(mapSource, /Map legend/)
  assert.match(viewSource, /Nearest historical fire/)
  assert.match(viewSource, /Most recent historical fire/)
  assert.match(viewSource, /See past bushfire records near your home\./)
  assert.match(viewSource, /grid-template-columns: minmax\(0, 3fr\) minmax\(0, 2fr\)/)
  assert.match(viewSource, /class="card insight-card"/)
  assert.match(viewSource, /Recorded: \$\{recordedDate\(store\.nearestFire\)\}/)
  assert.match(viewSource, /distanceFromHome\(store\.mostRecentFire\)/)
  assert.match(viewSource, /Approximate location:/)
  assert.match(viewSource, /historical fire \$\{noun\} within \$\{radius\} km/)
  assert.match(viewSource, /@click="focusFire\(store\.nearestFire\)"/)
  assert.match(viewSource, /@click="focusFire\(store\.mostRecentFire\)"/)
  assert.doesNotMatch(viewSource, /Season/)
  assert.doesNotMatch(viewSource, /Showing \{\{/)
})

test('approximate fire location is lazy and cached by coordinate', async () => {
  const fireMapStore = createStore()
  let reverseCalls = 0
  api.getHistoricalFirePoints = async () => successResponse
  api.getNearbyAddresses = async () => {
    reverseCalls += 1
    return [{ address: 'Near Beach Road, Mordialloc VIC 3195' }]
  }

  await fireMapStore.loadFirePoints()
  assert.equal(reverseCalls, 0)

  const first = await fireMapStore.resolveApproximateLocation(successResponse.points[0])
  const second = await fireMapStore.resolveApproximateLocation(successResponse.points[0])

  assert.equal(first, 'Near Beach Road, Mordialloc VIC 3195')
  assert.equal(second, first)
  assert.equal(reverseCalls, 1)
})

test('reverse lookup failure is contained and cached as unavailable', async () => {
  const fireMapStore = createStore()
  let reverseCalls = 0
  api.getNearbyAddresses = async () => {
    reverseCalls += 1
    throw new ApiError(503, 'Nearby address lookup is unavailable.')
  }

  const first = await fireMapStore.resolveApproximateLocation(successResponse.points[1])
  const second = await fireMapStore.resolveApproximateLocation(successResponse.points[1])

  assert.equal(first, null)
  assert.equal(second, null)
  assert.equal(reverseCalls, 1)
})

test('matching featured-fire coordinates share one in-flight reverse lookup', async () => {
  const fireMapStore = createStore()
  let reverseCalls = 0
  let finishLookup
  api.getNearbyAddresses = () => {
    reverseCalls += 1
    return new Promise((resolve) => { finishLookup = resolve })
  }

  const point = successResponse.points[0]
  const nearestLookup = fireMapStore.resolveApproximateLocation(point)
  const recentLookup = fireMapStore.resolveApproximateLocation({ ...point })
  assert.equal(reverseCalls, 1)

  finishLookup([{ address: 'Wantirna South VIC' }])
  assert.deepEqual(await Promise.all([nearestLookup, recentLookup]), [
    'Wantirna South VIC',
    'Wantirna South VIC',
  ])
})

test('the six main routes still map to their intended views', async () => {
  const routerSource = await readFile(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const mappings = [
    ['/', 'WelcomeView.vue'],
    ['/plan', 'PlanBuilderView.vue'],
    ['/overview', 'OverviewView.vue'],
    ['/map', 'MapView.vue'],
    ['/scenarios', 'ScenarioTesterView.vue'],
    ['/summary', 'PreparednessSummaryView.vue'],
  ]

  for (const [path, view] of mappings) {
    assert.match(
      routerSource,
      new RegExp(`path: '${path.replace('/', '\\/')}'[\\s\\S]*?component: \\(\\) => import\\('\\.\\./views/${view.replace('.', '\\.')}\\'\\)`),
    )
  }
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
