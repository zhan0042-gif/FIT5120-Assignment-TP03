import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'

// The household store reads localStorage when it is created; give it an in-memory one,
// as the other store tests do.
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
const { liveTransport } = await import('../src/voice/liveConnection.js')
const { MicrophoneDenied } = await import('../src/voice/liveConnection.js')
const { useHouseholdStore } = await import('../src/stores/household.js')
const { useLocalContextStore } = await import('../src/stores/localContext.js')
const { useVoiceStore, IDLE_TIMEOUT_MS, MAX_SESSION_MS, NUMBER_CHECK_DELAY_MS } = await import(
  '../src/stores/voice.js'
)
const { VOICE_CHECK_FIGURES, VOICE_NOT_UNDERSTOOD, VOICE_UNAVAILABLE } = await import(
  '../src/utils/voiceCopy.js'
)

const originals = {
  open: liveTransport.open,
  decide: api.decideVoiceAction,
  createSession: api.createLiveSession,
  getLocalContext: api.getLocalContext,
}

afterEach(() => {
  liveTransport.open = originals.open
  api.decideVoiceAction = originals.decide
  api.createLiveSession = originals.createSession
  api.getLocalContext = originals.getLocalContext
  mock.timers.reset()
})

const WEATHER_CONTEXT = {
  weather: {
    temperature_c: 21.5,
    relative_humidity: 40,
    wind_speed_kmh: 18,
    wind_direction: 'NW',
    observed_at: '2026-10-08T01:00:00Z',
    station_name: 'Melbourne Airport',
  },
  fire_danger: { availability: 'unavailable', message: 'x' },
}

// Let pending promises (the decide call, the handler, the commentary send) settle.
// setImmediate is not mocked, so this works while setTimeout is.
const flush = () => new Promise((resolve) => setImmediate(resolve))

function setup() {
  // The store starts a 60 s idle timer and a 10 min limit for every session. Mock
  // setTimeout for every test so no real timer keeps the test process alive; the
  // afterEach above resets it.
  mock.timers.reset() // a test may call setup() more than once
  mock.timers.enable({ apis: ['setTimeout'] })
  setActivePinia(createPinia())
  const household = useHouseholdStore()
  household.householdId = 'hh_1'
  const localContext = useLocalContextStore()
  localContext.location = { latitude: -37.8, longitude: 145.1, verification_status: 'verified' }
  api.getLocalContext = async () => WEATHER_CONTEXT

  const fake = { sent: [], emit: null, onClosed: null, closeCalls: 0, openArgs: null }
  liveTransport.open = async (args) => {
    fake.openArgs = args
    fake.emit = args.onEvent
    fake.onClosed = args.onClosed
    return {
      send: (event) => fake.sent.push(event),
      close: () => {
        fake.closeCalls += 1
      },
    }
  }

  const decisions = []
  api.decideVoiceAction = async (householdId, body) => {
    decisions.push({ householdId, body })
    return { action: 'read_weather', confidence: 0.9 }
  }

  const router = {
    currentRoute: { value: { name: 'plan-builder' } },
    pushed: [],
    async push(path) {
      this.pushed.push(path)
      this.currentRoute.value = { name: path.slice(1) }
    },
    back() {
      this.pushed.push('back')
    },
  }
  const store = useVoiceStore()
  return { store, fake, decisions, router, localContext }
}

async function startSession(ctx) {
  await ctx.store.start({ router: ctx.router })
  ctx.fake.emit({ type: 'session.started', session: { id: 'live_1' } })
}

function say(ctx, text) {
  ctx.fake.emit({ type: 'session.input_transcript.delta', delta: text, start_ms: 0, end_ms: 1 })
}

function delegate(ctx, id = 'd1') {
  ctx.fake.emit({ type: 'session.delegation.created', delegation: { id, target: 'client' } })
}

const commentary = (ctx) => ctx.fake.sent.filter((event) => event.type === 'session.commentary.append')

test('start opens a session and listening begins at session.started', async () => {
  const ctx = setup()

  const starting = ctx.store.start({ router: ctx.router })
  assert.equal(ctx.store.status, 'connecting')
  await starting
  assert.equal(ctx.store.status, 'connecting')
  ctx.fake.emit({ type: 'session.started', session: { id: 'live_1' } })

  assert.equal(ctx.store.status, 'listening')
})

