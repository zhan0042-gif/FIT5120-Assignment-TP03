import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'

const { createPinia, setActivePinia } = await import('pinia')
const { api } = await import('../src/api/client.js')
const { registerTargets, resetVoiceRegistry } = await import('../src/voice/registry.js')
const { NONE_OF_THESE, NO_SPAN } = await import('../src/voice/questions.js')
const { addressTarget, buttonTarget, pageTarget, textTarget } = await import('../src/voice/targets.js')
const { isStopPhrase, useVoiceStore } = await import('../src/stores/voice.js')

const originalJudge = api.judgeVoiceCommand
const originalLog = api.logVoiceTurn
let logs
let current

beforeEach(() => {
  logs = []
  api.logVoiceTurn = async (record) => {
    logs.push(record)
    return { accepted: true }
  }
})

afterEach(() => {
  current?.endSession()
  current = null
  api.judgeVoiceCommand = originalJudge
  api.logVoiceTurn = originalLog
  resetVoiceRegistry()
})

const a = (id, answer, probability) => ({ id, answer, probability })
const NO_STOP = a('stop', 'no', 0.95)
const flush = () => new Promise((resolve) => setImmediate(resolve))
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// The judge replies in order, one reply per call. An Error reply is thrown.
function judgeReplies(...replies) {
  const calls = []
  api.judgeVoiceCommand = async (batch) => {
    calls.push(batch)
    const reply = replies.shift()
    if (reply instanceof Error) throw reply
    return { answers: reply }
  }
  return calls
}

function begin(options = {}) {
  setActivePinia(createPinia())
  const store = useVoiceStore()
  const stt = {
    handlers: null,
    stopped: false,
    start(handlers) { this.handlers = handlers },
    stop() { this.stopped = true },
  }
  store.startSession({ createStt: () => stt, ...options })
  current = store
  return { store, stt, say: (text) => stt.handlers.onFinal(text) }
}

const fireMap = (counter) =>
  pageTarget({ id: 'page-map', label: 'Fire Map', go: () => { counter.visits += 1 } })

const removeMinh = (counter) => buttonTarget({
  id: 'm1-remove', label: 'Remove member Minh', confirm: true, press: () => { counter.presses += 1 },
})

const RESULTS = ['12 Smith St, Ballarat VIC 3350', '12 Smith Rd, Sale VIC 3850']
const destination = (place) => addressTarget({
  id: 'address-1',
  label: 'Primary destination address',
  current: place.text,
  setText: (value) => { place.text = value; place.searched = true },
  suggestions: () => (place.searched ? place.results : []),
  choose: (index) => { place.chosen = index },
})
const ADDRESS_COMMAND = [a('command', 'enter the address for Primary destination address', 0.95), NO_STOP]

test('stop phrases are matched exactly, ignoring trailing punctuation', () => {
  assert.equal(isStopPhrase('Stop.'), true)
  assert.equal(isStopPhrase(' cancel '), true)
  assert.equal(isStopPhrase('stop listening!'), true)
  assert.equal(isStopPhrase('stop the car'), false)
})

test('a session listens until it is ended', () => {
  const { store, stt } = begin()
  assert.equal(store.status, 'listening')
  store.endSession()
  assert.equal(store.status, 'idle')
  assert.equal(stt.stopped, true)
})

test('interim words are shown but never judged', () => {
  const calls = judgeReplies()
  const { store, stt } = begin()
  stt.handlers.onInterim('go to')
  assert.equal(store.interim, 'go to')
  assert.equal(calls.length, 0)
})

test('a confident command is carried out and logged once, by target id', async () => {
  const counter = { visits: 0 }
  registerTargets(() => [fireMap(counter)])
  judgeReplies([a('command', 'go to Fire Map', 0.95), NO_STOP])
  const { store, say } = begin()

  await say('go to fire map')
  await flush()

  assert.equal(counter.visits, 1)
  assert.equal(store.status, 'listening')
  assert.equal(store.message, '✓ Go to Fire Map')
  assert.equal(logs.length, 1)
  assert.deepEqual(
    [logs[0].decision, logs[0].outcome, logs[0].mode, logs[0].transcript],
    ['execute', 'ok', 'normal', 'go to fire map'],
  )
  assert.deepEqual(logs[0].answers[0], { id: 'command', answer: 'page-map', probability: 0.95 })
  assert.deepEqual(logs[0].action, { kind: 'page', target: 'page-map', value: null })
})

test('saying stop ends the session without asking the judge', async () => {
  const calls = judgeReplies()
  const { store, stt, say } = begin()
  await say('Stop.')
  await flush()
  assert.equal(calls.length, 0)
  assert.equal(store.status, 'idle')
  assert.equal(stt.stopped, true)
  assert.deepEqual(logs.map((log) => log.decision), ['stop'])
})

