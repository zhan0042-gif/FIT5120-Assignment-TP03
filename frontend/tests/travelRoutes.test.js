import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'
import { api } from '../src/api/client.js'
import { useTravelRoutesStore } from '../src/stores/travelRoutes.js'
import { useTravelDisruptionsStore } from '../src/stores/travelDisruptions.js'
import { buildTravelMapData } from '../src/utils/travelMapData.js'
import { drawTravelRoutes, travelRouteGeometry } from '../src/utils/travelRouteMap.js'

const route = (type = 'primary', id = 'p') => ({
  status: 'available', destination_type: type, destination_id: id, destination_name: id,
  origin: { latitude: -37.8, longitude: 145 }, destination: { latitude: -37.9, longitude: 145.1 },
  geometry: [{ latitude: -37.8, longitude: 145 }, { latitude: -37.81, longitude: 145.07 }, { latitude: -37.9, longitude: 145.1 }],
})
const plan = { arrangements: {
  primary_destination: { destination_id: 'p', display_name: 'Primary', latitude: -37.9, longitude: 145.1, verification_status: 'verified' },
  backup_arrangements: [1, 2].map((index) => ({ destination: {
    destination_id: `b${index}`, display_name: `Backup ${index}`, latitude: -37.9 - index * .01, longitude: 145.1, verification_status: 'verified',
  } })),
} }

function mockApi(context, method, replacement) {
  const original = api[method]
  api[method] = replacement
  context.after(() => { api[method] = original })
}

test('travel routes load through the backend API and preserve every destination route', async (context) => {
  setActivePinia(createPinia())
  const expected = { status: 'available', routes: [route(), route('backup', 'b1'), route('backup', 'b2')] }
  mockApi(context, 'getTravelRoutes', async (id) => { assert.equal(id, 'hh_1'); return expected })
  const store = useTravelRoutesStore()
  await store.load('hh_1')
  assert.equal(store.status, 'available')
  assert.deepEqual(store.result, expected)
})

test('route partial/unavailable/not-applicable responses leave disruption state intact', async (context) => {
  setActivePinia(createPinia())
  const disruptions = useTravelDisruptionsStore()
  disruptions.result = { status: 'available', primary_destination: { disruptions: [{ disruption_id: 'current' }] } }
  disruptions.status = 'success'
  const saved = JSON.parse(JSON.stringify({ result: disruptions.result, status: disruptions.status }))
  const store = useTravelRoutesStore()
  let response
  mockApi(context, 'getTravelRoutes', async () => response)
  for (const status of ['partial', 'unavailable', 'not_applicable']) {
    response = { status, routes: status === 'partial' ? [route()] : [] }
    await store.load('hh_1')
    assert.equal(store.status, status === 'partial' ? 'partial' : 'unavailable')
    assert.deepEqual({ result: disruptions.result, status: disruptions.status }, saved)
  }
})

test('HTTP route failure removes stale lines only, and missing household never calls API', async (context) => {
  setActivePinia(createPinia())
  let calls = 0
  mockApi(context, 'getTravelRoutes', async () => { calls++; throw new Error('failure') })
  const store = useTravelRoutesStore()
  store.result = { status: 'available', routes: [route()] }
  await store.load('hh_1')
  assert.equal(store.status, 'unavailable')
  assert.equal(store.result, null)
  await store.load(null)
  assert.equal(calls, 1)
})

test('older requests and reset cannot overwrite the latest route state', async (context) => {
  setActivePinia(createPinia())
  let resolveOld
  mockApi(context, 'getTravelRoutes', (id) => id === 'old'
    ? new Promise((resolve) => { resolveOld = resolve }) : Promise.resolve({ status: 'unavailable', routes: [] }))
  const store = useTravelRoutesStore()
  const old = store.load('old')
  await store.load('new')
  resolveOld({ status: 'available', routes: [route()] })
  await old
  assert.equal(store.status, 'unavailable')
  const resetRequest = store.load('old')
  store.reset()
  resolveOld({ status: 'available', routes: [route()] })
  await resetRequest
  assert.equal(store.status, 'idle')
  assert.equal(store.result, null)
})

