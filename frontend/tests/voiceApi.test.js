import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

const { api } = await import('../src/api/client.js')

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

function stubFetch(payload) {
  const calls = []
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  return calls
}

test('createLiveSession posts the offer under the household', async () => {
  const calls = stubFetch({ session: { id: 'live_1' }, transport: { type: 'webrtc', sdp: 'answer' } })

  const result = await api.createLiveSession('hh_1', 'offer-sdp')

  assert.equal(calls[0].url, '/api/v1/households/hh_1/live/sessions')
  assert.equal(calls[0].init.method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].init.body), { sdp: 'offer-sdp' })
  assert.equal(result.transport.sdp, 'answer')
})

test('decideVoiceAction posts the utterance and labels with snake_case keys', async () => {
  const calls = stubFetch({ action: 'read_weather', confidence: 0.9 })

  const result = await api.decideVoiceAction('hh_1', {
    utterance: 'weather',
    page: 'overview',
    lastReadout: 'fire history',
  })

  assert.equal(calls[0].url, '/api/v1/households/hh_1/live/decide')
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    utterance: 'weather',
    page: 'overview',
    last_readout: 'fire history',
  })
  assert.equal(result.action, 'read_weather')
})

test('the household id is URL encoded', async () => {
  const calls = stubFetch({ action: 'none', confidence: 0 })

  await api.decideVoiceAction('a/b', { utterance: 'x', page: '', lastReadout: '' })

  assert.equal(calls[0].url, '/api/v1/households/a%2Fb/live/decide')
})
