<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@maplibre/maplibre-gl-leaflet'
import { travelLocationPopup, travelDisruptionPopup } from '../../utils/travelReadinessPresentation'
import { hasMapCoordinates } from '../../utils/travelMapData'
import { openFreeMapStyle } from '../fireMap/openFreeMapStyle'

const props = defineProps({
  householdLocation: { type: Object, default: null },
  destinations: { type: Array, required: true },
  disruptions: { type: Array, required: true },
})

const container = ref(null)
const mapError = ref(false)
let map
let layoutFrame
let homeMarker
let destinationBounds
const fitOptions = { padding: [24, 24], maxZoom: 12 }

const homeIcon = L.divIcon({
  className: 'travel-home-icon',
  html: '<svg viewBox="0 0 40 44" aria-hidden="true"><path d="M20 1C9.5 1 2 8.6 2 18.2 2 30.5 20 43 20 43s18-12.5 18-24.8C38 8.6 30.5 1 20 1Z" fill="#2563eb" stroke="#fff" stroke-width="2"/><path d="m11.5 19 8.5-7 8.5 7v10h-6v-6h-5v6h-6Z" fill="#fff"/></svg>',
  iconSize: [40, 44],
  iconAnchor: [20, 43],
  popupAnchor: [0, -38],
})
const disruptionIcon = L.divIcon({
  className: 'travel-disruption-icon',
  html: '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3 38 35H2Z" fill="#e34b12" stroke="#fff" stroke-width="3" stroke-linejoin="round"/><path d="M20 14v10" stroke="#fff" stroke-width="4" stroke-linecap="round"/><circle cx="20" cy="30" r="2.3" fill="#fff"/></svg>',
  iconSize: [36, 36],
  iconAnchor: [18, 18],
  popupAnchor: [0, -18],
})

function fitMap() {
  if (!map || !destinationBounds?.isValid()) return
  const bounds = L.latLngBounds(destinationBounds.getSouthWest(), destinationBounds.getNorthEast())
  if (hasMapCoordinates(props.householdLocation)) {
    bounds.extend([props.householdLocation.latitude, props.householdLocation.longitude])
  }
  map.fitBounds(bounds, fitOptions)
}

function updateHomeMarker() {
  if (!map) return
  if (homeMarker) map.removeLayer(homeMarker)
  homeMarker = null
  if (hasMapCoordinates(props.householdLocation)) {
    homeMarker = L.marker([props.householdLocation.latitude, props.householdLocation.longitude], {
      icon: homeIcon, title: 'Your home', zIndexOffset: 1000,
    }).addTo(map).bindPopup(travelLocationPopup('Your home', null, props.householdLocation.address))
  }
  fitMap()
}

watch(() => props.householdLocation, updateHomeMarker)

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
        }).addTo(map).bindPopup(travelLocationPopup(
          destination.type, destination.destination_name, destination.destination_address,
        ))
      } catch {
        // A malformed destination must not prevent other markers or the list.
      }
    }

    for (const disruption of props.disruptions) {
      try {
        const position = [disruption.latitude, disruption.longitude]
        bounds.extend(position)
        L.marker(position, { icon: disruptionIcon, title: 'Reported road disruption', zIndexOffset: 500 })
          .addTo(map).bindPopup(travelDisruptionPopup(disruption))
      } catch {
        // A malformed marker must not prevent other markers or the list.
      }
    }

    if (!bounds.isValid()) throw new Error('No mappable destination')
    destinationBounds = bounds
    updateHomeMarker()
    layoutFrame = requestAnimationFrame(() => {
      map.invalidateSize()
      fitMap()
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
    <div v-show="!mapError" ref="container" class="travel-map" role="img" aria-label="Map of your home, saved evacuation destinations, ten kilometre search areas, and reported road disruptions"></div>
    <div v-if="!mapError" class="map-legend" aria-label="Map legend">
      <span><i class="marker primary"></i>Primary destination</span>
      <span><i class="marker backup"></i>Backup destination</span>
      <span v-if="householdLocation"><i class="marker home">&#8962;</i>Your home</span>
      <span><i class="marker disruption">!</i>Reported disruption</span>
      <span><i class="radius"></i>10 km search area</span>
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
.marker.home { background: #2563eb; color: #fff; border-radius: 3px; font-weight: 700; text-align: center; width: 1.1rem; height: 1.1rem; line-height: 1.1rem; }
.marker.disruption { background: #e34b12; color: #fff; clip-path: polygon(50% 0, 100% 100%, 0 100%); border-radius: 0; width: 1.2rem; height: 1.2rem; text-align: center; font-weight: 800; line-height: 1.5rem; }
:deep(.travel-home-icon), :deep(.travel-disruption-icon) { background: transparent; border: 0; }
:deep(.travel-home-icon svg), :deep(.travel-disruption-icon svg) { width: 100%; height: 100%; filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.45)); }
:deep(.travel-popup) { line-height: 1.45; overflow-wrap: anywhere; }
:deep(.travel-popup-address) { margin-top: 0.3rem; }
:deep(.travel-popup-field) { margin-top: 0.65rem; }
:deep(.travel-popup-field > strong) { display: block; margin-bottom: 0.15rem; }
.radius { border: 2px solid #2563eb; }
</style>
