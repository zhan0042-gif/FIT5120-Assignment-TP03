import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  OPEN_FREE_MAP_ATTRIBUTION,
  openFreeMapStyle,
} from '../src/components/fireMap/openFreeMapStyle.js'

test('OpenFreeMap style uses the public vector source with complete attribution', () => {
  assert.equal(openFreeMapStyle.version, 8)
  assert.equal(openFreeMapStyle.sources.openmaptiles.type, 'vector')
  assert.equal(openFreeMapStyle.sources.openmaptiles.url, 'https://tiles.openfreemap.org/planet')
  assert.equal(openFreeMapStyle.sources.openmaptiles.attribution, OPEN_FREE_MAP_ATTRIBUTION)
  assert.match(OPEN_FREE_MAP_ATTRIBUTION, /OpenFreeMap/)
  assert.match(OPEN_FREE_MAP_ATTRIBUTION, /OpenMapTiles/)
  assert.match(OPEN_FREE_MAP_ATTRIBUTION, /OpenStreetMap/)
  assert.doesNotMatch(JSON.stringify(openFreeMapStyle), /access_token|api[_-]?key/i)
})

test('focused basemap keeps context layers and omits distracting map detail', () => {
  const layers = new Map(openFreeMapStyle.layers.map((layer) => [layer.id, layer]))
  const retainedLayers = [
    'land',
    'residential-areas',
    'parks',
    'woodland',
    'water',
    'waterways',
    'minor-roads',
    'major-roads',
    'major-road-labels',
    'locality-labels',
    'town-labels',
  ]

  for (const layer of retainedLayers) assert.ok(layers.has(layer), `${layer} should be retained`)

  const sourceLayers = new Set(openFreeMapStyle.layers.map((layer) => layer['source-layer']).filter(Boolean))
  for (const omitted of ['poi', 'building', 'aerodrome_label']) {
    assert.equal(sourceLayers.has(omitted), false, `${omitted} should not be rendered`)
  }

  assert.equal(layers.get('minor-roads').minzoom, 12)
  assert.equal(layers.get('major-road-labels').minzoom, 11.5)
  assert.equal(layers.get('water').paint['fill-color'], '#cddfe9')
  assert.equal(layers.get('parks').paint['fill-color'], '#dce8d6')
})
