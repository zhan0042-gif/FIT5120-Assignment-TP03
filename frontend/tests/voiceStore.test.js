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
  EMERGENCY_FAILSAFE_MS,
  EMERGENCY_RELEASE_MS,
  OUTCOME_FAILSAFE_MS,
  OUTCOME_HOLD_MS,
  PIN_FAILSAFE_MARGIN_MS,
  PIN_HOLD_MAX_MS,
  PIN_WORD_MS,
  REACTION_MS,
  TALK_HOLD_MS,
  TRANSCRIPT_MAX_WAIT_MS,
  TRANSCRIPT_SETTLE_MS,
} = await import(
  '../src/stores/voice.js'
)
const { EMERGENCY_MESSAGE } = await import('../src/utils/safetyGuidanceCopy.js')
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


function speak(ctx, text = 'Okay.') {
  ctx.fake.emit({ type: 'session.output_transcript.delta', delta: text })
}

test('the face follows the conversation: thinking while connecting, listening, thinking while working, neutral when closed', async () => {
  const ctx = setup()

  const starting = ctx.store.start({ router: ctx.router })
  assert.equal(ctx.store.face, 'thinking')
  await starting
  ctx.fake.emit({ type: 'session.started', session: { id: 'live_1' } })
  assert.equal(ctx.store.face, 'listening')

  say(ctx, 'Show me the weather')
  delegate(ctx)
  assert.equal(ctx.store.face, 'thinking')
  await flush()
  assert.equal(ctx.store.face, 'listening')

  ctx.fake.onClosed(null)
  assert.equal(ctx.store.face, 'neutral')
})

test('a weather answer does not make the koala smile', async () => {
  const ctx = setup()
  await startSession(ctx)

  say(ctx, 'Show me the weather')
  delegate(ctx)
  await flush()
  speak(ctx)

  assert.equal(ctx.store.face, 'listening')
})

test('opening a page makes the koala smile while it speaks, then the smile fades', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'happy')
  speak(ctx)
  mock.timers.tick(OUTCOME_HOLD_MS - 1)
  assert.equal(ctx.store.face, 'happy')
  mock.timers.tick(1)

  assert.equal(ctx.store.face, 'listening')
})

test('a smile does not outlast the person speaking again', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)
  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'happy')

  say(ctx, 'And the weather')

  assert.equal(ctx.store.face, 'listening')
})

test('a smile is dropped after the failsafe even if the assistant never speaks', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'open_fire_map', confidence: 0.95, emotion: 'calm' })
  await startSession(ctx)
  say(ctx, 'Take me to the map')
  delegate(ctx)
  await flush()

  mock.timers.tick(OUTCOME_FAILSAFE_MS)

  assert.equal(ctx.store.face, 'listening')
})

test('a request that was not understood leaves the koala sorry', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'none', confidence: 0.9, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'hello there')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'sorry')
})

test('a failing decision service, an empty request and a thrown handler all leave the koala sorry', async () => {
  const cases = [
    async (ctx) => {
      api.decideVoiceAction = async () => {
        throw new ApiError(503, 'down')
      }
      say(ctx, 'weather')
    },
    async () => {},
    async (ctx) => {
      ctx.router.push = async () => {
        throw new Error('navigation failed')
      }
      say(ctx, 'weather')
    },
  ]
  for (const arrange of cases) {
    const ctx = setup()
    await startSession(ctx)
    await arrange(ctx)

    delegate(ctx)
    await flush()

    assert.equal(ctx.store.face, 'sorry')
  }
})

test('a start failure leaves the koala sorry, not smiling', async () => {
  const ctx = setup()
  liveTransport.open = async () => {
    throw new MicrophoneDenied()
  }

  await ctx.store.start({ router: ctx.router })

  assert.equal(ctx.store.status, 'error')
  assert.equal(ctx.store.face, 'sorry')
})

test('a handler that reports a shortfall leaves the koala sorry', async () => {
  const ctx = setup()
  ctx.localContext.location = { verification_status: 'unverified' }
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'calm' })
  await startSession(ctx)

  say(ctx, 'What is the weather')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'sorry')
})

test('how the speaker sounds shows on the koala from the moment the decision arrives until the reply starts', async () => {
  const ctx = setup()
  let release
  api.getLocalContext = () => new Promise((resolve) => { release = () => resolve(WEATHER_CONTEXT) })
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'worried' })
  await startSession(ctx)

  say(ctx, 'What is the weather, I am worried')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'concerned')
  release()
  await flush()
  // The reply is queued but not yet being said, so the reaction is still showing.
  assert.equal(ctx.store.face, 'concerned')
  speak(ctx)

  assert.equal(ctx.store.face, 'listening')
})

