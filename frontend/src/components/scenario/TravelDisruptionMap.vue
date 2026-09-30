<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@maplibre/maplibre-gl-leaflet'
import { openFreeMapStyle } from '../fireMap/openFreeMapStyle'

const props = defineProps({
  destinations: { type: Array, required: true },
  disruptions: { type: Array, required: true },
})

const container = ref(null)
const mapError = ref(false)
let map
let layoutFrame

function popup(title, lines) {
  const content = document.createElement('div')
  const heading = document.createElement('strong')
  heading.textContent = title
  content.append(heading)
  for (const [label, value] of lines) {
    if (value === null || value === undefined || value === '') continue
    const line = document.createElement('div')
    line.textContent = `${label}: ${value}`
    content.append(line)
  }
  return content
}

onMounted(() => {
  try {
    map = L.map(container.value)
    L.maplibreGL({ style: openFreeMapStyle, interactive: false }).addTo(map)
    const bounds = L.latLngBounds([])

    for (const destination of props.destinations) {
      try {
        const position = [destination.latitude, destination.longitude]
        const primary = destination.type === 'Primary destination'
        const color = primary ? '#2563eb' : '#00857a'
        L.circle(position, {
          radius: destination.search_radius_km * 1000,
          color,
          weight: 2,
          fillOpacity: 0.06,
        }).addTo(map)
        bounds.extend(L.latLng(position).toBounds(destination.search_radius_km * 2000))
        L.circleMarker(position, {
          radius: 12,
          color: '#fff',
          weight: 2,
          fillColor: color,
          fillOpacity: 1,
        }).addTo(map).bindPopup(popup(destination.type, [
          ['Destination', destination.destination_name],
          ['Address', destination.destination_address],
          ['Reported within', `${destination.search_radius_km} km`],
        ]))
      } catch {
        // A malformed destination must not prevent other markers or the list.
      }
    }

    for (const disruption of props.disruptions) {
      try {
        const position = [disruption.latitude, disruption.longitude]
        bounds.extend(position)
        L.circleMarker(position, {
          radius: 5,
          color: '#fff',
          weight: 2,
          fillColor: '#d14920',
          fillOpacity: 1,
        }).addTo(map).bindPopup(popup('Reported road disruption', [
          ['Road', disruption.road_name],
          ['Type', disruption.event_subtype || disruption.event_type],
          ['Distance from destination', Number.isFinite(disruption.distance_km) ? `${disruption.distance_km.toFixed(1)} km` : null],
          ['Impact', disruption.impact],
        ]))
      } catch {
        // A malformed marker must not prevent other markers or the list.
      }
    }

    if (!bounds.isValid()) throw new Error('No mappable destination')
    const fitOptions = { padding: [24, 24], maxZoom: 12 }
    map.fitBounds(bounds, fitOptions)
    layoutFrame = requestAnimationFrame(() => {
      map.invalidateSize()
      map.fitBounds(bounds, fitOptions)
    })
  } catch {
    mapError.value = true
    if (map) map.remove()
    map = null
  }
})

onBeforeUnmount(() => {
  if (layoutFrame) cancelAnimationFrame(layoutFrame)
  if (map) map.remove()
})
</script>

<template>
  <div class="map-shell">
    <p v-if="mapError" class="map-fallback" role="status">Map visualization is unavailable. Reported disruption details remain below.</p>
    <div v-show="!mapError" ref="container" class="travel-map" role="img" aria-label="Map of saved evacuation destinations, ten kilometre search areas, and reported road disruptions"></div>
    <div v-if="!mapError" class="map-legend" aria-label="Map legend">
      <span><i class="marker primary"></i>Primary destination</span>
      <span><i class="marker backup"></i>Backup destination</span>
      <span><i class="marker disruption"></i>Reported disruption</span>
      <span><i class="radius"></i>Search radius</span>
    </div>
  </div>
</template>

<style scoped>
.map-shell { min-width: 0; }
.travel-map { width: 100%; height: clamp(20rem, 48vw, 31rem); border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-bg-card-muted); }
.map-fallback { padding: 2rem; border: 1px solid var(--color-border); border-radius: var(--radius); color: var(--color-text-muted); }
.map-legend { display: flex; flex-wrap: wrap; gap: 0.6rem 1.25rem; padding: 0.7rem 0; color: var(--color-text-muted); font-size: 0.85rem; }
.map-legend span { display: inline-flex; align-items: center; gap: 0.4rem; }
.marker, .radius { display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 50%; }
.marker.primary { background: #2563eb; }
.marker.backup { background: #00857a; }
.marker.disruption { background: #d14920; }
.radius { border: 2px solid #2563eb; }
</style>
