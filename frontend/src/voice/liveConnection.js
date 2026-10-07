// The browser side of a GPT-Live WebRTC session. Nothing here knows about the app:
// the caller says how to exchange the offer for an answer and what to do with events.
// The microphone and the peer are always released, whether the session ends cleanly,
// the channel drops, or setup fails part-way.

const EVENT_CHANNEL = 'oai-events'
const ICE_TIMEOUT_MS = 10_000
const CLOSE_TIMEOUT_MS = 15_000

export class MicrophoneDenied extends Error {
  constructor() {
    super('Microphone access was blocked.')
    this.name = 'MicrophoneDenied'
  }
}

function browserEnvironment() {
  return {
    createPeer: () => new RTCPeerConnection(),
    getUserMedia: (constraints) => navigator.mediaDevices.getUserMedia(constraints),
    createAudio: () => new Audio(),
    createStream: (track) => new MediaStream([track]),
  }
}

function waitForIce(peer) {
  if (peer.iceGatheringState === 'complete') return Promise.resolve()
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      peer.removeEventListener('icegatheringstatechange', onChange)
      reject(new Error('Timed out while gathering ICE candidates'))
    }, ICE_TIMEOUT_MS)
    function onChange() {
      if (peer.iceGatheringState !== 'complete') return
      clearTimeout(timer)
      peer.removeEventListener('icegatheringstatechange', onChange)
      resolve()
    }
    peer.addEventListener('icegatheringstatechange', onChange)
  })
}

export async function openLiveConnection({ requestAnswer, onEvent, onClosed }, env = browserEnvironment()) {
  const peer = env.createPeer()
  const audio = env.createAudio()
  audio.autoplay = true
  let microphone = null
  let channel = null
  let closeTimer = null
  let finished = false

  function teardown() {
    clearTimeout(closeTimer)
    microphone?.getTracks().forEach((track) => track.stop())
    channel?.close()
    peer.close()
    audio.srcObject = null
  }

  function finish(closedEvent) {
    if (finished) return
    finished = true
    teardown()
    onClosed(closedEvent)
  }

  try {
    peer.addEventListener('track', (event) => {
      audio.srcObject = env.createStream(event.track)
      audio.play?.().catch(() => {})
    })

    try {
      microphone = await env.getUserMedia({ audio: true })
    } catch (error) {
      if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
        throw new MicrophoneDenied()
      }
      throw error
    }
    for (const track of microphone.getAudioTracks()) peer.addTrack(track, microphone)

    channel = peer.createDataChannel(EVENT_CHANNEL)
    channel.addEventListener('message', ({ data }) => {
      let event
      try {
        event = JSON.parse(data)
      } catch {
        return
      }
      onEvent(event)
      if (event?.type === 'session.closed') finish(event)
    })
    channel.addEventListener('close', () => finish(null))

    await peer.setLocalDescription(await peer.createOffer())
    await waitForIce(peer)
    const sdp = peer.localDescription?.sdp
    if (!sdp) throw new Error('Missing local SDP offer')
    const answer = await requestAnswer(sdp)
    await peer.setRemoteDescription({ type: 'answer', sdp: answer })
  } catch (error) {
    finished = true
    teardown()
    throw error
  }

  return {
    send(event) {
      if (channel?.readyState === 'open') channel.send(JSON.stringify(event))
    },
    close() {
      if (finished) return
      if (channel?.readyState !== 'open') {
        finish(null)
        return
      }
      channel.send(JSON.stringify({ type: 'session.close' }))
      closeTimer = setTimeout(() => finish(null), CLOSE_TIMEOUT_MS)
    },
  }
}

// The store calls this object, so a test can swap `open` for a fake.
export const liveTransport = { open: openLiveConnection }