test('stop while a command is being judged means it is never carried out', async () => {
  const counter = { visits: 0 }
  registerTargets(() => [fireMap(counter)])
  let release
  api.judgeVoiceCommand = () => new Promise((resolve) => { release = resolve })
  const { store, say } = begin()

  const pending = say('go to fire map')
  await say('stop')
  release({ answers: [a('command', 'go to Fire Map', 0.95), NO_STOP] })
  await pending

  assert.equal(counter.visits, 0)
  assert.equal(store.status, 'idle')
})

test('while one command is judged, only the newest utterance waits its turn', async () => {
  const heard = []
  let release
  api.judgeVoiceCommand = (batch) => {
    heard.push(batch.state.transcript)
    if (heard.length === 1) return new Promise((resolve) => { release = resolve })
    return Promise.resolve({ answers: [a('command', NONE_OF_THESE, 0.9), NO_STOP] })
  }
  const { say } = begin()

  const first = say('first')
  say('second')
  say('third')
  release({ answers: [a('command', NONE_OF_THESE, 0.9), NO_STOP] })
  await first

  assert.deepEqual(heard, ['first', 'third'])
})

test('an important action waits for yes', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  const calls = judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'yes', 0.95), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  assert.equal(store.status, 'confirming')
  assert.equal(store.prompt, 'Press Remove member Minh? Say yes or no.')
  assert.equal(counter.presses, 0)

  await say('yes')
  await flush()
  assert.equal(counter.presses, 1)
  assert.equal(store.status, 'listening')
  assert.deepEqual(calls[1].questions.map((question) => question.id), ['confirm', 'stop'])
  assert.deepEqual(logs.map((log) => log.decision), ['confirm', 'execute'])
})

test('no drops the held action', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'no', 0.95), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  await say('no')

  assert.equal(counter.presses, 0)
  assert.equal(store.status, 'listening')
  assert.equal(store.message, 'Cancelled. Nothing was changed.')
})

test('an unclear answer is asked once more, then dropped', async () => {
  const counter = { presses: 0 }
  registerTargets(() => [removeMinh(counter)])
  judgeReplies(
    [a('command', 'press Remove member Minh', 0.97), NO_STOP],
    [a('confirm', 'no', 0.3), NO_STOP],
    [a('confirm', 'no', 0.3), NO_STOP],
  )
  const { store, say } = begin()

  await say('remove Minh')
  await say('hmm')
  assert.equal(store.status, 'confirming')
  assert.match(store.prompt, /^Please say yes or no\./)

  await say('hmm')
  assert.equal(store.status, 'listening')
  assert.equal(counter.presses, 0)
})

test('a value the judge could not lift is dictated and written exactly as heard', async () => {
  let name = ''
  registerTargets(() => [textTarget({
    id: 'm2-name', label: 'Name (member 2)', current: name, set: (value) => { name = value },
  })])
  const calls = judgeReplies([a('command', 'fill in Name (member 2)', 0.95), a('span', NO_SPAN, 0.9), NO_STOP])
  const { store, say } = begin()

  await say('fill in the name')
  assert.equal(store.status, 'dictating')
  assert.equal(store.prompt, 'What should I enter for Name (member 2)?')

  await say('Lan Nguyen')
  assert.equal(name, 'Lan Nguyen')
  assert.equal(calls.length, 1)
  assert.equal(store.status, 'listening')
})

test('dictation that would replace something already typed asks first', async () => {
  // The judge may pick the wrong row ("fill in the name" with two members);
  // the dictated value must not silently rename Minh.
  let name = 'Minh'
  registerTargets(() => [textTarget({
    id: 'm1-name', label: 'Name (Minh)', current: name, set: (value) => { name = value },
  })])
  judgeReplies(
    [a('command', 'fill in Name (Minh)', 0.72), a('span', NO_SPAN, 0.9), NO_STOP],
    [a('confirm', 'yes', 0.95), NO_STOP],
  )
  const { store, say } = begin()

  await say('fill in the name')
  await say('Lan Nguyen')
  assert.equal(name, 'Minh')
  assert.equal(store.status, 'confirming')
  assert.equal(store.prompt, 'Fill in Name (Minh) with “Lan Nguyen”? Say yes or no.')

  await say('yes')
  assert.equal(name, 'Lan Nguyen')
})