test('a reaction still shows when the reply is ready at once, and ends when it starts being spoken', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'worried' })
  await startSession(ctx)

  say(ctx, "I'm worried, what is the weather")
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'concerned')
  speak(ctx)

  assert.equal(ctx.store.face, 'listening')
})

test('speech before the reply is queued does not end a reaction', async () => {
  const ctx = setup()
  api.getLocalContext = () => new Promise(() => {})
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'worried' })
  await startSession(ctx)
  say(ctx, "I'm worried, what is the weather")
  delegate(ctx)
  await flush()

  speak(ctx, 'Let me check that.')

  assert.equal(ctx.store.face, 'concerned')
})

test('a reaction is dropped after two seconds if the reply is slow', async () => {
  const ctx = setup()
  api.getLocalContext = () => new Promise(() => {})
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'frustrated' })
  await startSession(ctx)
  say(ctx, 'Why is this so slow')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'sorry')

  mock.timers.tick(REACTION_MS)

  assert.equal(ctx.store.face, 'thinking')
})

test('a playful reading on a weather question does not make the koala smile', async () => {
  const ctx = setup()
  api.getLocalContext = () => new Promise(() => {})
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9, emotion: 'playful' })
  await startSession(ctx)

  say(ctx, 'ha, what is the weather')
  delegate(ctx)
  await flush()

  assert.notEqual(ctx.store.face, 'happy')
})

function arrangeEmergency(emotion = 'urgent', confidence = 1) {
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence, emotion })
  api.getSafetyGuidance = async () => ({ entries: [], suggested_ids: [], location_conditions_applied: false })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
}

const holdFor = (text) => Math.min(text.trim().split(/\s+/).length * PIN_WORD_MS, PIN_HOLD_MAX_MS)

test('the emergency pin outranks a playful reading', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx, 'd1')
  await flush()
  assert.equal(ctx.store.face, 'serious')

  // A second, playful request while the answer is still being heard cannot lift the pin.
  api.decideVoiceAction = async () => ({ action: 'open_home', confidence: 0.9, emotion: 'playful' })
  say(ctx, 'Haha, take me home')
  delegate(ctx, 'd2')
  await flush()

  assert.equal(ctx.store.face, 'serious')
})

test('speech before the emergency reply is queued does not start the pin releasing', async () => {
  const ctx = setup()
  let releaseGuidance
  api.decideVoiceAction = async () => ({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  api.getSafetyGuidance = () =>
    new Promise((resolve) => {
      releaseGuidance = () => resolve({ entries: [], suggested_ids: [], location_conditions_applied: false })
    })
  api.askSafetyGuidance = async () => ({ status: 'emergency', entry_ids: [] })
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'serious')

  speak(ctx, 'Let me check that.')
  mock.timers.tick(EMERGENCY_RELEASE_MS * 2)
  assert.equal(ctx.store.face, 'serious')

  releaseGuidance()
  await flush()
  assert.equal(ctx.store.face, 'serious')
})

test('the pin is held for as long as the answer takes to say, even if its text arrives at once', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()

  speak(ctx, EMERGENCY_MESSAGE) // all the text at once; the audio takes longer
  mock.timers.tick(EMERGENCY_RELEASE_MS + 100) // quiet for longer than the usual release
  assert.equal(ctx.store.face, 'serious')
  mock.timers.tick(holdFor(EMERGENCY_MESSAGE))

  assert.notEqual(ctx.store.face, 'serious')
})

test('the pin is released once the answer has been said and the assistant has gone quiet', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()

  speak(ctx, EMERGENCY_MESSAGE)
  mock.timers.tick(holdFor(EMERGENCY_MESSAGE) - 1)
  assert.equal(ctx.store.face, 'serious')
  mock.timers.tick(1)

  assert.notEqual(ctx.store.face, 'serious')
})

test('the pin is released by the failsafe even if the assistant never speaks', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()
  assert.equal(ctx.store.face, 'serious')
  const failsafe = Math.max(EMERGENCY_FAILSAFE_MS, holdFor(EMERGENCY_MESSAGE) + PIN_FAILSAFE_MARGIN_MS)

  mock.timers.tick(failsafe - 1)
  assert.equal(ctx.store.face, 'serious')
  mock.timers.tick(1)

  assert.notEqual(ctx.store.face, 'serious')
})

