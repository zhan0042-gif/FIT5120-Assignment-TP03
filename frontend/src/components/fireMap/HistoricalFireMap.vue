<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@maplibre/maplibre-gl-leaflet'
import { formatAustralianDate } from '../../utils/dateTime'
import { openFreeMapStyle } from './openFreeMapStyle'

const props = defineProps({
  householdLocation: { type: Object, required: true },
  points: { type: Array, required: true },
  searchRadiusKm: { type: Number, required: true },
  resolveLocation: { type: Function, required: true },
})

const HOUSEHOLD_COLOR = '#2563eb'
const FIRE_POINT_COLOR = '#ff3b30'

const houseIcon = L.divIcon({
  className: 'firebreak-map-icon',
  html: `<svg viewBox="0 0 40 44" aria-hidden="true"><path d="M20 1C9.5 1 2 8.6 2 18.2 2 30.5 20 43 20 43s18-12.5 18-24.8C38 8.6 30.5 1 20 1Z" fill="${HOUSEHOLD_COLOR}" stroke="#fff" stroke-width="2"/><path d="m11.5 19 8.5-7 8.5 7v10h-6v-6h-5v6h-6Z" fill="#fff"/></svg>`,
  iconSize: [40, 44],
  iconAnchor: [20, 43],
  popupAnchor: [0, -38],
})

const fireIcon = L.divIcon({
  className: 'firebreak-map-icon',
  html: `<svg viewBox="0 0 36 42" aria-hidden="true"><path d="M19.2 1.5c1.1 6.7-4.5 8.9-5.5 14.4-1.7-1.6-2.4-3.8-2.2-6.1C6 14.4 3 19.1 3 24.8 3 33.4 9.5 40 18 40s15-6.6 15-15.2c0-7.1-4.5-13.6-11.3-17.7.2 4.1-1.1 6.5-3 8.5.6-4.8 2.4-8.6.5-14.1Z" fill="${FIRE_POINT_COLOR}" stroke="#fff" stroke-width="2"/><path d="M18.2 20.1c.4 3.6-3.6 5.5-3.6 9.1 0 2.2 1.5 4.1 3.7 4.1 2.3 0 4-1.9 4-4.4 0-2.8-1.5-5.4-4.1-8.8Z" fill="#ffb627"/></svg>`,
  iconSize: [36, 42],
  iconAnchor: [18, 40],
  popupAnchor: [0, -35],
})

function labelledValue(label, value) {
  const group = document.createElement('div')
  group.className = 'popup-field'
  const heading = document.createElement('strong')
  heading.textContent = label
  const detail = document.createElement('div')
  detail.textContent = value
  group.append(heading, detail)
  return { group, detail }
}

function householdPopup() {
  const popup = document.createElement('div')
  const title = document.createElement('strong')
  title.textContent = 'Your home'
  const address = document.createElement('div')
  address.textContent = props.householdLocation.address || 'Address unavailable'
  popup.append(title, address)
  return popup
}

function firePopup(point) {
  const popup = document.createElement('div')
  const title = document.createElement('strong')
  title.textContent = 'Historical fire'
  popup.append(title)

  if (point.start_date) {
    popup.append(
      labelledValue(
        'Recorded',
        formatAustralianDate(point.start_date),
      ).group,
    )
  } else {
    const unavailable = document.createElement('div')
    unavailable.textContent = 'Recorded date unavailable'
    popup.append(unavailable)
  }

  const location = labelledValue(
    'Approximate location',
    'Finding approximate location...',
  )
  popup.append(location.group)

  popup.append(
    labelledValue(
      'Area burned',
      Number.isFinite(point.area_ha)
        ? `${point.area_ha.toLocaleString(undefined, {
            maximumFractionDigits: 2,
          })} ha`
        : 'Area unavailable',
    ).group,
  )

  popup.append(
    labelledValue(
      'Distance from your home',
      Number.isFinite(point.distance_km)
        ? `${point.distance_km.toFixed(1)} km`
        : 'Distance unavailable',
    ).group,
  )

  return {
    popup,
    locationValue: location.detail,
  }
}

const mapContainer = ref(null)
let map
let layoutFrame
const fireMarkers = new Map()

function coordinateKey(point) {
  return `${point.latitude},${point.longitude}`
}