test('API calls only the FIREBREAK travel-routes endpoint with the encoded household ID', async (context) => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/households/hh%2F1/travel-routes')
    assert.equal(options.method, undefined)
    return { ok: true, status: 200, json: async () => ({ status: 'available', routes: [] }) }
  }
  context.after(() => { globalThis.fetch = originalFetch })
  assert.equal((await api.getTravelRoutes('hh/1')).status, 'available')
})

test('route geometry rejects missing/invalid points and remote outliers without joining across them', () => {
  assert.deepEqual(travelRouteGeometry(route()), [[-37.8, 145], [-37.81, 145.07], [-37.9, 145.1]])
  for (const geometry of [null, [], [route().geometry[0]], [route().geometry[0], { latitude: NaN, longitude: 145 }],
    [route().geometry[0], { latitude: 95, longitude: 145 }], [route().geometry[0], { latitude: 0, longitude: 0 }]]) {
    assert.equal(travelRouteGeometry({ ...route(), geometry }), null)
  }
  assert.equal(travelRouteGeometry({ ...route(), status: 'unavailable' }), null)
})

test('verified destination markers and 10 km circles survive provider failures independently', () => {
  for (const status of ['unavailable', 'not_applicable']) {
    const mapped = buildTravelMapData({ status }, plan)
    assert.equal(mapped.destinations.length, 3)
    assert.deepEqual(mapped.destinations.map((item) => item.search_radius_km), [10, 10, 10])
  }
  const unverified = structuredClone(plan)
  unverified.arrangements.backup_arrangements[0].destination.verification_status = 'unverified'
  assert.equal(buildTravelMapData(null, unverified).destinations.length, 2)
})

// Native map calls are mocked, not the route rendering helper. This mounts the
// actual Vue map component using an in-memory renderer with no browser/page.
function mapStub() {
  const state = { map: null, groups: [], fitted: [], polylines: [], failLine: false }
  function item(kind, positions, options) {
    return { kind, positions, options,
      addTo(layer) {
        layer.entries.push(this)
        if (kind === 'polyline' && state.failLine) throw new Error('route layer unavailable')
        return this
      }, bindPopup(content) { this.popup = content; return this },
    }
  }
  const L = {
    divIcon: (value) => value,
    map: () => (state.map = { entries: [], removed: false,
      fitBounds(bounds) { state.fitted.push([...bounds.points]) }, invalidateSize() {},
      removeLayer(layer) { this.entries = this.entries.filter((entry) => entry !== layer) },
      remove() { this.removed = true },
    }),
    maplibreGL: () => ({ addTo() {} }),
    latLngBounds: () => ({ points: [], extend(value) {
      this.points.push(...(value.points ?? [value])); return this
    }, isValid() { return this.points.length > 0 } }),
    latLng: (point) => ({ toBounds: () => ({ points: [point] }) }),
    layerGroup: () => {
      const layer = { entries: [], addTo() { return this }, clearLayers() { this.entries = [] },
        hasLayer(entry) { return this.entries.includes(entry) }, removeLayer(entry) { this.entries = this.entries.filter((value) => value !== entry) } }
      state.groups.push(layer)
      return layer
    },
    circle: (position, options) => item('circle', position, options),
    circleMarker: (position, options) => item('destination', position, options),
    marker: (position, options) => item('marker', position, options),
    polyline: (geometry, options) => {
      const line = item('polyline', geometry, options)
      state.polylines.push(line)
      return line
    },
  }
  return { L, state }
}

async function compiledMap() {
  const url = new URL('../src/components/scenario/TravelDisruptionMap.vue', import.meta.url)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: 'travel-map-integration', inlineTemplate: true }).content
  code = code.replace(/^import ['"][^'"]+['"]\s*$/gm, '')
  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    const target = name === 'leaflet' ? 'data:text/javascript,export default globalThis.__travelLeaflet'
      : name.startsWith('.') ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href : import.meta.resolve(name)
    code = code.replace(match[0], `from '${target}'`)
  }
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)).default
}

