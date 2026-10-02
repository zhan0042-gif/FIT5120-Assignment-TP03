import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { afterEach, test } from 'node:test'

class MemoryStorage {
  constructor() { this.values = new Map() }
  getItem(key) { return this.values.get(key) ?? null }
  setItem(key, value) { this.values.set(key, String(value)) }
  removeItem(key) { this.values.delete(key) }
  clear() { this.values.clear() }
}

globalThis.localStorage = new MemoryStorage()

const { createPinia, setActivePinia } = await import('pinia')
const { api } = await import('../src/api/client.js')
const { useHouseholdStore } = await import('../src/stores/household.js')

const originalApi = { ...api }
const originalFetch = globalThis.fetch
const overviewSource = await readFile(new URL('../src/views/OverviewView.vue', import.meta.url), 'utf8')
const styleSource = await readFile(new URL('../src/style.css', import.meta.url), 'utf8')
const localContextSource = await readFile(
  new URL('../src/components/localContext/LocalContextCard.vue', import.meta.url),
  'utf8',
)
const mapSource = await readFile(new URL('../src/views/MapView.vue', import.meta.url), 'utf8')
const completionSource = await readFile(
  new URL('../src/components/completion/CompletionOverview.vue', import.meta.url),
  'utf8',
)
const layoutSource = await readFile(
  new URL('../src/components/layout/AppLayout.vue', import.meta.url),
  'utf8',
)
const routerSource = await readFile(new URL('../src/router/index.js', import.meta.url), 'utf8')

afterEach(() => {
  Object.assign(api, originalApi)
  globalThis.fetch = originalFetch
  localStorage.clear()
})

test('overview loads the latest saved plan through the existing store', async () => {
  localStorage.setItem('firebreak.household-id.v1', 'hh_overview')
  setActivePinia(createPinia())
  const store = useHouseholdStore()
  const savedPlan = {
    members: [{
      member_id: 'm_1',
      display_name: 'Maya',
      relationship: 'self',
      usual_location: { kind: 'work', address: '1 Treasury Place, East Melbourne VIC 3002' },
    }],
    animals: [],
    transports: [],
    arrangements: { backup_arrangements: [] },
    responsibilities: [],
  }
  api.getHouseholdPlan = async (householdId) => {
    assert.equal(householdId, 'hh_overview')
    return savedPlan
  }
  api.getCompletion = async () => ({ overall_status: 'needs_information', sections: [], immediate_checks: [] })

  await store.loadPlan()

  assert.deepEqual(store.plan, savedPlan)
  assert.equal(store.planStatus, 'success')
})

test('overview contains only the concise saved-plan summary', () => {
  assert.match(
    overviewSource,
    /<CompletionOverview[\s\S]*?<div class="right-stack">[\s\S]*?<PreparationSupportBanner \/>/,
  )
  assert.doesNotMatch(overviewSource, /LocalContextCard/)
  assert.equal((mapSource.match(/<LocalContextCard \/>/g) ?? []).length, 1)
  assert.match(localContextSource, /Household address/)
  assert.match(localContextSource, /Edit address/)
  assert.match(localContextSource, /AddressAutocompleteInput/)
  assert.match(completionSource, /Edit my plan/)
  assert.match(overviewSource, /Export preparedness plan/)
  const overviewTemplate = overviewSource.slice(overviewSource.indexOf('<template>'), overviewSource.lastIndexOf('</template>'))
  assert.ok(overviewTemplate.indexOf('class="page-actions"') > overviewTemplate.indexOf('<h3>Responsibilities</h3>'))
  assert.match(overviewSource, /:disabled="noSavedPlan \|\| exportStatus === 'loading'" @click="exportPdf"/)
  assert.match(overviewSource, /\.page-actions \{[^}]*justify-content: flex-end/)

  assert.match(overviewSource, /Household Plan Summary/)
  assert.match(overviewSource, /<th>Name<\/th><th>Daytime location<\/th><th>Daytime address<\/th>/)
  assert.match(overviewSource, /usual_location\.kind === 'home'/)
  assert.match(overviewSource, /location\?\.canonical_address \|\| location\?\.address/)
  assert.match(overviewSource, /<h3>Key Locations<\/h3>/)
  assert.match(overviewSource, /<h3>Responsibilities<\/h3>/)
  const keyLocationsSource = overviewSource.match(/const keyLocations = computed[\s\S]*?const acceptedAdvice/)?.[0] ?? ''
  assert.doesNotMatch(keyLocationsSource, /label: 'Home'/)
  assert.doesNotMatch(keyLocationsSource, /usual_location/)
  assert.match(keyLocationsSource, /Primary destination/)
  assert.match(keyLocationsSource, /Backup destination/)
  assert.match(keyLocationsSource, /Meeting point/)
  assert.doesNotMatch(overviewSource, /Animals \/ pets/)
  assert.doesNotMatch(overviewSource, /<h2>Transport<\/h2>/)
  assert.doesNotMatch(overviewSource, /Bushfire-prone area/)
  assert.doesNotMatch(overviewSource, /CFA Fire District/)
  assert.doesNotMatch(overviewSource, /Current conditions/)
  assert.doesNotMatch(overviewSource, /Fire Danger Rating/)
  assert.doesNotMatch(overviewSource, /Historical fire activity/)
  for (const [token, colour] of [
    ['row', '#f6f1e8'],
    ['heading', '#ede4d8'],
    ['text', '#241f1b'],
    ['muted', '#5f554d'],
    ['border', '#d8ccbe'],
  ]) {
    assert.match(overviewSource, new RegExp(`var\\(--color-summary-${token}\\)`))
    assert.match(styleSource, new RegExp(`--color-summary-${token}: ${colour};`))
  }
})

