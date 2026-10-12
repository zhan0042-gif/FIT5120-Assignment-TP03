<script setup>
import { routeKilometres, routeMinutes } from '../../utils/travelRouteFormat'

defineProps({ routes: { type: Array, default: () => [] } })

const TYPE_LABELS = { primary: 'Primary destination', backup: 'Backup destination' }

function hasRoute(route) {
  return route.status === 'available' && route.distance_m != null && route.travel_time_seconds != null
}
</script>

<template>
  <section v-if="routes.length" class="route-summary" aria-labelledby="route-summary-title">
    <h2 id="route-summary-title">Road routes</h2>
    <ul>
      <li v-for="route in routes" :key="route.destination_id">
        <strong>{{ TYPE_LABELS[route.destination_type] ?? 'Destination' }}</strong>
        {{ route.destination_name }}:
        <template v-if="hasRoute(route)">
          {{ routeKilometres(route.distance_m) }} km, about {{ routeMinutes(route.travel_time_seconds) }} min by road
        </template>
        <template v-else>no road route available</template>
      </li>
    </ul>
    <p class="route-summary-note">Distances and driving times only; they do not say whether a route is safe.</p>
  </section>
</template>

<style scoped>
.route-summary { margin-top: 1rem; }
.route-summary h2 { font-size: 1.125rem; margin: 0 0 0.4rem; }
.route-summary ul { list-style: none; margin: 0; padding: 0; }
.route-summary li { padding: 0.25rem 0; }
.route-summary-note { color: var(--color-text-muted); font-size: 0.875rem; margin: 0.4rem 0 0; }
</style>