test('the answer request uses the household and the browser offer', async () => {
  const ctx = setup()
  const calls = []
  api.createLiveSession = async (householdId, sdp) => {
    calls.push([householdId, sdp])
    return { session: { id: 'live_1' }, transport: { type: 'webrtc', sdp: 'answer-sdp' } }
  }
  await ctx.store.start({ router: ctx.router })

  const answer = await ctx.fake.openArgs.requestAnswer('offer-sdp')

  assert.equal(answer, 'answer-sdp')
  assert.deepEqual(calls, [['hh_1', 'offer-sdp']])
})

test('a delegation chooses an action, runs it and sends the read-out as commentary', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'Show me the weather')
  delegate(ctx)
  assert.equal(ctx.store.status, 'checking')
  await flush()

  assert.deepEqual(ctx.decisions[0].body, {
    utterance: 'Show me the weather',
    page: 'my plan',
    lastReadout: '',
  })
  assert.deepEqual(ctx.router.pushed, ['/overview'])
  const [sent] = commentary(ctx)
  assert.equal(sent.delegation_id, 'd1')
  assert.match(sent.content, /^The temperature is 21\.5 degrees Celsius/)
  assert.equal(ctx.store.status, 'listening')
})

test('the next request is told what was last read out', async () => {
  const ctx = setup()
  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx, 'd1')
  await flush()

  say(ctx, 'say that again')
  delegate(ctx, 'd2')
  await flush()

  assert.equal(ctx.decisions[1].body.lastReadout, 'weather')
  assert.equal(ctx.decisions[1].body.page, 'overview')
})

test('an action the app has no handler for is not understood', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'delete_plan', confidence: 0.99 })
  await startSession(ctx)

  say(ctx, 'delete my plan')
  delegate(ctx)
  await flush()

  assert.equal(commentary(ctx)[0].content, VOICE_NOT_UNDERSTOOD)
  assert.deepEqual(ctx.router.pushed, [])
})

test('none is not understood', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'none', confidence: 0.9 })
  await startSession(ctx)

  say(ctx, 'hello')
  delegate(ctx)
  await flush()

  assert.equal(commentary(ctx)[0].content, VOICE_NOT_UNDERSTOOD)
})

test('an empty utterance is not understood and does not call the server', async () => {
  const ctx = setup()
  await startSession(ctx)

  delegate(ctx)
  await flush()

  assert.equal(commentary(ctx)[0].content, VOICE_NOT_UNDERSTOOD)
  assert.equal(ctx.decisions.length, 0)
})

test('the previous utterance is never reused for the next delegation', async () => {
  const ctx = setup()
  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx, 'd1')
  await flush()

  delegate(ctx, 'd2')
  await flush()

  assert.equal(ctx.decisions.length, 1)
  assert.equal(commentary(ctx)[1].content, VOICE_NOT_UNDERSTOOD)
})

test('a very long utterance is cut to the last 300 characters', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, `${'a'.repeat(250)}${'b'.repeat(250)}`)
  delegate(ctx)
  await flush()

  assert.equal(ctx.decisions[0].body.utterance, 'a'.repeat(50) + 'b'.repeat(250))
})

test('a failing decision service gets the fixed unavailable sentence', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => {
    throw new ApiError(503, 'down')
  }
  await startSession(ctx)

  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  assert.equal(commentary(ctx)[0].content, VOICE_UNAVAILABLE)
  assert.equal(ctx.store.status, 'listening')
})

test('a handler that throws does not leave the store stuck checking', async () => {
  const ctx = setup()
  ctx.router.push = async () => {
    throw new Error('navigation failed')
  }
  await startSession(ctx)

  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  assert.equal(commentary(ctx)[0].content, VOICE_UNAVAILABLE)
  assert.equal(ctx.store.status, 'listening')
})

test('a stale delegation result is dropped', async () => {
  const ctx = setup()
  const releases = []
  api.decideVoiceAction = (householdId, body) =>
    new Promise((resolve) => releases.push(() => resolve({ action: 'read_weather', confidence: 0.9, body })))
  await startSession(ctx)

  say(ctx, 'first')
  delegate(ctx, 'old')
  say(ctx, 'second')
  delegate(ctx, 'new')
  await flush() // both decide calls are made after an await, so wait for them
  releases[1]()
  await flush()
  releases[0]()
  await flush()

  const sent = commentary(ctx)
  assert.equal(sent.length, 1)
  assert.equal(sent[0].delegation_id, 'new')
})