test('PDF request keeps GET without advice and posts accepted advice when present', async () => {
  const expected = new Blob(['%PDF-test'], { type: 'application/pdf' })
  const requests = []
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init })
    return new Response(expected, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="firebreak-household-plan.pdf"',
      },
    })
  }

  await api.getPreparednessPlanPdf('hh_overview')
  await api.getPreparednessPlanPdf('hh_overview', 'Maya arrives last. Review the pickup plan.')

  assert.equal(requests[0].url, '/api/v1/households/hh_overview/preparedness-plan.pdf')
  assert.equal(requests[0].init, undefined)
  assert.equal(requests[1].init.method, 'POST')
  assert.equal(requests[1].init.headers.get('Content-Type'), 'application/json')
  assert.equal(requests[1].init.body, JSON.stringify({
    preparedness_advice: 'Maya arrives last. Review the pickup plan.',
  }))
})

test('navigation consolidates summary into Overview and labels the map Fire Map', () => {
  assert.doesNotMatch(layoutSource, /Summary &amp; Export/)
  assert.match(layoutSource, /<router-link to="\/map">Fire Map<\/router-link>/)
  assert.match(routerSource, /path: '\/summary',[\s\S]*?redirect: '\/overview'/)
})

test('fire map aligns address and 2 by 2 metrics with the historical map columns', () => {
  assert.doesNotMatch(localContextSource, /Historical fire activity/)
  assert.doesNotMatch(localContextSource, /fireHistoryRows/)
  assert.match(mapSource, /class="conditions-layout"[\s\S]*?<LocalContextCard \/>[\s\S]*?class="conditions-grid"/)
  assert.doesNotMatch(mapSource, /<h2 class="card-title">Household address<\/h2>/)
  assert.equal((mapSource.match(/<h1>Historical Fire Map<\/h1>/g) ?? []).length, 1)
  assert.doesNotMatch(mapSource, /<h2>Historical Fire Map<\/h2>/)
  assert.doesNotMatch(mapSource, /<h1>Local Area<\/h1>/)
  assert.doesNotMatch(mapSource, /View current conditions and bushfire information near your home\./)
  assert.match(mapSource, /<p class="subhead">See past bushfire records near your home\.<\/p>/)
  assert.equal((mapSource.match(/class="card condition-metric"/g) ?? []).length, 4)
  assert.match(
    mapSource,
    /class="conditions-grid"[\s\S]*?<h2>Temperature<\/h2>[\s\S]*?<h2>Humidity<\/h2>[\s\S]*?<h2>Wind<\/h2>[\s\S]*?<h2>Fire Danger<\/h2>[\s\S]*?<section class="historical-section">/,
  )
  assert.match(mapSource, /\.conditions-grid \{[\s\S]*?grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(mapSource, /@media \(max-width: 900px\)[\s\S]*?\.conditions-layout,[\s\S]*?grid-template-columns: 1fr/)
  assert.match(mapSource, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(mapSource, /grid-template-columns: minmax\(0, 3fr\) minmax\(0, 2fr\)/)
  const columns = (selector) => mapSource.match(new RegExp(`${selector} \{([^}]+)\}`))?.[1]
  for (const rule of ['grid-template-columns: minmax(0, 3fr) minmax(0, 2fr)', 'gap: clamp(2rem, 5vw, 4rem)']) {
    assert.ok(columns('\\.conditions-layout').includes(rule))
    assert.ok(columns('\\.map-layout').includes(rule))
  }
  assert.match(
    mapSource,
    /Nearest historical fire[\s\S]*?Most recent historical fire[\s\S]*?<h2>Bushfire context<\/h2>[\s\S]*?recordCountText/,
  )
  assert.match(mapSource, /Bushfire-prone area/)
  assert.match(mapSource, /CFA Fire District/)
  assert.match(mapSource, /Used to match official fire danger information for your area\./)
})
