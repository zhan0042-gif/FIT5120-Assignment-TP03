import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { afterEach, test } from 'node:test'
import { createPinia } from 'pinia'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { importComponent } from './helpers/loadComponent.js'

globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }

const { useVoiceStore } = await import('../src/stores/voice.js')
const { MINIMIZED_KEY, bubbleFor, forcesOpen, isBusy, isLive, labelFor } = await import(
  '../src/voice/koalaControls.js'
)

const hadWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const hadNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
const hadStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')

afterEach(() => {
  if (hadWindow) Object.defineProperty(globalThis, 'window', hadWindow)
  else delete globalThis.window
  if (hadNavigator) Object.defineProperty(globalThis, 'navigator', hadNavigator)
  else delete globalThis.navigator
  Object.defineProperty(globalThis, 'localStorage', hadStorage)
})

function supportMicrophone() {
  Object.defineProperty(globalThis, 'window', {
    value: { RTCPeerConnection: class {} },
    configurable: true,
    writable: true,
  })
  Object.defineProperty(globalThis, 'navigator', {
    value: { mediaDevices: { getUserMedia() {} } },
    configurable: true,
    writable: true,
  })
}

function useStorage(value) {
  Object.defineProperty(globalThis, 'localStorage', { value, configurable: true, writable: true })
}

const KEEP_STORAGE = Symbol('keep the storage the test file set up')

async function render({ status = 'idle', error = null, notice = null, talking = false, storage = KEEP_STORAGE } = {}) {
  const KoalaAssistant = await importComponent('../src/components/layout/KoalaAssistant.vue')
  const pinia = createPinia()
  // The stores read localStorage when they are created, so build them first; the storage the
  // component itself sees is swapped in just before it renders.
  const store = useVoiceStore(pinia)
  store.status = status
  store.error = error
  store.notice = notice
  if (talking) store.talking = true
  if (storage !== KEEP_STORAGE) useStorage(storage)
  const router = createRouter({ history: createMemoryHistory(), routes: [] })
  return renderToString(createSSRApp(KoalaAssistant).use(pinia).use(router))
}

// ---- pure helpers

test('live is listening or working; busy is connecting or ending', () => {
  assert.equal(isLive('listening'), true)
  assert.equal(isLive('checking'), true)
  assert.equal(isLive('idle'), false)
  assert.equal(isBusy('connecting'), true)
  assert.equal(isBusy('closing'), true)
  assert.equal(isBusy('listening'), false)
})

test('the button is named for what pressing it does', () => {
  assert.equal(labelFor('idle'), 'Talk to the assistant')
  assert.equal(labelFor('error'), 'Talk to the assistant')
  assert.equal(labelFor('listening'), 'Stop voice')
  assert.equal(labelFor('checking'), 'Stop voice')
})

test('the bubble says an error first, then the figures notice, then the status', () => {
  assert.deepEqual(bubbleFor({ supported: true, status: 'error', error: 'No mic.', notice: 'Check.' }), { text: 'No mic.', role: 'alert' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'listening', error: null, notice: 'Check.' }), { text: 'Check.', role: 'alert' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'listening', error: null, notice: null }), { text: 'Listening…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'idle', error: null, notice: null }), { text: 'Talk to me', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'connecting', error: null, notice: null }), { text: 'Connecting…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'checking', error: null, notice: null }), { text: 'Checking…', role: 'status' })
  assert.deepEqual(bubbleFor({ supported: true, status: 'closing', error: null, notice: null }), { text: 'Ending voice…', role: 'status' })
})

test('without microphone support the bubble says voice is not available in this browser', () => {
  assert.deepEqual(bubbleFor({ supported: false, status: 'idle', error: null, notice: null }), {
    text: "Voice isn't available in this browser.",
    role: 'status',
  })
})

test('anything that must stay visible keeps the koala open', () => {
  assert.equal(forcesOpen({ status: 'idle', error: null, notice: null }), false)
  assert.equal(forcesOpen({ status: 'listening', error: null, notice: null }), true)
  assert.equal(forcesOpen({ status: 'connecting', error: null, notice: null }), true)
  assert.equal(forcesOpen({ status: 'idle', error: 'No mic.', notice: null }), true)
  assert.equal(forcesOpen({ status: 'idle', error: null, notice: 'Check.' }), true)
})