test('saying that again after an emergency is serious again', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx, 'd1')
  await flush()
  speak(ctx, EMERGENCY_MESSAGE)
  mock.timers.tick(holdFor(EMERGENCY_MESSAGE) + EMERGENCY_RELEASE_MS)
  assert.notEqual(ctx.store.face, 'serious')

  api.decideVoiceAction = async () => ({ action: 'repeat_last', confidence: 0.9, emotion: 'calm' })
  say(ctx, 'Say that again')
  delegate(ctx, 'd2')
  await flush()

  assert.equal(ctx.store.face, 'serious')
  assert.equal(commentary(ctx).at(-1).content, EMERGENCY_MESSAGE)
})

test('an emergency reply pins the face even when the model read the speaker as calm', async () => {
  const ctx = setup()
  arrangeEmergency('calm', 0.9)
  await startSession(ctx)

  say(ctx, 'There is smoke and I am trapped')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'serious')
})

test('a stale delegation does not change the face', async () => {
  const ctx = setup()
  const releases = []
  api.decideVoiceAction = () => new Promise((resolve) => releases.push((answer) => resolve(answer)))
  await startSession(ctx)

  say(ctx, 'first')
  delegate(ctx, 'old')
  await flush()
  say(ctx, 'second')
  delegate(ctx, 'new')
  await flush()
  releases[1]({ action: 'read_weather', confidence: 0.9, emotion: 'calm' })
  await flush()
  releases[0]({ action: 'ask_safety_question', confidence: 1, emotion: 'urgent' })
  await flush()

  assert.notEqual(ctx.store.face, 'serious')
})

test('the talking flag follows the assistant speaking and drops shortly after', async () => {
  const ctx = setup()
  await startSession(ctx)
  assert.equal(ctx.store.talking, false)

  speak(ctx)
  assert.equal(ctx.store.talking, true)
  mock.timers.tick(TALK_HOLD_MS - 1)
  assert.equal(ctx.store.talking, true)
  mock.timers.tick(1)

  assert.equal(ctx.store.talking, false)
})

test('closing the session clears the face, the flag and any pin', async () => {
  const ctx = setup()
  arrangeEmergency()
  await startSession(ctx)
  say(ctx, 'The fire is coming, help me')
  delegate(ctx)
  await flush()
  speak(ctx)
  assert.equal(ctx.store.face, 'serious')
  assert.equal(ctx.store.talking, true)

  ctx.fake.onClosed(null)

  assert.equal(ctx.store.face, 'neutral')
  assert.equal(ctx.store.talking, false)
})

test('a decision without an emotion is treated as calm', async () => {
  const ctx = setup()
  api.decideVoiceAction = async () => ({ action: 'read_weather', confidence: 0.9 })
  await startSession(ctx)

  say(ctx, 'weather')
  delegate(ctx)
  await flush()

  assert.equal(ctx.store.face, 'listening')
})

test('dismissing a start error clears it and returns the store to idle', async () => {
  const ctx = setup()
  liveTransport.open = async () => {
    throw new MicrophoneDenied()
  }
  await ctx.store.start({ router: ctx.router })
  assert.equal(ctx.store.status, 'error')

  ctx.store.dismissMessage()

  assert.equal(ctx.store.status, 'idle')
  assert.equal(ctx.store.error, null)
  assert.equal(ctx.store.face, 'neutral')
})

test('dismissing clears the figures notice and leaves a live session running', async () => {
  const ctx = setup()
  await startSession(ctx)
  speak(ctx, 'It is 25 degrees.')
  mock.timers.tick(NUMBER_CHECK_DELAY_MS)
  assert.equal(ctx.store.notice, VOICE_CHECK_FIGURES)

  ctx.store.dismissMessage()

  assert.equal(ctx.store.notice, null)
  assert.equal(ctx.store.status, 'listening')
})

test('the figures notice does not outlive the session', async () => {
  const ctx = setup()
  await startSession(ctx)
  speak(ctx, 'It is 25 degrees.')
  mock.timers.tick(NUMBER_CHECK_DELAY_MS)
  assert.equal(ctx.store.notice, VOICE_CHECK_FIGURES)

  ctx.fake.onClosed(null)

  assert.equal(ctx.store.notice, null)
})
