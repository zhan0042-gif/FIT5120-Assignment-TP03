import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../src/api/client.js'
import { useSafetyGuidanceStore } from '../src/stores/safetyGuidance.js'

const entry = (id) => ({
  id,
  question: `Question ${id}?`,
  answer: 'Answer.',
  source_name: 'CFA',
  source_url: 'https://www.cfa.vic.gov.au/example',
  retrieved_on: '2026-10-05',
})

const response = (ids, suggested = ids, applied = true) => ({
  entries: ids.map(entry),
  suggested_ids: suggested,
  location_conditions_applied: applied,
})

function mockApi(context, method, replacement) {
  const original = api[method]
  api[method] = replacement
  context.after(() => { api[method] = original })
}

test('guidance loads through the backend API', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async (id) => {
    assert.equal(id, 'hh_1')
    return response(['a', 'b', 'c'], ['b', 'a'])
  })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries.map((item) => item.id), ['a', 'b', 'c'])
  assert.deepEqual(store.suggested.map((item) => item.id), ['b', 'a'])
  assert.equal(store.locationConditionsApplied, true)
})

test('a suggested id that is not among the entries is skipped', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a'], ['missing', 'a']))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.deepEqual(store.suggested.map((item) => item.id), ['a'])
})

test('an empty response is a success, not an error', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response([], [], false))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries, [])
  assert.deepEqual(store.suggested, [])
  assert.equal(store.locationConditionsApplied, false)
})

test('a failed request leaves an error and nothing to show', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => { throw new Error('boom') })
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.equal(store.status, 'error')
  assert.deepEqual(store.entries, [])
  assert.match(store.error, /could not be loaded/i)
})

test('loading without a household does not call the API', async (context) => {
  setActivePinia(createPinia())
  let called = false
  mockApi(context, 'getSafetyGuidance', async () => { called = true; return response([]) })
  const store = useSafetyGuidanceStore()

  await store.load(null)

  assert.equal(called, false)
  assert.equal(store.status, 'idle')
})

test('a slow response for an earlier household does not overwrite a later one', async (context) => {
  setActivePinia(createPinia())
  let releaseFirst
  const first = new Promise((resolve) => { releaseFirst = resolve })
  mockApi(context, 'getSafetyGuidance', async (id) => {
    if (id === 'hh_old') {
      await first
      return response(['old'], ['old'], false)
    }
    return response(['new'], ['new'], true)
  })
  const store = useSafetyGuidanceStore()

  const oldLoad = store.load('hh_old')
  await store.load('hh_new')
  releaseFirst()
  await oldLoad

  assert.deepEqual(store.entries.map((item) => item.id), ['new'])
  assert.equal(store.locationConditionsApplied, true)
})

test('loadFor resolves the household first, so a first-time visitor still gets guidance', async (context) => {
  setActivePinia(createPinia())
  let requested = null
  mockApi(context, 'getSafetyGuidance', async (id) => { requested = id; return response(['a']) })
  const store = useSafetyGuidanceStore()

  await store.loadFor(async () => 'hh_created_just_now')

  assert.equal(requested, 'hh_created_just_now')
  assert.equal(store.status, 'success')
  assert.deepEqual(store.entries.map((item) => item.id), ['a'])
})

test('loadFor reports an error when the household cannot be resolved', async (context) => {
  setActivePinia(createPinia())
  let called = false
  mockApi(context, 'getSafetyGuidance', async () => { called = true; return response([]) })
  const store = useSafetyGuidanceStore()

  await store.loadFor(async () => { throw new Error('no household') })

  assert.equal(called, false)
  assert.equal(store.status, 'error')
  assert.match(store.error, /could not be loaded/i)
})

test('asking a suggested question adds the question and then its reviewed answer', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a', 'b']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  const asked = store.ask('b')

  assert.equal(asked, true)
  assert.equal(store.messages.length, 2)
  assert.deepEqual(
    { role: store.messages[0].role, text: store.messages[0].text },
    { role: 'user', text: 'Question b?' },
  )
  assert.deepEqual(
    { role: store.messages[1].role, entryId: store.messages[1].entryId },
    { role: 'assistant', entryId: 'b' },
  )
})

test('asking an id that is not among the entries does nothing', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  const asked = store.ask('gone')

  assert.equal(asked, false)
  assert.deepEqual(store.messages, [])
})

test('asking the same question twice adds it twice, each message with its own id', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')

  store.ask('a')
  store.ask('a')

  assert.equal(store.messages.length, 4)
  assert.equal(new Set(store.messages.map((message) => message.id)).size, 4)
})

test('loading a household clears the earlier conversation', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')
  store.ask('a')

  await store.load('hh_2')

  assert.deepEqual(store.messages, [])
})

test('reset returns the store to its starting state', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a']))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')
  store.ask('a')

  store.reset()

  assert.equal(store.status, 'idle')
  assert.deepEqual(store.entries, [])
  assert.deepEqual(store.suggestedIds, [])
  assert.deepEqual(store.messages, [])
  assert.equal(store.error, null)
})

