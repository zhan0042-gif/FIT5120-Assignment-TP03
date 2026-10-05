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
