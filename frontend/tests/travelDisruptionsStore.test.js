import test from 'node:test'
import assert from 'node:assert/strict'

import { createPinia, setActivePinia } from 'pinia'

import { api } from '../src/api/client.js'
import { useTravelDisruptionsStore } from '../src/stores/travelDisruptions.js'


test('successful load stores the travel-disruption result', async () => {
  setActivePinia(createPinia())

  const original = api.getTravelDisruptions

  api.getTravelDisruptions = async () => ({
    status: 'available',
    checked_at: '2026-09-14T03:00:00Z',
    primary_destination: {
      destination_id: 'destination_primary',
      destination_name: 'Primary destination',
      search_radius_km: 10,
      active_disruption_count: 1,
      disruptions: [
        {
          disruption_id: 'impact-1',
          event_type: 'Hazard',
          event_subtype: 'Road Damage',
          road_name: 'Example Road',
          description: 'Example disruption',
          impact: 'Traffic affected',
          status: 'Active',
          latitude: -37.8136,
          longitude: 144.9631,
          distance_km: 2.4,
          last_updated: '2026-09-14T02:30:00Z',
          end_time: null,
        },
      ],
    },
    backup_destinations: [],
    unavailable_reason: null,
    disclaimer:
      'Nearby reported road disruptions do not necessarily mean your planned travel route is blocked or unsafe.',
  })

  try {
    const store = useTravelDisruptionsStore()

    await store.load('household-1')

    assert.equal(store.status, 'success')
    assert.equal(store.error, null)
    assert.equal(store.result.status, 'available')
    assert.equal(
      store.result.primary_destination.active_disruption_count,
      1,
    )
    assert.equal(
      store.result.primary_destination.disruptions[0].road_name,
      'Example Road',
    )
  } finally {
    api.getTravelDisruptions = original
  }
})


test('not_applicable is stored as a valid result', async () => {
  setActivePinia(createPinia())

  const original = api.getTravelDisruptions

  api.getTravelDisruptions = async () => ({
    status: 'not_applicable',
    checked_at: '2026-09-14T03:00:00Z',
    primary_destination: null,
    backup_destinations: [],
    unavailable_reason:
      'Add and verify an evacuation destination before checking current road disruptions.',
    disclaimer:
      'Nearby reported road disruptions do not necessarily mean your planned travel route is blocked or unsafe.',
  })

  try {
    const store = useTravelDisruptionsStore()

    await store.load('household-1')

    assert.equal(store.status, 'success')
    assert.equal(store.result.status, 'not_applicable')
    assert.equal(store.error, null)
  } finally {
    api.getTravelDisruptions = original
  }
})


test('a request failure clears stale results and sets an error', async () => {
  setActivePinia(createPinia())

  const original = api.getTravelDisruptions

  api.getTravelDisruptions = async () => {
    throw new Error('Road service unavailable')
  }

  try {
    const store = useTravelDisruptionsStore()

    store.result = {
      status: 'available',
    }

    await store.load('household-1')

    assert.equal(store.status, 'error')
    assert.equal(store.result, null)
    assert.equal(store.error, 'Road service unavailable')
  } finally {
    api.getTravelDisruptions = original
  }
})


test('load without a household id does not call the API', async () => {
  setActivePinia(createPinia())

  const original = api.getTravelDisruptions
  let calls = 0

  api.getTravelDisruptions = async () => {
    calls += 1
  }

  try {
    const store = useTravelDisruptionsStore()

    await store.load(null)

    assert.equal(calls, 0)
    assert.equal(store.status, 'error')
    assert.equal(store.result, null)
    assert.equal(store.error, 'No household is loaded yet.')
  } finally {
    api.getTravelDisruptions = original
  }
})