test('questions that are not suggested are listed as more questions, in file order', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a', 'b', 'c', 'd'], ['c', 'a']))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.deepEqual(store.moreQuestions.map((item) => item.id), ['b', 'd'])
})

test('there are no more questions when every entry is suggested', async (context) => {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(['a', 'b'], ['a', 'b']))
  const store = useSafetyGuidanceStore()

  await store.load('hh_1')

  assert.deepEqual(store.moreQuestions, [])
})

const answer = (status, entryIds = []) => ({ status, entry_ids: entryIds })

// One mock for the whole test, so a test can change the reply without stacking mocks.
function scriptedAsk(context) {
  const state = { reply: null }
  mockApi(context, 'askSafetyGuidance', async () => {
    if (state.reply instanceof Error) throw state.reply
    return state.reply
  })
  return state
}

async function loadedStore(context, ids = ['a', 'b', 'c']) {
  setActivePinia(createPinia())
  mockApi(context, 'getSafetyGuidance', async () => response(ids))
  const store = useSafetyGuidanceStore()
  await store.load('hh_1')
  return store
}

test('a typed question shows the question and then each reviewed answer in order', async (context) => {
  const store = await loadedStore(context)
  mockApi(context, 'askSafetyGuidance', async (id, question) => {
    assert.equal(id, 'hh_1')
    assert.equal(question, 'my own words')
    return answer('matched', ['c', 'a'])
  })

  const sent = await store.askTyped('hh_1', '  my own words  ')

  assert.equal(sent, true)
  assert.deepEqual(
    store.messages.map((message) => message.role === 'user' ? message.text : message.entryId),
    ['my own words', 'c', 'a'],
  )
})

test('ids that are not among the entries are skipped, and all-unknown is no match', async (context) => {
  const store = await loadedStore(context)
  const ask = scriptedAsk(context)

  ask.reply = answer('matched', ['gone', 'b'])
  await store.askTyped('hh_1', 'first')
  assert.deepEqual(store.messages.slice(1).map((message) => message.entryId), ['b'])

  ask.reply = answer('matched', ['gone'])
  await store.askTyped('hh_1', 'second')
  assert.equal(store.messages.at(-1).kind, 'no_match')
})

test('each answer status becomes the right fixed message', async (context) => {
  const store = await loadedStore(context)
  const ask = scriptedAsk(context)

  for (const status of ['no_match', 'emergency', 'unavailable']) {
    ask.reply = answer(status)
    await store.askTyped('hh_1', `question ${status}`)
    assert.equal(store.messages.at(-1).role, 'assistant')
    assert.equal(store.messages.at(-1).kind, status)
  }
})

test('a failed request or an unknown status is shown as unavailable', async (context) => {
  const store = await loadedStore(context)
  const ask = scriptedAsk(context)

  ask.reply = new Error('boom')
  await store.askTyped('hh_1', 'one')
  assert.equal(store.messages.at(-1).kind, 'unavailable')

  ask.reply = answer('something_new')
  await store.askTyped('hh_1', 'two')
  assert.equal(store.messages.at(-1).kind, 'unavailable')
})

test('a blank or over-long question is not sent', async (context) => {
  const store = await loadedStore(context)
  let called = false
  mockApi(context, 'askSafetyGuidance', async () => { called = true; return answer('matched', ['a']) })

  assert.equal(await store.askTyped('hh_1', '   '), false)
  assert.equal(await store.askTyped('hh_1', 'x'.repeat(301)), false)
  assert.equal(called, false)
  assert.deepEqual(store.messages, [])
})

test('nothing is sent without a household', async (context) => {
  const store = await loadedStore(context)
  let called = false
  mockApi(context, 'askSafetyGuidance', async () => { called = true; return answer('matched', ['a']) })

  assert.equal(await store.askTyped(null, 'a question'), false)
  assert.equal(called, false)
})

test('a second question is ignored while one is in flight', async (context) => {
  const store = await loadedStore(context)
  let release
  const gate = new Promise((resolve) => { release = resolve })
  let calls = 0
  mockApi(context, 'askSafetyGuidance', async () => { calls += 1; await gate; return answer('matched', ['a']) })

  const first = store.askTyped('hh_1', 'first')
  assert.equal(store.asking, true)
  const second = store.askTyped('hh_1', 'second')
  // Open the gate before waiting, so a missing guard fails the assertion instead of hanging.
  release()
  assert.equal(await second, false)
  await first

  assert.equal(calls, 1)
  assert.equal(store.asking, false)
})

test('asking is cleared after a failure', async (context) => {
  const store = await loadedStore(context)
  mockApi(context, 'askSafetyGuidance', async () => { throw new Error('boom') })

  await store.askTyped('hh_1', 'one')

  assert.equal(store.asking, false)
})

test('a reply that arrives after the conversation was reset adds nothing', async (context) => {
  const store = await loadedStore(context)
  let release
  const gate = new Promise((resolve) => { release = resolve })
  mockApi(context, 'askSafetyGuidance', async () => { await gate; return answer('matched', ['a']) })

  const pending = store.askTyped('hh_1', 'slow one')
  store.reset()
  release()
  await pending

  assert.deepEqual(store.messages, [])
  assert.equal(store.asking, false)
})
