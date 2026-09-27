export const OPEN_FREE_MAP_ATTRIBUTION =
  '<a href="https://openfreemap.org/">OpenFreeMap</a> ' +
  '<a href="https://openmaptiles.org/">© OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

const OPEN_FREE_MAP_SOURCE = 'openmaptiles'
const labelText = ['coalesce', ['get', 'name_en'], ['get', 'name']]

export const openFreeMapStyle = {
  version: 8,
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {
    [OPEN_FREE_MAP_SOURCE]: {
      type: 'vector',
      url: 'https://tiles.openfreemap.org/planet',
      attribution: OPEN_FREE_MAP_ATTRIBUTION,
    },
  },
  layers: [
    {
      id: 'land',
      type: 'background',
      paint: { 'background-color': '#f4f0e7' },
    },
    {
      id: 'residential-areas',
      type: 'fill',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'landuse',
      maxzoom: 16,
      filter: ['==', ['get', 'class'], 'residential'],
      paint: { 'fill-color': '#ebe7de', 'fill-opacity': 0.72 },
    },
    {
      id: 'parks',
      type: 'fill',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'park',
      paint: { 'fill-color': '#dce8d6', 'fill-opacity': 0.82 },
    },
    {
      id: 'woodland',
      type: 'fill',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'landcover',
      minzoom: 7,
      filter: ['==', ['get', 'class'], 'wood'],
      paint: { 'fill-color': '#d7e4d1', 'fill-opacity': 0.68 },
    },
    {
      id: 'water',
      type: 'fill',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'water',
      paint: { 'fill-color': '#cddfe9' },
    },
    {
      id: 'waterways',
      type: 'line',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'waterway',
      minzoom: 8,
      paint: {
        'line-color': '#bdd4e1',
        'line-opacity': 0.8,
        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.4, 14, 1.4],
      },
    },
    {
      id: 'minor-roads',
      type: 'line',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'transportation',
      minzoom: 12,
      filter: ['match', ['get', 'class'], ['minor', 'service'], true, false],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#ded9cf',
        'line-opacity': 0.68,
        'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.45, 16, 1.35],
      },
    },
    {
      id: 'major-road-casing',
      type: 'line',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'transportation',
      minzoom: 7,
      filter: ['match', ['get', 'class'], ['primary', 'secondary', 'tertiary', 'trunk', 'motorway'], true, false],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#cfc7b9',
        'line-opacity': 0.86,
        'line-width': ['interpolate', ['linear'], ['zoom'], 7, 1.2, 12, 3.1, 16, 7],
      },
    },
    {
      id: 'major-roads',
      type: 'line',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'transportation',
      minzoom: 7,
      filter: ['match', ['get', 'class'], ['primary', 'secondary', 'tertiary', 'trunk', 'motorway'], true, false],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#fffdf8',
        'line-opacity': 0.94,
        'line-width': ['interpolate', ['linear'], ['zoom'], 7, 0.7, 12, 2.2, 16, 5.6],
      },
    },
    {
      id: 'water-labels',
      type: 'symbol',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'water_name',
      minzoom: 8,
      layout: {
        'text-field': labelText,
        'text-font': ['Noto Sans Italic'],
        'text-size': 11,
        'text-max-width': 7,
      },
      paint: {
        'text-color': '#52758a',
        'text-halo-color': 'rgba(244, 240, 231, 0.88)',
        'text-halo-width': 1,
      },
    },
    {
      id: 'major-road-labels',
      type: 'symbol',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'transportation_name',
      minzoom: 11.5,
      filter: ['match', ['get', 'class'], ['primary', 'secondary', 'tertiary', 'trunk', 'motorway'], true, false],
      layout: {
        'symbol-placement': 'line',
        'symbol-spacing': 420,
        'text-field': labelText,
        'text-font': ['Noto Sans Regular'],
        'text-size': 11,
      },
      paint: {
        'text-color': '#746e64',
        'text-halo-color': 'rgba(255, 253, 248, 0.94)',
        'text-halo-width': 1.2,
      },
    },
    {
      id: 'locality-labels',
      type: 'symbol',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'place',
      minzoom: 9,
      filter: ['match', ['get', 'class'], ['suburb', 'neighbourhood', 'quarter', 'hamlet', 'village'], true, false],
      layout: {
        'text-field': labelText,
        'text-font': ['Noto Sans Regular'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 9, 10, 13, 12],
        'text-max-width': 8,
      },
      paint: {
        'text-color': '#514d47',
        'text-halo-color': 'rgba(244, 240, 231, 0.95)',
        'text-halo-width': 1.2,
      },
    },
    {
      id: 'town-labels',
      type: 'symbol',
      source: OPEN_FREE_MAP_SOURCE,
      'source-layer': 'place',
      minzoom: 5,
      filter: ['match', ['get', 'class'], ['town', 'city'], true, false],
      layout: {
        'text-field': labelText,
        'text-font': ['Noto Sans Bold'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 5, 11, 11, 15],
        'text-max-width': 8,
      },
      paint: {
        'text-color': '#3f3c37',
        'text-halo-color': 'rgba(244, 240, 231, 0.96)',
        'text-halo-width': 1.4,
      },
    },
  ],
}
