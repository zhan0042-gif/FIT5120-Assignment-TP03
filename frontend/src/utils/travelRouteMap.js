import { hasMapCoordinates } from './travelMapData.js'

export const TRAVEL_ROUTE_COLORS = { primary: '#2563eb', backup: '#00857a' }

// Reject the entire malformed route: dropping points could invent shortcuts.
// A generous endpoint corridor also rejects valid-range but remote outliers.
export function travelRouteGeometry(route) {
  if (route?.status !== 'available' || !TRAVEL_ROUTE_COLORS[route.destination_type]
    || !hasMapCoordinates(route.origin) || !hasMapCoordinates(route.destination)
    || !Array.isArray(route.geometry) || route.geometry.length < 2) return null
  const endpoints = [route.origin, route.destination]
  for (const axis of ['latitude', 'longitude']) {
    const min = Math.min(...endpoints.map((point) => point[axis]))
    const max = Math.max(...endpoints.map((point) => point[axis]))
    const margin = Math.max(1, max - min)
    if (route.geometry.some((point) => !hasMapCoordinates(point)
      || point[axis] < min - margin || point[axis] > max + margin)) return null
  }
  const positions = route.geometry.map((point) => [point.latitude, point.longitude])
  if (new Set(positions.map((point) => point.join(','))).size < 2) return null
  return positions
}

export function drawTravelRoutes(leaflet, layer, routes) {
  const visible = []
  for (const route of routes ?? []) {
    const geometry = travelRouteGeometry(route)
    if (!geometry) continue
    let line
    try {
      line = leaflet.polyline(geometry, {
        color: TRAVEL_ROUTE_COLORS[route.destination_type], weight: 4, opacity: 0.85,
        lineCap: 'round', lineJoin: 'round', interactive: false,
      })
      line.addTo(layer)
      visible.push(geometry)
    } catch {
      if (line && layer.hasLayer(line)) layer.removeLayer(line)
      // Only this route fails; markers, circles and other routes stay intact.
    }
  }
  return visible
}
