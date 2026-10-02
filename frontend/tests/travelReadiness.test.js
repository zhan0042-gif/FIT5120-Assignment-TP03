import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createPinia } from 'pinia'
import { useHouseholdStore } from '../src/stores/household.js'
import { useTravelDisruptionsStore } from '../src/stores/travelDisruptions.js'
import { buildTravelMapData } from '../src/utils/travelMapData.js'
import {
  coreDisruptionDescription,
  travelPlaceText,
  disruptionDetails,
  travelLocationPopup,
  travelDisruptionPopup,
  destinationAddress,
  disruptionStatus,
  dedupeDestinationDisruptions,
  travelDestinationGroups,
  uncheckedDestinations,
} from '../src/utils/travelReadinessPresentation.js'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')

const result = {
  status: 'available',
  primary_destination: {
    destination_id: 'primary', destination_name: 'Primary', latitude: -37.8,
    longitude: 145, search_radius_km: 10, disruptions: [
      { disruption_id: 'with-point', latitude: -37.81, longitude: 145.01, road_name: 'Example Road' },
      { disruption_id: 'without-point', latitude: null, longitude: null, road_name: 'Another Road' },
    ],
  },
  backup_destinations: [{
    destination_id: 'backup', destination_name: 'Backup', latitude: -37.9,
    longitude: 145.1, search_radius_km: 10, disruptions: [
      { disruption_id: 'with-point', latitude: -37.81, longitude: 145.01, road_name: 'Example Road' },
    ],
  }],
}

test('Travel Readiness has its own route and ordered navigation entry', async () => {
  const router = await source('../src/router/index.js')
  const layout = await source('../src/components/layout/AppLayout.vue')
  assert.match(router, /path: '\/travel-readiness',[\s\S]*?name: 'travel-readiness'/)
  assert.match(layout, /to="\/map">Fire Map<\/router-link>[\s\S]*?to="\/travel-readiness">Travel Readiness<\/router-link>[\s\S]*?to="\/scenarios">Test My Plan<\/router-link>/)
})

test('map data includes primary and backup destinations but only located disruptions', () => {
  const mapped = buildTravelMapData(result)
  assert.deepEqual(mapped.destinations.map((item) => item.type), ['Primary destination', 'Backup destination'])
  assert.deepEqual(mapped.disruptions.map((item) => item.disruption_id), ['with-point'])
  assert.equal(result.primary_destination.disruptions.length, 2)
  assert.deepEqual(buildTravelMapData({ status: 'unavailable' }), { destinations: [], disruptions: [] })
  assert.deepEqual(buildTravelMapData({
    status: 'available',
    primary_destination: { latitude: null, longitude: null, search_radius_km: 10 },
  }).destinations, [])
})

