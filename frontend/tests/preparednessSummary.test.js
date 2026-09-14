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
const summarySource = await readFile(
  new URL('../src/views/PreparednessSummaryView.vue', import.meta.url),
  'utf8',
)

afterEach(() => {
  Object.assign(api, originalApi)
  globalThis.fetch = originalFetch
  localStorage.clear()
})

test('summary refresh loads the latest saved plan through the existing store', async () => {
  localStorage.setItem('firebreak.household-id.v1', 'hh_summary')
  setActivePinia(createPinia())
  const store = useHouseholdStore()
  let planRequests = 0
  const savedPlan = {
    members: [{
      member_id: 'm_1',
      display_name: 'Maya',
      relationship: 'self',
      usual_location: { kind: 'work', address: '1 Treasury Place, East Melbourne VIC 3002' },
    }],
    animals: [{ animal_id: 'a_1', animal_type: 'cat', display_name: 'Gift', quantity: 1 }],
    transports: [],
    arrangements: { backup_arrangements: [] },
    responsibilities: [],
  }
  api.getHouseholdPlan = async (householdId) => {
    planRequests += 1
    assert.equal(householdId, 'hh_summary')
    return savedPlan
  }
  api.getCompletion = async () => ({ overall_status: 'needs_information', sections: [], immediate_checks: [] })

  await store.loadPlan()

  assert.equal(planRequests, 1)
  assert.deepEqual(store.plan, savedPlan)
  assert.deepEqual(store.plan.members[0].usual_location, {
    kind: 'work',
    address: '1 Treasury Place, East Melbourne VIC 3002',
  })
  assert.deepEqual(store.plan.animals[0], {
    animal_id: 'a_1',
    animal_type: 'cat',
    display_name: 'Gift',
    quantity: 1,
  })
  assert.equal(store.planStatus, 'success')
})

test('summary presents member daytime details and pets in labelled table columns', () => {
  assert.match(summarySource, /<th>Daytime location<\/th><th>Daytime address<\/th>/)
  assert.match(summarySource, /\{\{ daytimeLocation\(member\) \}\}/)
  assert.match(summarySource, /\{\{ daytimeAddress\(member\) \}\}/)
  assert.match(summarySource, /<th>Pet type<\/th><th>Name<\/th><th>Quantity<\/th>/)
  assert.match(summarySource, /\{\{ animalType\(animal\) \}\}/)
  assert.match(summarySource, /\{\{ recorded\(animal\.display_name\) \}\}/)
  assert.match(summarySource, /\{\{ animal\.quantity \}\}/)
  assert.match(summarySource, /api\.getLocation\(householdStore\.householdId\)/)
  assert.match(summarySource, /location\.canonical_address \|\| location\.address/)
  assert.doesNotMatch(summarySource, /Uses household address/)
  assert.match(summarySource, /Check your saved plan before exporting or printing it\./)
})

test('PDF request uses the household endpoint and download filename', async () => {
  const expected = new Blob(['%PDF-test'], { type: 'application/pdf' })
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/v1/households/hh_summary/preparedness-plan.pdf')
    assert.equal(init, undefined)
    return new Response(expected, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="firebreak-household-plan.pdf"',
      },
    })
  }

  const result = await api.getPreparednessPlanPdf('hh_summary')

  assert.equal(result.filename, 'firebreak-household-plan.pdf')
  assert.equal(result.blob.type, 'application/pdf')
  assert.equal(await result.blob.text(), '%PDF-test')
})
