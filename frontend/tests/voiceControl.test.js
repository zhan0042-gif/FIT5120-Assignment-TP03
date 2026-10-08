import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { afterEach, test } from 'node:test'
import { createPinia } from 'pinia'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { importComponent } from './helpers/loadComponent.js'

// The household store reads localStorage when it is created; give it an in-memory one.
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }

const { useVoiceStore } = await import('../src/stores/voice.js')
const { VOICE_PRIVACY_NOTE } = await import('../src/utils/voiceCopy.js')

const hadWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const hadNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')

afterEach(() => {
  if (hadWindow) Object.defineProperty(globalThis, 'window', hadWindow)
  else delete globalThis.window
  if (hadNavigator) Object.defineProperty(globalThis, 'navigator', hadNavigator)
  else delete globalThis.navigator
})

// Pretend to be a browser that can capture a microphone.
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

async function render(arrange) {
  const VoiceControl = await importComponent('../src/components/overview/VoiceControl.vue')
  const pinia = createPinia()
  arrange(useVoiceStore(pinia))
  const router = createRouter({ history: createMemoryHistory(), routes: [] })
  return renderToString(createSSRApp(VoiceControl).use(pinia).use(router))
}

test('nothing is shown where the browser cannot capture a microphone', async () => {
  const html = await render(() => {})

  assert.doesNotMatch(html, /Talk to the assistant/)
  assert.doesNotMatch(html, /OpenAI/)
})

test('an idle control offers to start and says the audio goes to OpenAI', async () => {
  supportMicrophone()

  const html = await render(() => {})

  assert.match(html, /Talk to the assistant/)
  assert.match(html, /aria-pressed="false"/)
  assert.match(html, /Voice is off\./)
  // The page escapes apostrophes, so compare with the same escaping.
  assert.ok(html.includes(VOICE_PRIVACY_NOTE.replaceAll("'", '&#39;')))
  assert.doesNotMatch(html, /disabled/)
})

test('a live control offers to stop', async () => {
  supportMicrophone()

  const html = await render((store) => {
    store.status = 'listening'
  })

  assert.match(html, /Stop voice/)
  assert.match(html, /aria-pressed="true"/)
  assert.match(html, /Listening\./)
})

test('the button is disabled while connecting and while closing', async () => {
  supportMicrophone()

  for (const status of ['connecting', 'closing']) {
    const html = await render((store) => {
      store.status = status
    })

    assert.match(html, /disabled/, status)
  }
})

test('a start failure message replaces the status line', async () => {
  supportMicrophone()

  const html = await render((store) => {
    store.status = 'error'
    store.error = 'Microphone access was blocked. You can still use the chat.'
  })

  assert.match(html, /Microphone access was blocked/)
  assert.match(html, /Talk to the assistant/)
})

test('the check-the-figures notice is an alert', async () => {
  supportMicrophone()

  const html = await render((store) => {
    store.status = 'listening'
    store.notice = 'Please check the figures on screen.'
  })

  assert.match(html, /role="alert"[^>]*>Please check the figures on screen\./)
})

test('the safety chat panel shows the voice control above the typed question form', async () => {
  const panel = await readFile(
    new URL('../src/components/overview/SafetyChatPanel.vue', import.meta.url),
    'utf8',
  )

  assert.match(panel, /import VoiceControl from '\.\/VoiceControl\.vue'/)
  assert.match(panel, /<VoiceControl \/>\s*<form class="ask-form"/)
})

test('the privacy note says what leaves the site: the audio and what the assistant reads aloud, names included', () => {
  assert.match(VOICE_PRIVACY_NOTE, /microphone audio/)
  assert.match(VOICE_PRIVACY_NOTE, /OpenAI/)
  assert.match(VOICE_PRIVACY_NOTE, /reads aloud/)
  assert.match(VOICE_PRIVACY_NOTE, /names/)
  assert.match(VOICE_PRIVACY_NOTE, /street addresses/)
})