test('recognition punctuation at the end of dictation does not reach the plan', async () => {
  let name = ''
  registerTargets(() => [textTarget({
    id: 'm2-name', label: 'Name (member 2)', current: name, set: (value) => { name = value },
  })])
  judgeReplies([a('command', 'fill in Name (member 2)', 0.95), a('span', NO_SPAN, 0.9), NO_STOP])
  const { say } = begin()

  await say('fill in the name')
  await say('Lan Nguyen.')
  assert.equal(name, 'Lan Nguyen')
})

test('a dictated address that would replace one already entered asks first', async () => {
  // Replacing an address clears its verification; the judge may have picked
  // the wrong row, so this waits for yes like any other overwrite.
  const place = { text: '1 Old Road', searched: false, results: RESULTS, chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(
    ADDRESS_COMMAND,
    [a('confirm', 'yes', 0.95), NO_STOP],
  )
  const { store, say } = begin({ suggestionWaitMs: 500 })

  await say('primary destination')
  await say('12 smith road sale')
  assert.equal(place.text, '1 Old Road')
  assert.equal(store.status, 'confirming')
  assert.equal(store.prompt, 'Enter “12 smith road sale” for Primary destination address? Say yes or no.')

  await say('yes')
  assert.equal(place.text, '12 smith road sale')
  assert.equal(store.status, 'choosing')
  assert.deepEqual(store.suggestions, RESULTS)
})

test('a spoken address is typed as heard, then a numbered suggestion is chosen', async () => {
  const place = { text: '', searched: false, results: RESULTS, chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND, [a('suggestion', '2 second: 12 Smith Rd, Sale VIC 3850', 0.95), NO_STOP])
  const { store, say } = begin({ suggestionWaitMs: 500 })

  await say('primary destination')
  assert.equal(store.status, 'dictating')
  assert.equal(store.prompt, 'Say the address for Primary destination address.')

  await say('12 smith road sale')
  assert.equal(place.text, '12 smith road sale')
  assert.equal(store.status, 'choosing')
  assert.deepEqual(store.suggestions, RESULTS)

  await say('the second one')
  assert.equal(place.chosen, 1)
  assert.equal(store.message, '✓ Chose 12 Smith Rd, Sale VIC 3850')
})

test('saying none keeps the address as typed and unverified', async () => {
  const place = { text: '', searched: false, results: RESULTS, chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND, [a('suggestion', 'none', 0.95), NO_STOP])
  const { store, say } = begin({ suggestionWaitMs: 500 })

  await say('primary destination')
  await say('12 smith road sale')
  await say('none of them')

  assert.equal(place.chosen, null)
  assert.equal(place.text, '12 smith road sale')
  assert.equal(store.message, 'The address is kept as entered. It is not verified.')
})

test('with no suggestions the address stays as typed and unverified', async () => {
  const place = { text: '', searched: false, results: [], chosen: null }
  registerTargets(() => [destination(place)])
  judgeReplies(ADDRESS_COMMAND)
  const { store, say } = begin({ suggestionWaitMs: 250 })

  await say('primary destination')
  await say('somewhere unknown')

  assert.equal(store.status, 'listening')
  assert.equal(place.text, 'somewhere unknown')
  assert.match(store.message, /not verified/)
})

test('one failed turn keeps listening; a second in a row ends the session', async () => {
  judgeReplies(new Error('503'), new Error('503'))
  const { store, say } = begin()

  await say('go to fire map')
  assert.equal(store.status, 'listening')
  assert.equal(store.message, 'Voice commands are unavailable right now.')

  await say('go to fire map')
  assert.equal(store.status, 'idle')
})

test('a target that disappears while the judge answers is not acted on', async () => {
  const counter = { visits: 0 }
  const unregister = registerTargets(() => [fireMap(counter)])
  api.judgeVoiceCommand = async () => {
    unregister()
    return { answers: [a('command', 'go to Fire Map', 0.95), NO_STOP] }
  }
  const { store, say } = begin()

  await say('go to fire map')
  await flush()

  assert.equal(counter.visits, 0)
  assert.equal(store.message, 'That’s no longer on this page.')
  assert.equal(logs[0].outcome, 'fail')
})

test('an overlong utterance is refused without asking the judge', async () => {
  const calls = judgeReplies()
  const { store, say } = begin()
  await say('word '.repeat(120))
  assert.equal(calls.length, 0)
  assert.equal(store.message, 'That was too long. Try a shorter command.')
})

test('silence ends the session', async () => {
  const { store } = begin({ silenceMs: 30 })
  await sleep(80)
  assert.equal(store.status, 'idle')
})

test('a blocked microphone ends the session with a way forward', () => {
  const { store, stt } = begin()
  stt.handlers.onError('not-allowed')
  assert.equal(store.status, 'idle')
  assert.equal(store.message, 'Microphone blocked — allow it in your browser settings.')
})