// ---- rendering

test('the koala is a button named for its action, in the bubble it says it will talk', async () => {
  supportMicrophone()

  const html = await render()

  assert.match(html, /<button[^>]*class="koala-button"/)
  assert.match(html, /aria-label="Talk to the assistant"/)
  assert.match(html, /aria-pressed="false"/)
  assert.match(html, /Talk to me/)
  assert.match(html, /data-face="neutral"/)
})

test('while listening the button stops voice and shows the listening face', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening' })

  assert.match(html, /aria-label="Stop voice"/)
  assert.match(html, /aria-pressed="true"/)
  assert.match(html, /data-face="listening"/)
  assert.match(html, /Listening…/)
})

test('the button is disabled while connecting and while ending', async () => {
  supportMicrophone()

  for (const status of ['connecting', 'closing']) {
    assert.match(await render({ status }), /class="koala-button"[^>]*disabled/, status)
  }
})

test('a start error shows in the bubble as an alert and the button can be pressed again', async () => {
  supportMicrophone()

  const html = await render({ status: 'error', error: 'Microphone access was blocked. You can still use the chat.' })

  assert.match(html, /role="alert"[^>]*>Microphone access was blocked/)
  assert.doesNotMatch(html, /class="koala-button"[^>]*disabled/)
})

test('the figures notice is an alert in the bubble', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening', notice: 'Please check the figures on screen.' })

  assert.match(html, /role="alert"[^>]*>Please check the figures on screen\./)
})

test('without microphone support the button is disabled and says why', async () => {
  const html = await render()

  assert.match(html, /class="koala-button"[^>]*disabled/)
  assert.match(html, /Voice isn&#39;t available in this browser\./)
})

test('the koala shows the talking mouth while the assistant speaks', async () => {
  supportMicrophone()

  const html = await render({ status: 'listening', talking: true })

  assert.match(html, /data-talking="true"/)
})

// ---- minimising

test('a stored minimised koala is a small button that brings it back', async () => {
  supportMicrophone()

  const html = await render({
    storage: { getItem: (key) => (key === MINIMIZED_KEY ? '1' : null), setItem() {}, removeItem() {} },
  })

  assert.match(html, /aria-label="Show the assistant"/)
  assert.doesNotMatch(html, /class="koala-button"/)
})

test('an open koala offers to be hidden', async () => {
  supportMicrophone()

  assert.match(await render(), /aria-label="Hide the assistant"/)
})

test('a minimised koala opens by itself while voice is on, so it can be stopped', async () => {
  supportMicrophone()

  const html = await render({
    status: 'listening',
    storage: { getItem: () => '1', setItem() {}, removeItem() {} },
  })

  assert.match(html, /class="koala-button"/)
  assert.doesNotMatch(html, /aria-label="Hide the assistant"/)
})

test('a minimised koala opens by itself to show an error or the figures notice', async () => {
  supportMicrophone()
  const storage = { getItem: () => '1', setItem() {}, removeItem() {} }

  assert.match(await render({ status: 'error', error: 'No mic.', storage }), /role="alert"[^>]*>No mic\./)
  assert.match(
    await render({ status: 'idle', notice: 'Check the figures.', storage }),
    /role="alert"[^>]*>Check the figures\./,
  )
})

test('storage that throws does not break the component', async () => {
  supportMicrophone()

  const html = await render({
    storage: {
      getItem() {
        throw new Error('blocked')
      },
      setItem() {
        throw new Error('blocked')
      },
      removeItem() {},
    },
  })

  assert.match(html, /class="koala-button"/)
})

test('missing storage does not break the component either', async () => {
  supportMicrophone()

  assert.match(await render({ storage: undefined }), /class="koala-button"/)
})

// ---- layout

test('the layout renders the koala, no longer renders the dock, and leaves room for it', async () => {
  const layout = await readFile(new URL('../src/components/layout/AppLayout.vue', import.meta.url), 'utf8')

  assert.match(layout, /import KoalaAssistant from '\.\/KoalaAssistant\.vue'/)
  assert.match(layout, /<KoalaAssistant \/>/)
  assert.doesNotMatch(layout, /VoiceDock/)
  assert.match(layout, /padding-bottom: *calc\(/)
})
