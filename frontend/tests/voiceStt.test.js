import assert from 'node:assert/strict'
import { test } from 'node:test'

const { createWebSpeechStt, speechRecognitionAvailable } = await import('../src/voice/stt.js')

function fakeScope() {
  const instances = []
  class FakeRecognition {
    constructor() {
      this.starts = 0
      this.stopped = false
      instances.push(this)
    }
    start() { this.starts += 1 }
    stop() { this.stopped = true; this.onend?.() }
  }
  return { scope: { webkitSpeechRecognition: FakeRecognition }, instances }
}

function result(text, isFinal) {
  return Object.assign([{ transcript: text }], { isFinal })
}

function listen(scope) {
  const heard = { interim: [], final: [], errors: [] }
  const stt = createWebSpeechStt(scope)
  stt.start({
    onInterim: (text) => heard.interim.push(text),
    onFinal: (text) => heard.final.push(text),
    onError: (code) => heard.errors.push(code),
  })
  return { stt, heard }
}

test('availability follows either constructor name', () => {
  assert.equal(speechRecognitionAvailable({}), false)
  assert.equal(speechRecognitionAvailable({ webkitSpeechRecognition: class {} }), true)
  assert.equal(speechRecognitionAvailable({ SpeechRecognition: class {} }), true)
})

test('recognition listens continuously in Australian English with interim words', () => {
  const { scope, instances } = fakeScope()
  listen(scope)
  const [recognition] = instances
  assert.deepEqual(
    [recognition.lang, recognition.continuous, recognition.interimResults, recognition.starts],
    ['en-AU', true, true, 1],
  )
})

test('interim and final words are reported trimmed, and empty ones are dropped', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onresult({
    resultIndex: 0,
    results: [result(' scroll ', false), result(' scroll down ', true), result('   ', true)],
  })
  assert.deepEqual(heard.interim, ['scroll'])
  assert.deepEqual(heard.final, ['scroll down'])
})

test('only results from resultIndex onwards are new', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onresult({ resultIndex: 1, results: [result('old', true), result('new', true)] })
  assert.deepEqual(heard.final, ['new'])
})

test('silence and Chrome ending the session on its own restart quietly', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onerror({ error: 'no-speech' })
  instances[0].onend()
  assert.equal(instances[0].starts, 2)
  assert.deepEqual(heard.errors, [])
})

test('a blocked microphone is reported and not retried', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].onerror({ error: 'not-allowed' })
  instances[0].onend()
  assert.deepEqual(heard.errors, ['not-allowed'])
  assert.equal(instances[0].starts, 1)
})

test('stopping ends recognition without a restart', () => {
  const { scope, instances } = fakeScope()
  const { stt } = listen(scope)
  stt.stop()
  assert.equal(instances[0].stopped, true)
  assert.equal(instances[0].starts, 1)
})

test('a restart the browser refuses is reported rather than thrown', () => {
  const { scope, instances } = fakeScope()
  const { heard } = listen(scope)
  instances[0].start = () => { throw new Error('InvalidStateError') }
  instances[0].onend()
  assert.deepEqual(heard.errors, ['restart-failed'])
})
