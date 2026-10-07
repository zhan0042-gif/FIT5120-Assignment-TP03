import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createHandlers, pageLabel } = await import('../src/voice/actions.js')
const { EMERGENCY_MESSAGE, NO_MATCH_MESSAGE } = await import('../src/utils/safetyGuidanceCopy.js')
const { VOICE_NOTHING_TO_REPEAT, VOICE_UNAVAILABLE } = await import('../src/utils/voiceCopy.js')

function makeDeps(overrides = {}) {
  const log = []
  const router = {
    currentRoute: { value: { name: 'plan-builder' } },
    async push(path) {
      log.push(['push', path])
      this.currentRoute.value = { name: path.slice(1) }
    },
    back() {
      log.push(['back'])
    },
  }
  const deps = {
    log,
    router,
    householdStore: {
      householdId: 'hh_1',
      completion: null,
      completionStatus: 'idle',
      async ensureHousehold() {
        return 'hh_1'
      },
      async loadCompletion() {
        log.push(['loadCompletion'])
      },
    },
    localContextStore: {
      location: null,
      context: null,
      contextStatus: 'idle',
      async init() {
        log.push(['init'])
      },
      async loadContext() {
        log.push(['loadContext'])
      },
    },
    fireMapStore: {
      status: 'idle',
      totalCount: 0,
      searchRadiusKm: null,
      mostRecentFire: null,
      nearestFire: null,
      async loadFirePoints() {
        log.push(['loadFirePoints'])
      },
    },
    travelStore: {
      status: 'idle',
      result: null,
      async load(householdId) {
        log.push(['loadDisruptions', householdId])
      },
    },
    safetyStore: {
      status: 'success',
      messages: [],
      entriesById: {},
      async loadFor() {
        log.push(['loadSafety'])
      },
      async askTyped() {
        return true
      },
    },
    getLastText: () => '',
    ...overrides,
  }
  return deps
}

test('pageLabel maps route names to the labels the server is told', () => {
  assert.equal(pageLabel('overview'), 'overview')
  assert.equal(pageLabel('plan-builder'), 'my plan')
  assert.equal(pageLabel('fire-map'), 'fire map')
  assert.equal(pageLabel('scenario-tester'), 'test my plan')
  assert.equal(pageLabel('travel-readiness'), 'travel readiness')
  assert.equal(pageLabel('something-new'), 'other')
  assert.equal(pageLabel(undefined), 'other')
})

test('every action except none has a handler', () => {
  const handlers = createHandlers(makeDeps())

  assert.deepEqual(
    Object.keys(handlers).sort(),
    [
      'ask_safety_question',
      'check_travel_disruptions',
      'go_back',
      'open_fire_map',
      'open_overview',
      'open_plan',
      'open_scenarios',
      'open_travel_readiness',
      'read_fire_danger',
      'read_plan_completion',
      'read_weather',
      'repeat_last',
      'show_fire_history',
    ],
  )
})

test('navigation actions go to their page and say so', async () => {
  const deps = makeDeps()
  const handlers = createHandlers(deps)

  assert.deepEqual(await handlers.open_overview({}), { spoken: 'Opening the overview.' })
  await handlers.open_plan({})
  await handlers.open_fire_map({})
  await handlers.open_scenarios({})
  await handlers.open_travel_readiness({})

  assert.deepEqual(
    deps.log.filter(([kind]) => kind === 'push').map(([, path]) => path),
    ['/overview', '/plan', '/map', '/scenarios', '/travel-readiness'],
  )
})

test('go_back goes back', async () => {
  const deps = makeDeps()

  assert.deepEqual(await createHandlers(deps).go_back({}), { spoken: 'Going back.' })
  assert.deepEqual(deps.log, [['back']])
})

