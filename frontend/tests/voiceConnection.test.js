import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'

const { MicrophoneDenied, openLiveConnection } = await import('../src/voice/liveConnection.js')

afterEach(() => mock.timers.reset())

class FakeChannel {
  constructor(label) {
    this.label = label
    this.readyState = 'open'
    this.sent = []
    this.listeners = {}
  }
  addEventListener(type, listener) {
    ;(this.listeners[type] ??= []).push(listener)
  }
  send(data) {
    this.sent.push(JSON.parse(data))
  }
  close() {
    this.readyState = 'closed'
  }
  emit(type, event = {}) {
    for (const listener of this.listeners[type] ?? []) listener(event)
  }
}

class FakePeer {
  constructor() {
    this.listeners = {}
    this.iceGatheringState = 'complete'
    this.tracks = []
    this.closed = false
    this.remote = null
  }
  addEventListener(type, listener) {
    ;(this.listeners[type] ??= []).push(listener)
  }
  removeEventListener() {}
  addTrack(track, stream) {
    this.tracks.push([track, stream])
  }
  createDataChannel(label) {
    this.channel = new FakeChannel(label)
    return this.channel
  }
  async createOffer() {
    return { type: 'offer', sdp: 'raw-offer' }
  }
  async setLocalDescription() {
    this.localDescription = { sdp: 'offer-sdp' }
  }
  async setRemoteDescription(description) {
    this.remote = description
  }
  close() {
    this.closed = true
  }
}

function makeEnv({ getUserMedia } = {}) {
  const peer = new FakePeer()
  const track = { stopped: false, stop() { this.stopped = true } }
  const stream = { getAudioTracks: () => [track], getTracks: () => [track] }
  const audio = { srcObject: 'set', autoplay: false }
  return {
    peer,
    track,
    audio,
    env: {
      createPeer: () => peer,
      getUserMedia: getUserMedia ?? (async () => stream),
      createAudio: () => audio,
      createStream: (remoteTrack) => ({ remoteTrack }),
    },
  }
}

test('open requests the microphone, adds the track, and exchanges the offer for the answer', async () => {
  const { peer, env } = makeEnv()
  const offers = []

  const connection = await openLiveConnection(
    { requestAnswer: async (sdp) => (offers.push(sdp), 'answer-sdp'), onEvent() {}, onClosed() {} },
    env,
  )

  assert.equal(peer.tracks.length, 1)
  assert.equal(peer.channel.label, 'oai-events')
  assert.deepEqual(offers, ['offer-sdp'])
  assert.deepEqual(peer.remote, { type: 'answer', sdp: 'answer-sdp' })
  assert.equal(typeof connection.send, 'function')
})

test('events from the data channel are parsed and forwarded, and junk is ignored', async () => {
  const { peer, env } = makeEnv()
  const events = []
  await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent: (event) => events.push(event), onClosed() {} },
    env,
  )

  peer.channel.emit('message', { data: JSON.stringify({ type: 'session.started' }) })
  peer.channel.emit('message', { data: 'not json' })

  assert.deepEqual(events, [{ type: 'session.started' }])
})

test('session.closed tears everything down and reports the closing event once', async () => {
  const { peer, track, audio, env } = makeEnv()
  const closed = []
  await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent() {}, onClosed: (event) => closed.push(event) },
    env,
  )

  const finalEvent = { type: 'session.closed', reason: 'close_requested', usage: { seconds: 12 } }
  peer.channel.emit('message', { data: JSON.stringify(finalEvent) })
  peer.channel.emit('close')

  assert.deepEqual(closed, [finalEvent])
  assert.equal(track.stopped, true)
  assert.equal(peer.closed, true)
  assert.equal(audio.srcObject, null)
})

test('a channel that closes without a session.closed reports null', async () => {
  const { peer, env } = makeEnv()
  const closed = []
  await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent() {}, onClosed: (event) => closed.push(event) },
    env,
  )

  peer.channel.emit('close')

  assert.deepEqual(closed, [null])
})

test('send writes JSON while the channel is open and does nothing otherwise', async () => {
  const { peer, env } = makeEnv()
  const connection = await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent() {}, onClosed() {} },
    env,
  )

  connection.send({ type: 'session.commentary.append', content: 'hi' })
  peer.channel.readyState = 'closed'
  connection.send({ type: 'ignored' })

  assert.deepEqual(peer.channel.sent, [{ type: 'session.commentary.append', content: 'hi' }])
})

test('close asks for a graceful close and gives up after fifteen seconds', async () => {
  mock.timers.enable({ apis: ['setTimeout'] })
  const { peer, env } = makeEnv()
  const closed = []
  const connection = await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent() {}, onClosed: (event) => closed.push(event) },
    env,
  )

  connection.close()
  assert.deepEqual(peer.channel.sent, [{ type: 'session.close' }])
  assert.deepEqual(closed, [])

  mock.timers.tick(15_000)

  assert.deepEqual(closed, [null])
  assert.equal(peer.closed, true)
})

test('a blocked microphone throws MicrophoneDenied and closes the peer without calling onClosed', async () => {
  const denied = Object.assign(new Error('blocked'), { name: 'NotAllowedError' })
  const { peer, env } = makeEnv({ getUserMedia: async () => { throw denied } })
  let closedCalls = 0

  await assert.rejects(
    openLiveConnection({ requestAnswer: async () => 'a', onEvent() {}, onClosed: () => closedCalls++ }, env),
    (error) => error instanceof MicrophoneDenied && error.name === 'MicrophoneDenied',
  )
  assert.equal(peer.closed, true)
  assert.equal(closedCalls, 0)
})

test('another microphone error is rethrown unchanged', async () => {
  const missing = Object.assign(new Error('none'), { name: 'NotFoundError' })
  const { env } = makeEnv({ getUserMedia: async () => { throw missing } })

  await assert.rejects(
    openLiveConnection({ requestAnswer: async () => 'a', onEvent() {}, onClosed() {} }, env),
    (error) => error === missing,
  )
})

test('a failed answer request stops the microphone and rethrows', async () => {
  const { peer, track, env } = makeEnv()

  await assert.rejects(
    openLiveConnection(
      { requestAnswer: async () => { throw new Error('429') }, onEvent() {}, onClosed() {} },
      env,
    ),
    /429/,
  )
  assert.equal(track.stopped, true)
  assert.equal(peer.closed, true)
})

test('close stops the microphone straight away, before the session confirms it has closed', async () => {
  mock.timers.enable({ apis: ['setTimeout'] })
  const { peer, track, env } = makeEnv()
  const closed = []
  const connection = await openLiveConnection(
    { requestAnswer: async () => 'a', onEvent() {}, onClosed: (event) => closed.push(event) },
    env,
  )

  connection.close()

  assert.equal(track.stopped, true)
  assert.deepEqual(closed, [])
  assert.deepEqual(peer.channel.sent, [{ type: 'session.close' }])
})
