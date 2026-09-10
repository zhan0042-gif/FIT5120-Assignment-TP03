import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

const { createPinia, setActivePinia } = await import('pinia')
const { api } = await import('../src/api/client.js')
const { useRendezvousStore } = await import('../src/stores/rendezvous.js')

const READY = {
  status: 'ready',
  destination_name: "Relative's House",
  member_etas: [
    {
      member_id: 'm_001',
      display_name: 'Maya',
      origin_kind: 'home',
      travel_seconds: 720,
      distance_meters: 7200,
      waiting_seconds: 2100,
    },
  ],
  everyone_together_seconds: 2820,
  slowest_member_id: 'm_002',
  warnings: [],
  simulated_at: '2026-09-10T04:32:00Z',
}

const originalSimulate = api.simulateRendezvous

afterEach(() => {
  api.simulateRendezvous = originalSimulate
})

function freshStore() {
  setActivePinia(createPinia())
  return useRendezvousStore()
}

test('a successful run stores the result and reports success', async () => {
  api.simulateRendezvous = async () => READY
  const store = freshStore()

  await store.runSimulation('hh_1')

  assert.equal(store.status, 'success')
  assert.equal(store.result.everyone_together_seconds, 2820)
  assert.equal(store.error, null)
})

test('a not_applicable response is a result, not an error', async () => {
  api.simulateRendezvous = async () => ({
    status: 'not_applicable',
    unavailable_reason: 'Finish your plan before running this simulation.',
    missing_sections: ['member_locations'],
    member_etas: [],
    warnings: [],
    simulated_at: '2026-09-10T04:32:00Z',
  })
  const store = freshStore()

  await store.runSimulation('hh_1')

  assert.equal(store.status, 'success')
  assert.equal(store.result.status, 'not_applicable')
  assert.deepEqual(store.result.missing_sections, ['member_locations'])
  assert.equal(store.error, null)
})

test('a thrown request sets an error and clears any stale result', async () => {
  api.simulateRendezvous = async () => READY
  const store = freshStore()
  await store.runSimulation('hh_1')

  api.simulateRendezvous = async () => {
    throw new Error('network down')
  }
  await store.runSimulation('hh_1')

  assert.equal(store.status, 'error')
  assert.equal(store.result, null)
  assert.match(store.error, /network down/)
})

test('a run without a household id never reaches the network', async () => {
  let called = false
  api.simulateRendezvous = async () => {
    called = true
    return READY
  }
  const store = freshStore()

  await store.runSimulation(null)

  assert.equal(called, false)
  assert.equal(store.status, 'error')
})
