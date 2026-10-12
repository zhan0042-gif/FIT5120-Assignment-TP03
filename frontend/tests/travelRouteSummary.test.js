import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { importComponent } from './helpers/loadComponent.js'

const ROUTES = [
  { status: 'available', destination_type: 'primary', destination_id: 'd1', destination_name: "Relative's House", distance_m: 22_400, travel_time_seconds: 1_860 },
  { status: 'unavailable', destination_type: 'backup', destination_id: 'd2', destination_name: 'Community Centre', distance_m: null, travel_time_seconds: null },
]

async function render(routes) {
  const TravelRouteSummary = await importComponent('../src/components/scenario/TravelRouteSummary.vue')
  return renderToString(createSSRApp(TravelRouteSummary, { routes }))
}

test('each destination shows its name, distance and driving time as text', async () => {
  const html = await render(ROUTES)

  assert.match(html, /Road routes/)
  assert.match(html, /Relative&#39;s House/)
  assert.match(html, /22\.4 km, about 31 min by road/)
})

test('a destination with no route says so rather than showing numbers', async () => {
  const html = await render(ROUTES)

  assert.match(html, /Community Centre[\s\S]*no road route available/)
})

test('it says routes are distances and times only, never safety', async () => {
  const html = await render(ROUTES)

  assert.match(html, /do not say whether a route is safe/)
})

test('nothing is shown when there are no routes', async () => {
  const html = await render([])

  assert.doesNotMatch(html, /Road routes/)
})

test('the Travel Readiness page shows the summary from the routes it loads', async () => {
  const view = await readFile(new URL('../src/views/TravelReadinessView.vue', import.meta.url), 'utf8')

  assert.match(view, /import TravelRouteSummary from '\.\.\/components\/scenario\/TravelRouteSummary\.vue'/)
  assert.match(view, /<TravelRouteSummary :routes="routeStore\.result\?\.routes \?\? \[\]" \/>/)
})