test('map reuses the Fire Map base style and renders markers and search circles independently', async () => {
  const map = await source('../src/components/scenario/TravelDisruptionMap.vue')
  const page = await source('../src/views/TravelReadinessView.vue')
  assert.match(map, /L\.map\(container\.value\)/)
  assert.match(map, /L\.maplibreGL\(\{ style: openFreeMapStyle/)
  assert.match(map, /L\.circle\(position,[\s\S]*?search_radius_km \* 1000/)
  assert.equal((map.match(/L\.circleMarker\(position/g) ?? []).length, 1)
  assert.match(map, /L\.marker\(position, \{ icon: disruptionIcon/)
  assert.match(map, /bounds\.extend\(L\.latLng\(position\)\.toBounds\(destination\.search_radius_km \* 2000\)\)/)
  assert.match(map, /map\.fitBounds\(bounds/)
  assert.match(map, /mapError\.value = true/)
  assert.match(page, /<TravelDisruptionMap[\s\S]*?:destinations="mapData\.destinations"[\s\S]*?:disruptions="mapData\.disruptions"/)
  assert.doesNotMatch(page + map, /historical-fire-points|useFireMapStore|loadFirePoints/)
})

test('results and unavailable states stay in the moved panel, outside the map', async () => {
  const page = await source('../src/views/TravelReadinessView.vue')
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  const scenarios = await source('../src/views/ScenarioTesterView.vue')
  assert.match(page, /<TravelDisruptionPanel \/>/)
  assert.match(panel, /travelDestinationGroups\(result\.value\)/)
  assert.match(panel, /destinationAddress\(destination\)/)
  assert.match(panel, /v-for="disruption in destination\.disruptions"/)
  assert.match(panel, /disruptionStatus\(disruption\)/)
  assert.match(panel, /result\.status === 'unavailable'/)
  assert.match(panel, /Check again/)
  assert.doesNotMatch(scenarios, /TravelDisruptionPanel|useTravelDisruptionsStore/)
  assert.match(scenarios, /<RendezvousPanel/)
  assert.match(scenarios, /<TestResultPanel/)
})

test('desktop uses a map-led two-column layout and mobile stacks results', async () => {
  const page = await source('../src/views/TravelReadinessView.vue')
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  assert.match(page, /class="travel-layout"[\s\S]*?class="map-section"[\s\S]*?class="results-column"[\s\S]*?<TravelDisruptionPanel \/>/)
  assert.match(page, /grid-template-columns: minmax\(0, 11fr\) minmax\(19rem, 9fr\)/)
  assert.doesNotMatch(page, /\.results-column \{[^}]*(max-height|overflow-y|scrollbar-gutter)/)
  assert.match(page, /@media \(max-width: 1100px\)[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/)
  assert.match(panel, /<h2>Reported disruptions<\/h2>[\s\S]*?@click="loadDisruptions"/)
  assert.doesNotMatch(panel, /Travel disruption awareness|<p class="eyebrow">Travel readiness/)
  assert.match(panel, /overflow-wrap: anywhere/)
})

test('destination summaries preserve labels, one address and counts without repeating the radius', async () => {
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  assert.deepEqual(travelDestinationGroups(result).map((item) => item.type), ['Primary destination', 'Backup destination'])
  assert.match(panel, /destination\.destination_name/)
  assert.match(panel, /destinationAddress\(destination\)/)
  assert.match(panel, /destination\.active_disruption_count/)
  assert.match(panel, /No nearby disruptions reported\./)
  assert.doesNotMatch(panel, /Reported within|reported within|radius-note/)
  assert.equal(destinationAddress({ destination_name: '71 B Hateleys Road, Arapiles VIC 3409', destination_address: '71 B Hateleys Road, Arapiles VIC 3409' }), '')
  assert.equal(destinationAddress({ destination_name: 'gr', destination_address: '71 B Hateleys Road, Arapiles VIC 3409' }), '71 B Hateleys Road, Arapiles VIC 3409')
})

test('disruption cards retain every required field in human reading order', async () => {
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  const card = panel.slice(panel.indexOf('<article'), panel.indexOf('</article>'))
  const fields = ['event_subtype', 'distance_km', 'road_name', 'disruptionStatus(disruption)', 'disruptionDetails(disruption)', 'last_updated']
  const positions = fields.map((field) => card.indexOf(field))
  assert.ok(positions.every((position) => position >= 0))
  assert.deepEqual(positions, [...positions].sort((a, b) => a - b))
  assert.match(panel, /v-for="disruption in destination\.disruptions"/)
  assert.doesNotMatch(panel, /Phone:|Email:|Contact:/)
})

test('impact and direction form a readable status without inventing missing values', () => {
  assert.equal(disruptionStatus({ impact: 'Road closed', direction: 'Both directions' }), 'Road closed in both directions.')
  assert.equal(disruptionStatus({ impact: 'Road closed', direction: 'Southbound' }), 'Road closed southbound.')
  assert.equal(disruptionStatus({ impact: 'direction: Both directions; impactType: Changed conditions' }), 'Changed conditions reported in both directions.')
  assert.equal(disruptionStatus({ impact: 'Changed conditions' }), 'Changed conditions reported.')
  assert.equal(disruptionStatus({ direction: 'Northbound' }), 'Conditions reported northbound.')
  assert.equal(disruptionStatus({ impact: 'Lane closure', direction: 'Inbound' }), 'Lane closure (Inbound).')
})

test('presentation removes contact suffixes while preserving the source record', () => {
  const disruption = { description: 'Kirwans Bridge CLOSED due to bridge damage. Further details contact Strathbogie Shire. Phone: 1800 000 000 Email: roads@example.org' }
  assert.equal(coreDisruptionDescription(disruption.description), 'Kirwans Bridge CLOSED due to bridge damage.')
  assert.match(disruption.description, /Phone: 1800 000 000 Email:/)
  assert.equal(coreDisruptionDescription('Please avoid the area. Further details: Strathbogie Shire 03 5555 5555'), 'Please avoid the area.')
  assert.equal(coreDisruptionDescription('Contact: 03 5555 5555'), '')
})

test('unverified primary and backup destinations receive explanations without false zero results', async () => {
  const plan = { arrangements: {
    primary_destination: { destination_id: 'p', display_name: 'Primary', verification_status: 'unverified', latitude: null, longitude: null },
    backup_arrangements: [
      { destination: { destination_id: 'b1', display_name: 'Backup 1', verification_status: 'verified', latitude: -37.8, longitude: 145 } },
      { destination: { destination_id: 'b2', display_name: 'Backup 2', verification_status: 'unverified', latitude: null, longitude: null } },
    ],
  } }
  assert.deepEqual(uncheckedDestinations(plan).map((destination) => [destination.type, destination.destination_name]), [
    ['Primary destination', 'Primary'], ['Backup destination', 'Backup 2'],
  ])
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  const uncheckedSection = panel.slice(panel.indexOf('class="unchecked-results"'))
  assert.match(uncheckedSection, /does not have verified coordinates/)
  assert.doesNotMatch(uncheckedSection, /active_disruption_count|No nearby disruptions reported/)
})

test('provider unavailable remains explicit, and map/list rendering stays independent', async () => {
  const page = await source('../src/views/TravelReadinessView.vue')
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  assert.match(panel, /result\.status === 'unavailable'[\s\S]*?Road-disruption information unavailable/)
  assert.match(page, /<TravelDisruptionMap[\s\S]*?<\/section>[\s\S]*?<TravelDisruptionPanel/)
  assert.match(page, /v-if="mapData\.destinations\.length \|\| householdLocation"/)
  assert.match(panel, /result\.status === 'available'/)
  assert.match(page, /void householdStore\.loadPlan\(\)/)
})

test('map and page colors use theme tokens for surfaces in both themes', async () => {
  const page = await source('../src/views/TravelReadinessView.vue')
  const map = await source('../src/components/scenario/TravelDisruptionMap.vue')
  assert.match(page, /background: var\(--color-bg-card\)/)
  assert.match(page, /color: var\(--color-text-muted\)/)
  assert.match(map, /background: var\(--color-bg-card-muted\)/)
  assert.match(map, /border: 1px solid var\(--color-border\)/)
})

test('dedupe keeps the newest update per destination without mutating provider data', () => {
  const old = {
    disruption_id: 'old', road_name: 'Example Road', event_type: 'Hazard',
    event_subtype: 'Road damage', description: 'Bridge damaged. Further details contact Council.',
    latitude: -37.81, longitude: 145.01, last_updated: '2026-10-01T01:00:00Z',
  }
  const newest = { ...old, disruption_id: 'new', description: 'Bridge damaged. Phone: 03 5555 5555', last_updated: '2026-10-01T03:00:00+00:00' }
  const invalidDate = { ...old, disruption_id: 'invalid', last_updated: 'invalid' }
  const input = { ...result, primary_destination: { ...result.primary_destination, active_disruption_count: 3, disruptions: [newest, old, invalidDate] },
    backup_destinations: [{ ...result.backup_destinations[0], disruptions: [old] }] }
  const groups = travelDestinationGroups(input)
  assert.deepEqual(groups.map((group) => group.disruptions.map((item) => item.disruption_id)), [['new'], ['old']])
  assert.deepEqual(groups.map((group) => group.active_disruption_count), [1, 1])
  assert.deepEqual(buildTravelMapData({ ...input, backup_destinations: [] }).disruptions, [newest])
  assert.equal(input.primary_destination.disruptions.length, 3)
  assert.equal(input.primary_destination.active_disruption_count, 3)
  assert.deepEqual(dedupeDestinationDisruptions([old, newest]), [newest])
})

test('dedupe retains different incidents on one road and sparse unidentified records', () => {
  const base = { disruption_id: 'base', road_name: 'Same Road', event_type: 'Hazard', description: 'Bridge damaged.', latitude: -37.8, longitude: 145 }
  const distinct = [
    base,
    { ...base, disruption_id: 'other-segment', latitude: -37.9 },
    { ...base, disruption_id: 'other-type', event_type: 'Works' },
    { ...base, disruption_id: 'other-description', description: 'Tree fallen.' },
    { ...base, disruption_id: 'other-direction', direction: 'Southbound' },
    { disruption_id: 'sparse-one', road_name: 'Same Road' },
    { disruption_id: 'sparse-two', road_name: 'Same Road' },
    {}, {},
  ]
  assert.equal(dedupeDestinationDisruptions(distinct).length, distinct.length)
  assert.equal(dedupeDestinationDisruptions([
    { ...base, latitude: null, longitude: null },
    { ...base, disruption_id: 'new', latitude: null, longitude: null, last_updated: '2026-10-01T00:00:00Z' },
  ])[0].disruption_id, 'new')
  assert.deepEqual(travelDestinationGroups({ status: 'not_applicable' }), [])
  assert.deepEqual(travelDestinationGroups({ status: 'available' }), [])
})

test('status and description strip API syntax and unnecessary contact information', () => {
  assert.equal(disruptionStatus({ impact: 'impactType: No Blockage; direction: Both directions' }), 'No blockage reported. Proceed with caution.')
  assert.equal(disruptionStatus({ event_subtype: 'Road damage' }), 'Road damage reported.')
  assert.equal(disruptionStatus({}), '')
  assert.equal(coreDisruptionDescription('Road damaged Further details contact Council'), 'Road damaged')
  assert.equal(coreDisruptionDescription('Road closed. Email: roads@example.org'), 'Road closed.')
  assert.equal(coreDisruptionDescription('Road closed. Contact organisation: Council'), 'Road closed.')
  assert.equal(coreDisruptionDescription('Phone: 1800 000 000'), '')
  assert.equal(coreDisruptionDescription('Road closed. roads@example.org'), 'Road closed.')
  assert.equal(coreDisruptionDescription('Road closed. 03 5555 5555'), 'Road closed.')
})

test('home and disruption use distinct icons and the fixed 10 km legend', async () => {
  const map = await source('../src/components/scenario/TravelDisruptionMap.vue')
  const page = await source('../src/views/TravelReadinessView.vue')
  assert.match(map, /10 km search area/)
  assert.doesNotMatch(map, /Search radius|Reported within|disruption\.impact/)
  assert.match(map, /icon: homeIcon, title: 'Your home'/)
  assert.match(map, /travelLocationPopup\('Your home', null, props\.householdLocation\.address\)/)
  assert.match(map, /iconSize: \[36, 36\]/)
  assert.match(map, /watch\(\(\) => props\.householdLocation, updateHomeMarker\)/)
  assert.match(page, /api\.getLocation\(householdId\)/)
  assert.match(page, /:household-location="householdLocation"/)
  assert.match(page, /disruptionStore\.load\(householdId, 10\)/)
  assert.doesNotMatch(page, /useFireMapStore|loadContext|loadFirePoints/)
  assert.match(page, /Nearby reported disruptions do not necessarily mean your evacuation route is blocked or unsafe/)
})

// Compile actual Vue templates without opening a page. Leaflet is stubbed for SSR.
async function loadComponent(path) {
  const url = new URL(path, import.meta.url)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: path, inlineTemplate: true }).content
  code = code.replace(/^import ['"][^'"]+['"]\s*$/gm, '')
  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    let resolved
    if (name === 'leaflet') {
      resolved = 'data:text/javascript,export default { divIcon: value => value }'
    } else if (name.endsWith('.vue')) {
      resolved = await loadComponent(new URL(name, url).href)
    } else {
      resolved = name.startsWith('.')
        ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href
        : import.meta.resolve(name)
    }
    code = code.replace(match[0], `from '${resolved}'`)
  }
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

test('rendered cards show newest records, clean text, corrected counts and all result states', async (context) => {
  const originalStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: () => null }
  context.after(() => {
    if (originalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = originalStorage
  })
  const { default: Panel } = await import(await loadComponent('../src/components/scenario/TravelDisruptionPanel.vue'))
  const pinia = createPinia()
  const household = useHouseholdStore(pinia)
  const store = useTravelDisruptionsStore(pinia)
  household.planStatus = 'success'
  store.status = 'success'
  const old = { disruption_id: 'old', road_name: 'MCDONALDS ROAD', event_type: 'HAZARD',
    event_subtype: 'ROAD DAMAGE', description: 'BRIDGE DAMAGE ON MCDONALDS ROAD. Further details contact Council.',
    latitude: -37.81, longitude: 145.01, distance_km: 2,
    impact: 'impactType: No Blockage', last_updated: '2026-10-01T01:00:00Z' }
  store.result = { ...result, disclaimer: 'Nearby disruptions do not mean your route is blocked or unsafe.',
    primary_destination: { ...result.primary_destination, destination_address: '12 RIVER STREET NAGAMBIE VIC 3608', active_disruption_count: 2,
      disruptions: [old, { ...old, disruption_id: 'new', distance_km: 1.5, last_updated: '2026-10-02T01:00:00Z' }] },
    backup_destinations: [] }
  const render = () => renderToString(createSSRApp(Panel).use(pinia))
  const html = await render()
  assert.equal((html.match(/class="disruption-item"/g) ?? []).length, 1)
  assert.match(html, /1 disruption/)
  assert.match(html, /1.5 km away/)
  assert.match(html, /No blockage reported\. Proceed with caution\./)
  assert.match(html, /Bridge damage on Mcdonalds Road/)
  assert.match(html, /Mcdonalds Road/)
  assert.match(html, /Road Damage/)
  assert.match(html, /12 River Street Nagambie VIC 3608/)
  assert.doesNotMatch(html, /MCDONALDS ROAD|ROAD DAMAGE|RIVER STREET/)
  assert.match(html, /Updated/)
  assert.match(html, /route is blocked or unsafe/)
  assert.doesNotMatch(html, /impactType|Further details|Council|within.*10 km|2.0 km away/)
  store.result = { status: 'available', primary_destination: { ...result.primary_destination, disruptions: [] } }
  assert.match(await render(), /No nearby disruptions reported\./)
  store.result = { status: 'unavailable' }
  assert.match(await render(), /Road-disruption information unavailable/)
  store.result = { status: 'not_applicable' }
  assert.match(await render(), /Destination information needed/)
  household.plan = { arrangements: { primary_destination: { destination_id: 'unchecked', display_name: 'dsssg', address: '34 H VOGELS ROAD WATCHEM WEST VIC 3482' } } }
  const uncheckedHtml = await render()
  assert.match(uncheckedHtml, /cannot be checked/)
  assert.match(uncheckedHtml, /34 H Vogels Road Watchem West VIC 3482/)
})

test('rendered map legend names home, destinations, disruption and the 10 km area', async () => {
  const { default: Map } = await import(await loadComponent('../src/components/scenario/TravelDisruptionMap.vue'))
  const html = await renderToString(createSSRApp(Map, {
    destinations: [], disruptions: [], householdLocation: { latitude: -37.8, longitude: 145, address: 'Home address' },
  }))
  for (const label of ['Primary destination', 'Backup destination', 'Your home', 'Reported disruption', '10 km search area']) {
    assert.ok(html.includes(label))
  }
  assert.doesNotMatch(html, /Search radius|Reported within/)
})


test('place casing preserves mixed casing, state codes, postcodes and address components', () => {
  const examples = [
    ['MCDONALDS ROAD', 'Mcdonalds Road'],
    ['KIRWANS BRIDGE ROAD', 'Kirwans Bridge Road'],
    ['MCLEOD STREET', 'Mcleod Street'],
    ['12 RIVER STREET NAGAMBIE VIC 3608', '12 River Street Nagambie VIC 3608'],
    ['34 H VOGELS ROAD WATCHEM WEST VIC 3482', '34 H Vogels Road Watchem West VIC 3482'],
    ['12A RIVER STREET VIC 3608', '12A River Street VIC 3608'],
    ['M1 - PRINCES HIGHWAY', 'M1 - Princes Highway'],
    ["O'NEILL ROAD", "O'Neill Road"],
    ['McLeod Street', 'McLeod Street'],
    ['VIC NSW ACT QLD SA WA NT TAS', 'VIC NSW ACT QLD SA WA NT TAS'],
    [null, ''], ['', ''],
  ]
  for (const [input, expected] of examples) assert.equal(travelPlaceText(input), expected)
  assert.equal(destinationAddress({ destination_name: 'River home', destination_address: examples[3][0] }), examples[3][1])
  assert.equal(destinationAddress({ destination_name: '12 River Street Nagambie VIC 3608', destination_address: examples[3][0] }), '')
})

test('details sentence-case uppercase prose but preserve mixed prose, road references and abbreviations', () => {
  const incident = { road_name: 'KIRWANS BRIDGE ROAD', description: 'KIRWANS BRIDGE ROAD CLOSED IN VIC. SES ON SITE. Further details contact Council.' }
  assert.equal(disruptionDetails(incident), 'Kirwans Bridge Road closed in VIC. SES on site.')
  assert.match(incident.description, /KIRWANS BRIDGE ROAD CLOSED/)
  assert.equal(disruptionDetails({ road_name: 'MCLEOD STREET', description: 'Avoid MCLEOD STREET and follow SES advice.' }), 'Avoid Mcleod Street and follow SES advice.')
  assert.equal(disruptionStatus({ impact: 'LANE CLOSURE', direction: 'INBOUND' }), 'Lane closure (Inbound).')
  assert.equal(disruptionDetails({ description: 'Please avoid McLeod Street. Follow SES advice.' }), 'Please avoid McLeod Street. Follow SES advice.')
  assert.equal(disruptionDetails({ description: 'Phone: 1800 000 000' }), '')
  assert.equal(disruptionStatus({ impact: 'impactType: CHANGED CONDITIONS; direction: BOTH DIRECTIONS' }), 'Changed conditions reported in both directions.')
  assert.equal(disruptionStatus({ impact: 'ROAD CLOSED', direction: 'SOUTHBOUND' }), 'Road closed southbound.')
})

// Minimal document implementation to inspect real popup builder output in Node.
// Values go through textContent; this test never launches a browser or map.
const popupDocument = {
  createElement(tagName) {
    return { tagName, className: '', children: [], textContent: '', append(...children) { this.children.push(...children) } }
  },
}
const popupText = (node) => node.textContent + node.children.map(popupText).join('')

test('home and destination popup structure separates emphasized title from unlabelled values', () => {
  const home = travelLocationPopup('Your home', null, '23 BOUNDARY ROAD MORDIALLOC VIC 3195', popupDocument)
  assert.equal(home.children[0].children[0].tagName, 'strong')
  assert.equal(popupText(home.children[0]), 'Your home')
  assert.equal(popupText(home.children[1]), '23 Boundary Road Mordialloc VIC 3195')
  assert.doesNotMatch(popupText(home), /Address:/)
  for (const type of ['Primary destination', 'Backup destination']) {
    const popup = travelLocationPopup(type, 'dsssg', '34 H VOGELS ROAD WATCHEM WEST VIC 3482', popupDocument)
    const [title, name] = popup.children[0].children
    assert.equal(title.tagName, 'strong')
    assert.equal(title.textContent, `${type} - `)
    assert.equal(name.tagName, 'span')
    assert.equal(name.textContent, 'dsssg')
    assert.equal(popupText(popup.children[1]), '34 H Vogels Road Watchem West VIC 3482')
    assert.doesNotMatch(popupText(popup), /Destination:|Address:/)
  }
  const unsafeName = '<img src=x onerror=alert(1)>'
  const popup = travelLocationPopup('Backup destination', unsafeName, null, popupDocument)
  assert.equal(popup.children[0].children[1].textContent, unsafeName)
  assert.equal(popup.children.length, 1)
})

test('disruption popup uses clear label/value groups with formatted text and optional fields', () => {
  const incident = { road_name: 'MCLEOD STREET', event_subtype: 'ROAD DAMAGE', distance_km: 3.8,
    impact: 'impactType: CHANGED CONDITIONS; direction: BOTH DIRECTIONS',
    description: 'MCLEOD STREET DAMAGED. Further details contact Council. Phone: 03 5555 5555' }
  const popup = travelDisruptionPopup(incident, popupDocument)
  assert.equal(popupText(popup.children[0]), 'Reported road disruption')
  assert.deepEqual(popup.children.slice(1).map((group) => group.children.map(popupText)), [
    ['Road', 'Mcleod Street'], ['Type', 'Road Damage'], ['Distance from destination', '3.8 km'],
    ['Conditions', 'Changed conditions reported in both directions.'], ['Details', 'Mcleod Street damaged.'],
  ])
  for (const group of popup.children.slice(1)) {
    assert.equal(group.children[0].tagName, 'strong')
    assert.equal(group.children[1].tagName, 'div')
  }
  assert.doesNotMatch(popupText(popup), /impactType|Further details|Phone|Council|MCLEOD STREET/)
  assert.equal(travelDisruptionPopup({}, popupDocument).children.length, 1)
})