test('a delegation without an id is ignored', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'weather')
  ctx.fake.emit({ type: 'session.delegation.created', delegation: {} })
  await flush()

  assert.equal(commentary(ctx).length, 0)
  assert.equal(ctx.decisions.length, 0)
})

test('start failures are described and leave the store usable again', async () => {
  const cases = [
    [new MicrophoneDenied(), /Microphone access was blocked/],
    [Object.assign(new Error('x'), { name: 'NotFoundError' }), /No microphone was found/],
    [new ApiError(429, 'slow down'), /Too many voice sessions/],
    [new ApiError(503, 'down'), /Voice is not available right now/],
    [new Error('boom'), /Voice could not start/],
  ]
  for (const [failure, message] of cases) {
    const ctx = setup()
    liveTransport.open = async () => {
      throw failure
    }

    await ctx.store.start({ router: ctx.router })

    assert.equal(ctx.store.status, 'error')
    assert.match(ctx.store.error, message)
    assert.match(ctx.store.error, /chat|try again/i)

    liveTransport.open = originals.open
    liveTransport.open = async (args) => {
      ctx.fake.emit = args.onEvent
      return { send() {}, close() {} }
    }
    await ctx.store.start({ router: ctx.router })
    assert.equal(ctx.store.status, 'connecting')
    assert.equal(ctx.store.error, null)
  }
})

test('stop asks the connection to close and the session ends when it reports closed', async () => {
  const ctx = setup()
  await startSession(ctx)

  ctx.store.stop()
  assert.equal(ctx.store.status, 'closing')
  assert.equal(ctx.fake.closeCalls, 1)
  ctx.fake.onClosed({ type: 'session.closed', reason: 'close_requested', usage: { seconds: 5 } })

  assert.equal(ctx.store.status, 'idle')
})

test('the session ends after sixty seconds without speech', async () => {
  const ctx = setup()
  await startSession(ctx)

  mock.timers.tick(IDLE_TIMEOUT_MS - 1)
  assert.equal(ctx.fake.closeCalls, 0)
  mock.timers.tick(1)

  assert.equal(ctx.fake.closeCalls, 1)
  assert.equal(ctx.store.status, 'closing')
})

test('speech keeps the session open until the ten minute limit', async () => {
  const ctx = setup()
  await startSession(ctx)

  for (let elapsed = 0; elapsed < MAX_SESSION_MS - 30_000; elapsed += 30_000) {
    say(ctx, 'still here')
    mock.timers.tick(30_000)
  }
  assert.equal(ctx.fake.closeCalls, 0)
  say(ctx, 'still here')
  mock.timers.tick(30_000)

  assert.equal(ctx.fake.closeCalls, 1)
})

test('speech with a number that was never sent raises the figures notice', async () => {
  const ctx = setup()
  await startSession(ctx)

  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'It is 25 degrees.' })
  mock.timers.tick(NUMBER_CHECK_DELAY_MS)

  assert.equal(ctx.store.notice, VOICE_CHECK_FIGURES)
})

test('speech that repeats only the sent figures raises no notice, and a later delegation clears one', async () => {
  const ctx = setup()
  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'It is 21.5 degrees, ' })
  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'humidity 40 percent.' })
  mock.timers.tick(NUMBER_CHECK_DELAY_MS)
  assert.equal(ctx.store.notice, null)

  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'About 99 percent.' })
  mock.timers.tick(NUMBER_CHECK_DELAY_MS)
  assert.equal(ctx.store.notice, VOICE_CHECK_FIGURES)

  say(ctx, 'weather')
  delegate(ctx, 'd2')
  assert.equal(ctx.store.notice, null)
  await flush()
})

test('a closed session resets state and a new session starts clean', async () => {
  const ctx = setup()
  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  ctx.fake.onClosed(null)
  assert.equal(ctx.store.status, 'idle')

  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx, 'd9')
  await flush()
  assert.equal(ctx.decisions.at(-1).body.lastReadout, '')
})