const element = () => ({ children: [], props: {}, style: {}, append(...items) { this.children.push(...items) } })
const renderer = createRenderer({
  createElement: element, createText: (text) => ({ text }), createComment: (text) => ({ text }),
  insert(child, parent, anchor) {
    child.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index >= 0) parent.children.splice(index, 0, child)
    else parent.children.push(child)
  },
  remove(node) {
    if (node.parent) node.parent.children = node.parent.children.filter((child) => child !== node)
  },
  setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text },
  parentNode: (node) => node.parent, nextSibling: (node) => node.parent?.children[node.parent.children.indexOf(node) + 1] ?? null, patchProp: (node, key, old, value) => { node.props[key] = value },
})

test('mounted map renders primary and all backups from TomTom points; failures isolate route layers', async (context) => {
  const { L, state } = mapStub()
  const originals = Object.fromEntries(['document', 'requestAnimationFrame', 'cancelAnimationFrame', '__travelLeaflet'].map((name) => [name, globalThis[name]]))
  globalThis.__travelLeaflet = L
  globalThis.document = { createElement: element }
  globalThis.requestAnimationFrame = () => 1
  globalThis.cancelAnimationFrame = () => {}
  context.after(() => {
    for (const [name, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[name]
      else globalThis[name] = value
    }
  })
  const Map = await compiledMap()
  const props = reactive({ destinations: buildTravelMapData(null, plan).destinations,
    disruptions: [{ disruption_id: 'incident', latitude: -37.89, longitude: 145.08 }],
    householdLocation: { latitude: -37.8, longitude: 145, address: 'Home' },
    routes: [route(), route('backup', 'b1'), route('backup', 'b2')] })
  const app = renderer.createApp({ render: () => h(Map, props) })
  app.mount(element())
  const [base, routes] = state.groups
  assert.equal(routes.entries.length, 3)
  assert.deepEqual(routes.entries.map((line) => line.options.color), ['#2563eb', '#00857a', '#00857a'])
  assert.deepEqual(routes.entries[0].positions, [[-37.8, 145], [-37.81, 145.07], [-37.9, 145.1]])
  assert.equal(base.entries.filter((item) => item.kind === 'destination').length, 3)
  assert.equal(base.entries.filter((item) => item.kind === 'circle' && item.options.radius === 10000).length, 3)
  assert.equal(base.entries.filter((item) => item.options.title === 'Reported road disruption').length, 1)
  assert.ok(state.map.entries.some((item) => item.options?.title === 'Your home'))
  assert.ok(state.fitted.at(-1).some((point) => point[0] === -37.81 && point[1] === 145.07))
  state.failLine = true
  props.routes = [route()]
  await nextTick()
  assert.equal(routes.entries.length, 0)
  assert.equal(state.map.removed, false)
  assert.equal(base.entries.length, 7)
  assert.ok(state.map.entries.some((item) => item.options?.title === 'Your home'))
  props.routes = [{ ...route(), geometry: null }]
  await nextTick()
  assert.equal(state.map.removed, false)
  props.routes = []
  await nextTick()
  assert.equal(base.entries.length, 7)
  assert.equal(state.fitted.at(-1).length, 5)
  app.unmount()
})

test('route legend and semantic disclaimer clearly keep route lines separate from disruptions', async () => {
  const page = await readFile(new URL('../src/views/TravelReadinessView.vue', import.meta.url), 'utf8')
  const map = await readFile(new URL('../src/components/scenario/TravelDisruptionMap.vue', import.meta.url), 'utf8')
  assert.match(map, /Primary route/)
  assert.match(map, /Backup route/)
  assert.match(map, /10 km search area/)
  assert.match(page, /not currently matched against the route/)
  assert.match(page, /do not necessarily mean your evacuation route is blocked or unsafe/)
  assert.doesNotMatch(page, /routeStore.status === 'available'[\s\S]*?<TravelDisruptionPanel/)
})