function focusPoint(point) {
  const marker = fireMarkers.get(coordinateKey(point))
  if (!map || !marker) return false
  map.panTo(marker.getLatLng())
  marker.openPopup()
  return true
}

defineExpose({ focusPoint })

onMounted(() => {
  map = L.map(mapContainer.value)

  L.maplibreGL({
    style: openFreeMapStyle,
    interactive: false,
  }).addTo(map)

  const householdLatLng = [props.householdLocation.latitude, props.householdLocation.longitude]

  L.circle(householdLatLng, {
    radius: props.searchRadiusKm * 1000,
    color: HOUSEHOLD_COLOR,
    weight: 1,
    fillOpacity: 0.05,
  }).addTo(map)

  L.marker(householdLatLng, { icon: houseIcon, title: 'Your home' })
    .addTo(map)
    .bindPopup(householdPopup())

  const bounds = L.latLng(householdLatLng).toBounds(props.searchRadiusKm * 2000)

  for (const point of props.points) {
    const latLng = [point.latitude, point.longitude]
    bounds.extend(latLng)
    const { popup, locationValue } = firePopup(point)
    let locationLoaded = false
    const marker = L.marker(latLng, { icon: fireIcon, title: 'Historical fire' })
      .addTo(map)
      .bindPopup(popup)
    fireMarkers.set(coordinateKey(point), marker)
    marker.on('popupopen', async () => {
      if (locationLoaded) return
      locationLoaded = true
      try {
        const address = await props.resolveLocation(point)
        locationValue.textContent = address || 'Approximate location unavailable'
      } catch {
        locationValue.textContent = 'Approximate location unavailable'
      }
    })
  }

  const fitOptions = { padding: [24, 24], maxZoom: 12 }
  map.fitBounds(bounds, fitOptions)

  layoutFrame = requestAnimationFrame(() => {
    map.invalidateSize()
    map.fitBounds(bounds, fitOptions)
  })
})

onBeforeUnmount(() => {
  if (layoutFrame) cancelAnimationFrame(layoutFrame)
  fireMarkers.clear()
  if (map) map.remove()
})
</script>

<template>
  <div class="map-shell">
    <div ref="mapContainer" class="fire-map" role="img" aria-label="Map of your home and nearby historical bushfire records"></div>
    <div class="map-legend" aria-label="Map legend">
      <span class="legend-item">
        <svg class="legend-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-7 9 7v9h-6v-6H9v6H3Z" /></svg>
        Your home
      </span>
      <span class="legend-item">
        <svg class="legend-icon legend-icon-fire" viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2c1 5-3 6-3 10-1-1-2-3-1-5-3 3-5 6-5 9a8 8 0 0 0 16 0c0-5-3-9-7-11 0 3-1 4-2 5 1-3 2-5 2-8Z" /></svg>
        Historical fire
      </span>
      <span class="legend-item"><span class="legend-radius" aria-hidden="true"></span>{{ searchRadiusKm }} km area</span>
    </div>
  </div>
</template>

<style scoped>
.map-shell {
  position: relative;
  isolation: isolate;
  min-width: 0;
  width: 100%;
}

.fire-map {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  background: #ddd;
}

:deep(.firebreak-map-icon) {
  background: transparent;
  border: 0;
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.35));
}

:deep(.leaflet-popup-content > strong) {
  display: block;
  margin-bottom: 0.65rem;
}

:deep(.popup-field) {
  margin-top: 0.55rem;
}

:deep(.popup-field strong) {
  display: block;
  font-size: 0.72rem;
}

.map-legend {
  position: absolute;
  z-index: 500;
  left: 0.75rem;
  bottom: 0.75rem;
  display: grid;
  gap: 0.4rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(27, 20, 16, 0.15);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  color: #1b1410;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  font-size: 0.78rem;
  line-height: 1.2;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-icon {
  width: 1.25rem;
  height: 1.25rem;
  fill: #2563eb;
}

.legend-icon-fire {
  fill: #ff3b30;
}

.legend-radius {
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid #2563eb;
  border-radius: 50%;
}

@media (max-width: 560px) {
  .map-legend {
    position: static;
    margin-top: 0.6rem;
    grid-template-columns: 1fr;
  }
}
</style>
