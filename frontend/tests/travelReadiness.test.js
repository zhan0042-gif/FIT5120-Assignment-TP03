import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { buildTravelMapData } from '../src/utils/travelMapData.js'
import {
  coreDisruptionDescription,
  destinationAddress,
  disruptionStatus,
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
  assert.equal((map.match(/L\.circleMarker\(position/g) ?? []).length, 2)
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
  assert.match(panel, /primary_destination/)
  assert.match(panel, /backup_destinations/)
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

test('destination summaries preserve labels, one address, counts and the 10 km result', async () => {
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  assert.match(panel, /type: 'Primary destination'/)
  assert.match(panel, /type: 'Backup destination'/)
  assert.match(panel, /destination\.destination_name/)
  assert.match(panel, /destinationAddress\(destination\)/)
  assert.match(panel, /destination\.active_disruption_count/)
  assert.match(panel, /No nearby disruptions reported within \{\{ destination\.search_radius_km \}\} km/)
  assert.equal(destinationAddress({ destination_name: '71 B Hateleys Road, Arapiles VIC 3409', destination_address: '71 B Hateleys Road, Arapiles VIC 3409' }), '')
  assert.equal(destinationAddress({ destination_name: 'gr', destination_address: '71 B Hateleys Road, Arapiles VIC 3409' }), '71 B Hateleys Road, Arapiles VIC 3409')
})

test('disruption cards retain every required field in human reading order', async () => {
  const panel = await source('../src/components/scenario/TravelDisruptionPanel.vue')
  const card = panel.slice(panel.indexOf('<article'), panel.indexOf('</article>'))
  const fields = ['event_subtype', 'distance_km', 'road_name', 'disruptionStatus(disruption)', 'coreDisruptionDescription(disruption.description)', 'last_updated']
  const positions = fields.map((field) => card.indexOf(field))
  assert.ok(positions.every((position) => position >= 0))
  assert.deepEqual(positions, [...positions].sort((a, b) => a - b))
  assert.match(panel, /v-for="disruption in destination\.disruptions"/)
  assert.doesNotMatch(panel, /Phone:|Email:|Contact:/)
})

test('impact and direction form a readable status without inventing missing values', () => {
  assert.equal(disruptionStatus({ impact: 'Road closed', direction: 'Both directions' }), 'Road closed in both directions')
  assert.equal(disruptionStatus({ impact: 'Road closed', direction: 'Southbound' }), 'Road closed southbound')
  assert.equal(disruptionStatus({ impact: 'direction: Both directions; impactType: Changed conditions' }), 'Changed conditions in both directions')
  assert.equal(disruptionStatus({ impact: 'Changed conditions' }), 'Changed conditions')
  assert.equal(disruptionStatus({ direction: 'Northbound' }), 'Reported direction: Northbound')
  assert.equal(disruptionStatus({ impact: 'Lane closure', direction: 'Inbound' }), 'Lane closure (Inbound)')
})

test('presentation removes safe contact suffixes but preserves raw and uncertain descriptions', () => {
  const disruption = { description: 'Kirwans Bridge CLOSED due to bridge damage. Further details contact Strathbogie Shire. Phone: 1800 000 000 Email: roads@example.org' }
  assert.equal(coreDisruptionDescription(disruption.description), 'Kirwans Bridge CLOSED due to bridge damage.')
  assert.match(disruption.description, /Phone: 1800 000 000 Email:/)
  assert.equal(coreDisruptionDescription('Please avoid the area. Further details: Strathbogie Shire 03 5555 5555'), 'Please avoid the area.')
  assert.equal(coreDisruptionDescription('Contact: 03 5555 5555'), 'Contact: 03 5555 5555')
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
  assert.match(page, /v-if="mapData\.destinations\.length"/)
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
