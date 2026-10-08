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
const {
  useVoiceStore,
  CONNECT_TIMEOUT_MS,
  IDLE_TIMEOUT_MS,
  MAX_SESSION_MS,
  NUMBER_CHECK_DELAY_MS,
  TRANSCRIPT_MAX_WAIT_MS,
  TRANSCRIPT_SETTLE_MS,
} = await import(
  '../src/stores/voice.js'
)
const { VOICE_CHECK_FIGURES, VOICE_NOT_UNDERSTOOD, VOICE_UNAVAILABLE } = await import(
  '../src/utils/voiceCopy.js'
)

// The real route names, so the page label the store sends matches what the app shows.
const ROUTE_NAMES = {
  '/map': 'fire-map',
  '/plan': 'plan-builder',
  '/safety-insights': 'safety-insights',
}

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

// Let pending promises settle. setImmediate is not mocked, so this works while
// setTimeout is.
const microtasks = () => new Promise((resolve) => setImmediate(resolve))

// A delegation waits for its transcript to settle before it is acted on; let that wait
// run out too, then let the decide call, the handler and the commentary send settle.
async function flush() {
  mock.timers.tick(TRANSCRIPT_MAX_WAIT_MS)
  await microtasks()
}

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
      this.currentRoute.value = { name: ROUTE_NAMES[path] ?? path.slice(1), path }
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
  assert.deepEqual(ctx.router.pushed, ['/map'])
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
  assert.equal(ctx.decisions[1].body.page, 'fire map')
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

test('a request to read the simulation is answered from the real simulation store', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'read_simulation', confidence: 0.9 })
  await startSession(ctx)

  say(ctx, 'What did the simulation say?')
  delegate(ctx)
  await flush()

  assert.deepEqual(ctx.router.pushed, ['/scenarios'])
  assert.match(commentary(ctx)[0].content, /has not been run yet/)
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
  await flush() // the older request is now with the server
  say(ctx, 'second')
  delegate(ctx, 'new')
  await flush()
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

test('what was heard before the assistant answered by itself is not carried into the next request', async () => {
  const ctx = setup()
  await startSession(ctx)

  // GPT-Live asks a clarifying question without delegating, as its prompt allows.
  say(ctx, 'Read me the fire history')
  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'Which area do you mean?' })
  say(ctx, 'No, never mind, what should we pack?')
  delegate(ctx)
  await flush()

  assert.equal(ctx.decisions[0].body.utterance, 'No, never mind, what should we pack?')
})

test('the assistant acknowledging a delegation does not discard the next request', async () => {
  const ctx = setup()
  await startSession(ctx)
  say(ctx, 'weather')
  delegate(ctx, 'd1')
  await flush()

  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'Let me check that.' })
  say(ctx, 'and the fire danger')
  delegate(ctx, 'd2')
  await flush()

  assert.equal(ctx.decisions[1].body.utterance, 'and the fire danger')
})

test('several fragments of one request are joined and still reach the server whole', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'Show me ')
  say(ctx, 'the weather')
  delegate(ctx)
  await flush()

  assert.equal(ctx.decisions[0].body.utterance, 'Show me the weather')
})

test('a session that never reports started is ended after fifteen seconds', async () => {
  const ctx = setup()
  await ctx.store.start({ router: ctx.router })
  assert.equal(CONNECT_TIMEOUT_MS, 15_000)

  mock.timers.tick(CONNECT_TIMEOUT_MS - 1)
  assert.equal(ctx.fake.closeCalls, 0)
  mock.timers.tick(1)

  assert.equal(ctx.fake.closeCalls, 1)
  assert.equal(ctx.store.status, 'closing')
})

test('a session that does start is not ended by the connect timeout', async () => {
  const ctx = setup()
  await startSession(ctx)

  mock.timers.tick(CONNECT_TIMEOUT_MS)

  assert.equal(ctx.fake.closeCalls, 0)
  assert.equal(ctx.store.status, 'listening')
})

test('a delegation that arrives before its transcript waits for the words to settle', async () => {
  const ctx = setup()
  await startSession(ctx)

  delegate(ctx) // GPT-Live signals the request before the transcript has come in
  await microtasks()
  assert.equal(ctx.decisions.length, 0)

  say(ctx, 'Show me ')
  mock.timers.tick(TRANSCRIPT_SETTLE_MS - 1)
  say(ctx, 'the weather') // more words restart the quiet period
  mock.timers.tick(TRANSCRIPT_SETTLE_MS - 1)
  await microtasks()
  assert.equal(ctx.decisions.length, 0)
  mock.timers.tick(1)
  await microtasks()

  assert.equal(ctx.decisions.length, 1)
  assert.equal(ctx.decisions[0].body.utterance, 'Show me the weather')
  assert.match(commentary(ctx)[0].content, /^The temperature is 21\.5/)
})

test('a delegation whose words are already there still waits briefly for the rest', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'Show me')
  delegate(ctx)
  await microtasks()
  assert.equal(ctx.decisions.length, 0)
  say(ctx, ' the weather')
  mock.timers.tick(TRANSCRIPT_SETTLE_MS)
  await microtasks()

  assert.equal(ctx.decisions[0].body.utterance, 'Show me the weather')
})

test('a delegation that never gets a transcript is not understood after the wait runs out', async () => {
  const ctx = setup()
  await startSession(ctx)

  delegate(ctx)
  mock.timers.tick(TRANSCRIPT_MAX_WAIT_MS - 1)
  await microtasks()
  assert.equal(commentary(ctx).length, 0)
  mock.timers.tick(1)
  await microtasks()

  assert.equal(commentary(ctx)[0].content, VOICE_NOT_UNDERSTOOD)
  assert.equal(ctx.decisions.length, 0)
})

test('an acknowledgement spoken while the transcript is still arriving does not erase it', async () => {
  const ctx = setup()
  await startSession(ctx)

  delegate(ctx)
  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: 'Let me check that.' })
  say(ctx, 'Show me the weather')
  mock.timers.tick(TRANSCRIPT_SETTLE_MS)
  await microtasks()

  assert.equal(ctx.decisions[0].body.utterance, 'Show me the weather')
})

test('a newer delegation supersedes one still waiting for its transcript', async () => {
  const ctx = setup()
  await startSession(ctx)

  delegate(ctx, 'old')
  delegate(ctx, 'new')
  say(ctx, 'Show me the weather')
  mock.timers.tick(TRANSCRIPT_SETTLE_MS)
  await microtasks()

  assert.equal(ctx.decisions.length, 1)
  const sent = commentary(ctx)
  assert.equal(sent.length, 1)
  assert.equal(sent[0].delegation_id, 'new')
})

test('closing the session while a delegation waits lets it end quietly', async () => {
  const ctx = setup()
  await startSession(ctx)
  delegate(ctx)

  ctx.fake.onClosed(null)
  await flush()

  assert.equal(commentary(ctx).length, 0)
  assert.equal(ctx.decisions.length, 0)
  assert.equal(ctx.store.status, 'idle')
})
