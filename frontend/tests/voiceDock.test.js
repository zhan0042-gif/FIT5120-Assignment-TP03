import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { createPinia } from 'pinia'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { importComponent } from './helpers/loadComponent.js'

// The household store reads localStorage when it is created; give it an in-memory one.
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} }

const { useVoiceStore } = await import('../src/stores/voice.js')

const Page = { render: () => null }

async function render({ route = '/map', status = 'idle', notice = null }) {
  const VoiceDock = await importComponent('../src/components/layout/VoiceDock.vue')
  const pinia = createPinia()
  const store = useVoiceStore(pinia)
  store.status = status
  store.notice = notice
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/overview', name: 'overview', component: Page },
      { path: '/safety-insights', name: 'safety-insights', component: Page },
      { path: '/map', name: 'fire-map', component: Page },
      { path: '/scenarios', name: 'scenario-tester', component: Page },
    ],
  })
  await router.push(route)
  await router.isReady()
  return renderToString(createSSRApp(VoiceDock).use(pinia).use(router))
}

test('nothing is shown while voice is off', async () => {
  const html = await render({ status: 'idle' })

  assert.doesNotMatch(html, /Stop voice/)
  assert.doesNotMatch(html, /Voice is on/)
})

test('a live session shows its status and a stop button on a page without the chat', async () => {
  const html = await render({ route: '/map', status: 'listening' })

  assert.match(html, /Voice is on/)
  assert.match(html, /Stop voice/)
})

test('the dock stays out of the way on Safety Insights, where the chat has its own control', async () => {
  const html = await render({ route: '/safety-insights', status: 'listening' })

  assert.doesNotMatch(html, /Stop voice/)
})

test('the check-the-figures notice is shown as an alert on any page', async () => {
  const html = await render({
    route: '/scenarios',
    status: 'checking',
    notice: 'Please check the figures on screen.',
  })

  assert.match(html, /role="alert"[^>]*>Please check the figures on screen\./)
})

test('the stop button is disabled while the session is ending', async () => {
  const html = await render({ route: '/map', status: 'closing' })

  assert.match(html, /Stop voice/)
  assert.match(html, /disabled/)
})

test('the layout renders the dock', async () => {
  const layout = await readFile(new URL('../src/components/layout/AppLayout.vue', import.meta.url), 'utf8')

  assert.match(layout, /import VoiceDock from '\.\/VoiceDock\.vue'/)
  assert.match(layout, /<VoiceDock \/>/)
})