test('read_weather opens the overview, loads the context and reads the weather', async () => {
  const deps = makeDeps()
  deps.localContextStore.location = { verification_status: 'verified' }
  deps.localContextStore.contextStatus = 'success'
  deps.localContextStore.context = {
    weather: {
      temperature_c: 21.5,
      relative_humidity: 40,
      wind_speed_kmh: 18,
      wind_direction: 'NW',
      station_name: 'Melbourne Airport',
    },
  }

  const result = await createHandlers(deps).read_weather({})

  assert.deepEqual(deps.log, [['push', '/overview'], ['loadContext']])
  assert.equal(result.label, 'weather')
  assert.match(result.spoken, /^The temperature is 21\.5 degrees Celsius/)
})

test('read_weather loads the saved location first when none is loaded yet', async () => {
  const deps = makeDeps()
  deps.localContextStore.init = async () => {
    deps.log.push(['init'])
    deps.localContextStore.location = { verification_status: 'verified' }
    deps.localContextStore.contextStatus = 'success'
    deps.localContextStore.context = { weather: null }
  }

  const result = await createHandlers(deps).read_weather({})

  assert.deepEqual(deps.log, [['push', '/overview'], ['init'], ['loadContext']])
  assert.match(result.spoken, /not available right now/)
})

test('read_weather keeps the failure status when no location could be loaded', async () => {
  const deps = makeDeps()
  deps.localContextStore.init = async () => {
    deps.log.push(['init'])
    deps.localContextStore.contextStatus = 'error'
  }

  const result = await createHandlers(deps).read_weather({})

  assert.deepEqual(deps.log, [['push', '/overview'], ['init']])
  assert.match(result.spoken, /not available right now/)
})

test('read_weather does not guess when the address is not verified', async () => {
  const deps = makeDeps()
  deps.localContextStore.location = { verification_status: 'unverified' }
  deps.localContextStore.contextStatus = 'unverified'

  const result = await createHandlers(deps).read_weather({})

  assert.match(result.spoken, /verified household address/)
})

test('read_fire_danger reads today from the overview context', async () => {
  const deps = makeDeps()
  deps.localContextStore.location = { verification_status: 'verified' }
  deps.localContextStore.contextStatus = 'success'
  deps.localContextStore.context = { fire_danger: { availability: 'available', today: 'High', tomorrow: 'High' } }

  const result = await createHandlers(deps).read_fire_danger({})

  assert.equal(result.label, 'fire danger')
  assert.equal(result.spoken, "Today's fire danger rating is High, from the official source.")
})

test('read_plan_completion opens the overview and reads the completion store', async () => {
  const deps = makeDeps()
  deps.householdStore.completionStatus = 'success'
  deps.householdStore.completion = { overall_status: 'complete', sections: [] }

  const result = await createHandlers(deps).read_plan_completion({})

  assert.deepEqual(deps.log, [['push', '/overview'], ['loadCompletion']])
  assert.deepEqual(result, { label: 'plan completion', spoken: 'Your plan is complete.' })
})

test('show_fire_history opens the fire map, loads the points and reads them', async () => {
  const deps = makeDeps()
  Object.assign(deps.fireMapStore, {
    status: 'success',
    totalCount: 3,
    searchRadiusKm: 10,
    mostRecentFire: { season: 2020 },
    nearestFire: { distance_km: 2.04 },
  })

  const result = await createHandlers(deps).show_fire_history({})

  assert.deepEqual(deps.log, [['push', '/map'], ['loadFirePoints']])
  assert.equal(result.label, 'fire history')
  assert.match(result.spoken, /^There are 3 recorded fires within 10\.0 kilometres/)
})

test('check_travel_disruptions opens Test My Plan, runs the check for the household and reads it', async () => {
  const deps = makeDeps()
  deps.travelStore.status = 'success'
  deps.travelStore.result = { status: 'not_applicable' }

  const result = await createHandlers(deps).check_travel_disruptions({})

  assert.deepEqual(deps.log, [['push', '/scenarios'], ['loadDisruptions', 'hh_1']])
  assert.equal(result.label, 'road disruptions')
  assert.match(result.spoken, /verified evacuation destination/)
})

