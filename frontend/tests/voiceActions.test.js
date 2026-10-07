import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createHandlers, pageLabel } = await import('../src/voice/actions.js')
const { EMERGENCY_MESSAGE, NO_MATCH_MESSAGE } = await import('../src/utils/safetyGuidanceCopy.js')
const { VOICE_NOTHING_TO_REPEAT, VOICE_UNAVAILABLE } = await import('../src/utils/voiceCopy.js')

function makeDeps(overrides = {}) {
  const log = []
  const router = {
    currentRoute: { value: { name: 'plan-builder', path: '/plan' } },
    async push(path) {
      log.push(['push', path])
      this.currentRoute.value = { name: path.slice(1), path }
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
      'open_home',
      'open_overview',
      'open_plan',
      'open_scenarios',
      'open_travel_readiness',
      'read_fire_danger',
      'read_plan_completion',
      'read_weather',
      'repeat_last',
      'scroll_down',
      'scroll_to_bottom',
      'scroll_to_top',
      'scroll_up',
      'section_fire_history',
      'section_household_address',
      'section_current_conditions',
      'section_plan_completion',
      'section_plan_summary',
      'section_preparation_status',
      'section_rendezvous',
      'section_safety_guidance',
      'section_scenario_results',
      'section_scenarios',
      'section_travel_disruptions',
      'section_travel_map',
      'show_fire_history',
    ].sort(),
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

test('check_travel_disruptions opens Travel Readiness (where the disruptions are shown), runs the check and reads it', async () => {
  const deps = makeDeps()
  deps.travelStore.status = 'success'
  deps.travelStore.result = { status: 'not_applicable' }

  const result = await createHandlers(deps).check_travel_disruptions({})

  assert.deepEqual(deps.log, [['push', '/travel-readiness'], ['loadDisruptions', 'hh_1']])
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


// A stand-in for the page's scroll container (main#main-content).
function makeBox(overrides = {}) {
  const box = {
    scrollTop: 0,
    scrollHeight: 2000,
    clientHeight: 500,
    calls: [],
    scrollBy(options) {
      this.calls.push(['by', options.top, options.behavior])
      this.scrollTop += options.top
    },
    scrollTo(options) {
      this.calls.push(['to', options.top, options.behavior])
      this.scrollTop = options.top
    },
    ...overrides,
  }
  return box
}

function scrollDeps(box) {
  return makeDeps({ getScroller: () => box, behavior: () => 'smooth' })
}

test('open_home goes to the home page', async () => {
  const deps = makeDeps()

  assert.deepEqual(await createHandlers(deps).open_home({}), { spoken: 'Opening the home page.' })
  assert.deepEqual(deps.log, [['push', '/']])
})

test('scroll_down moves about four fifths of the visible height and says so', async () => {
  const box = makeBox()

  const result = await createHandlers(scrollDeps(box)).scroll_down({})

  assert.deepEqual(box.calls, [['by', 400, 'smooth']])
  assert.deepEqual(result, { spoken: 'Scrolling down.' })
})

test('scroll_down at the bottom says so instead of scrolling', async () => {
  const box = makeBox({ scrollTop: 1500 })

  const result = await createHandlers(scrollDeps(box)).scroll_down({})

  assert.deepEqual(box.calls, [])
  assert.deepEqual(result, { spoken: "You're already at the bottom of the page." })
})

test('scroll_up moves back up, and at the top says so', async () => {
  const lower = makeBox({ scrollTop: 900 })
  const top = makeBox()

  assert.deepEqual(await createHandlers(scrollDeps(lower)).scroll_up({}), { spoken: 'Scrolling up.' })
  assert.deepEqual(lower.calls, [['by', -400, 'smooth']])
  assert.deepEqual(await createHandlers(scrollDeps(top)).scroll_up({}), {
    spoken: "You're already at the top of the page.",
  })
  assert.deepEqual(top.calls, [])
})

test('scroll_to_top and scroll_to_bottom go to the ends', async () => {
  const box = makeBox({ scrollTop: 700 })
  const handlers = createHandlers(scrollDeps(box))

  assert.deepEqual(await handlers.scroll_to_top({}), { spoken: 'Going to the top of the page.' })
  assert.deepEqual(await handlers.scroll_to_bottom({}), { spoken: 'Going to the bottom of the page.' })

  assert.deepEqual(box.calls, [['to', 0, 'smooth'], ['to', 2000, 'smooth']])
})

test('a page that does not scroll, or has no scroll container, says so', async () => {
  const short = makeBox({ scrollHeight: 400 })
  const nothing = createHandlers(makeDeps({ getScroller: () => null }))

  for (const action of ['scroll_down', 'scroll_up', 'scroll_to_top', 'scroll_to_bottom']) {
    const result = await createHandlers(scrollDeps(short))[action]({})
    assert.deepEqual(result, { spoken: 'There is nothing more to scroll on this page.' }, action)
    assert.deepEqual((await nothing[action]({})), { spoken: 'There is nothing more to scroll on this page.' }, action)
  }
  assert.deepEqual(short.calls, [])
})

test('scrolling is not a read-out, so it never becomes the thing to repeat', async () => {
  const box = makeBox()

  const result = await createHandlers(scrollDeps(box)).scroll_down({})

  assert.equal('label' in result, false)
})

function sectionDeps({ present = {}, currentPath = '/overview', missesBeforeFound = 0 } = {}) {
  const calls = []
  let misses = 0
  const deps = makeDeps({
    behavior: () => 'smooth',
    sleep: async () => {
      calls.push(['sleep'])
    },
    findSection: (key) => {
      calls.push(['find', key])
      if (misses < missesBeforeFound) {
        misses += 1
        return null
      }
      return present[key] ?? null
    },
  })
  deps.router.currentRoute.value = { name: currentPath.slice(1), path: currentPath }
  deps.calls = calls
  return deps
}

const anElement = (scrolls) => ({ scrollIntoView: (options) => scrolls.push(options) })

test('a section on the current page is scrolled to without navigating', async () => {
  const scrolls = []
  const deps = sectionDeps({ present: { 'safety-guidance': anElement(scrolls) } })

  const result = await createHandlers(deps).section_safety_guidance({})

  assert.deepEqual(result, { spoken: 'Here is the safety guidance.' })
  assert.deepEqual(scrolls, [{ block: 'start', behavior: 'smooth' }])
  assert.equal(deps.log.some(([kind]) => kind === 'push'), false)
})

test('a section on another page opens that page first, then scrolls', async () => {
  const scrolls = []
  const deps = sectionDeps({ currentPath: '/plan', present: { 'fire-history': anElement(scrolls) } })

  const result = await createHandlers(deps).section_fire_history({})

  assert.deepEqual(deps.log, [['push', '/map']])
  assert.deepEqual(result, { spoken: 'Here is the fire history.' })
  assert.equal(scrolls.length, 1)
})

test('a section that appears a moment after the page opens is still found', async () => {
  const scrolls = []
  const deps = sectionDeps({ missesBeforeFound: 3, present: { 'plan-summary': anElement(scrolls) } })

  const result = await createHandlers(deps).section_plan_summary({})

  assert.deepEqual(result, { spoken: 'Here is the household plan summary.' })
  assert.equal(deps.calls.filter(([kind]) => kind === 'sleep').length, 3)
})

test('a section that never appears is reported as not on the page, never guessed', async () => {
  const deps = sectionDeps({ currentPath: '/scenarios' })

  const result = await createHandlers(deps).section_scenario_results({})

  assert.deepEqual(result, { spoken: "That part isn't on the page right now." })
  assert.equal(deps.calls.filter(([kind]) => kind === 'sleep').length, 20)
})
