<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { formatAustralianDate } from '../../utils/dateTime'

const props = defineProps({
  householdLocation: { type: Object, required: true },
  points: { type: Array, required: true },
  searchRadiusKm: { type: Number, required: true },
})

// circleMarker avoids Leaflet's default marker icon, whose asset paths break
// under bundlers unless manually re-pointed. Colors match style.css tokens
// (--color-accent / --color-danger) since Leaflet path options need literal
// CSS color strings, not custom properties.
const HOUSEHOLD_COLOR = '#ff6b35'
const FIRE_POINT_COLOR = '#ff3b30'

const mapContainer = ref(null)
let map

onMounted(() => {
  map = L.map(mapContainer.value)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map)

  const householdLatLng = [props.householdLocation.latitude, props.householdLocation.longitude]

  L.circle(householdLatLng, {
    radius: props.searchRadiusKm * 1000,
    color: HOUSEHOLD_COLOR,
    weight: 1,
    fillOpacity: 0.05,
  }).addTo(map)

  L.circleMarker(householdLatLng, {
    radius: 9,
    color: HOUSEHOLD_COLOR,
    fillColor: HOUSEHOLD_COLOR,
    fillOpacity: 1,
    weight: 2,
  })
    .addTo(map)
    .bindPopup('Your household')

  const bounds = L.latLngBounds([householdLatLng])

  for (const point of props.points) {
    const latLng = [point.latitude, point.longitude]
    bounds.extend(latLng)
    const seasonLabel = point.season ? `Season ${point.season}` : 'Season unknown'
    const dateLabel = point.start_date ? formatAustralianDate(point.start_date) : 'Date unknown'
    L.circleMarker(latLng, {
      radius: 5,
      color: FIRE_POINT_COLOR,
      fillColor: FIRE_POINT_COLOR,
      fillOpacity: 0.7,
      weight: 1,
    })
      .addTo(map)
      .bindPopup(`<strong>${seasonLabel}</strong><br>${dateLabel}`)
  }

  if (props.points.length) {
    map.fitBounds(bounds, { padding: [32, 32] })
  } else {
    map.setView(householdLatLng, 11)
  }
})

onBeforeUnmount(() => {
  if (map) map.remove()
})
</script>

<template>
  <div ref="mapContainer" class="fire-map" role="img" aria-label="Map of household location and nearby historical bushfire records"></div>
</template>

<style scoped>
.fire-map {
  width: 100%;
  height: 32rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
}
</style>