test('repeat_last says the last read-out again, or that there is nothing to repeat', async () => {
  const repeating = createHandlers(makeDeps({ getLastText: () => 'The temperature is 21.5.' }))
  const empty = createHandlers(makeDeps())

  assert.deepEqual(await repeating.repeat_last({}), { spoken: 'The temperature is 21.5.' })
  assert.deepEqual(await empty.repeat_last({}), { spoken: VOICE_NOTHING_TO_REPEAT })
})

function safetyDeps(afterAsk) {
  const deps = makeDeps()
  deps.safetyStore.entriesById = {
    a: { id: 'a', answer: 'Leave early, before any fire starts.' },
    b: { id: 'b', answer: 'Plan for your pets too.' },
  }
  deps.safetyStore.askTyped = async (householdId, text) => {
    deps.log.push(['ask', householdId, text])
    deps.safetyStore.messages.push({ id: 1, role: 'user', text })
    afterAsk(deps.safetyStore.messages)
    return true
  }
  return deps
}

test('ask_safety_question opens the overview and speaks the matched reviewed answers', async () => {
  const deps = safetyDeps((messages) => {
    messages.push({ id: 2, role: 'assistant', entryId: 'a' }, { id: 3, role: 'assistant', entryId: 'b' })
  })

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'When should we leave?' })

  assert.deepEqual(deps.log, [['push', '/overview'], ['loadSafety'], ['ask', 'hh_1', 'When should we leave?']])
  assert.deepEqual(result, {
    label: 'safety answer',
    spoken: 'Leave early, before any fire starts. Plan for your pets too.',
  })
})

test('ask_safety_question uses the fixed sentences for emergency, no match and unavailable', async () => {
  const cases = [
    ['emergency', EMERGENCY_MESSAGE],
    ['no_match', NO_MATCH_MESSAGE],
    ['unavailable', VOICE_UNAVAILABLE],
  ]
  for (const [kind, expected] of cases) {
    const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', kind }))

    const result = await createHandlers(deps).ask_safety_question({ utterance: 'help' })

    assert.equal(result.spoken, expected)
  }
})

test('ask_safety_question loads the guidance first when the panel has not', async () => {
  const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', kind: 'no_match' }))
  deps.safetyStore.status = 'idle'

  await createHandlers(deps).ask_safety_question({ utterance: 'hi' })

  assert.deepEqual(deps.log.map(([kind]) => kind), ['push', 'loadSafety', 'ask'])
})

test('ask_safety_question does not push the overview when already there', async () => {
  const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', kind: 'no_match' }))
  deps.router.currentRoute.value = { name: 'overview' }

  await createHandlers(deps).ask_safety_question({ utterance: 'hi' })

  assert.equal(deps.log.some(([kind]) => kind === 'push'), false)
})

test('ask_safety_question is unavailable when the store refuses the question', async () => {
  const deps = makeDeps()
  deps.safetyStore.askTyped = async () => false

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'hi' })

  assert.equal(result.spoken, VOICE_UNAVAILABLE)
})

test('ask_safety_question is unavailable when no reply was recorded', async () => {
  const deps = safetyDeps(() => {})

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'hi' })

  assert.equal(result.spoken, VOICE_UNAVAILABLE)
})

test('after navigating, ask_safety_question loads the guidance last so the panel mounting cannot wipe the answer', async () => {
  // Opening the overview mounts the safety panel, whose own load clears the store's
  // messages and bumps its revision. A question asked in that window is discarded and the
  // person would hear "unavailable" instead of the 000 notice. So after a navigation the
  // handler waits for the mount, loads the guidance itself, and only then asks.
  const deps = safetyDeps((messages) => messages.push({ id: 2, role: 'assistant', kind: 'emergency' }))
  deps.safetyStore.status = 'success' // loaded on an earlier visit, as it would be

  const result = await createHandlers(deps).ask_safety_question({ utterance: 'The fire is coming, help me!' })

  assert.deepEqual(deps.log.map(([kind]) => kind), ['push', 'loadSafety', 'ask'])
  assert.equal(result.spoken, EMERGENCY_MESSAGE)
})

test('the unavailable sentence always carries the 000 instruction', () => {
  assert.match(VOICE_UNAVAILABLE, /If you are in danger, call 000\./)
})
